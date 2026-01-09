from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image, ImageOps
import io

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB limit

from app.services.appwrite_storage import upload_image_from_bytes
from app.services.wardrobe_service import wardrobe_service
from app.services.user_service import user_service
from app.core.config import settings
import os
from fastapi import Form
from starlette.concurrency import run_in_threadpool
import functools

@router.post("/upload-garment")
async def upload_garment(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    mobile: str = Form(...)
):
    # 1. Validate File Size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
        
    try:
        # 3. Direct Memory Upload via Threadpool
        # (Client handles processing, so we upload raw bytes)
        wardrobe_bucket = settings.APPWRITE_WARDROBE_BUCKET_ID
        if not wardrobe_bucket:
             raise HTTPException(status_code=500, detail="Wardrobe bucket configuration missing")
        
        # We must wrap the blocking call
        filename = f"{user_id}_{os.urandom(4).hex()}.jpg"
        
        # Create a partial function to pass arguments
        upload_func = functools.partial(
            upload_image_from_bytes, 
            image_data=contents, 
            filename=filename, 
            bucket_id=wardrobe_bucket
        )
        
        # Run in threadpool to avoid blocking event loop
        import time
        upload_start = time.time()
        print("--> Starting Image Upload to Appwrite Storage...")
        
        image_id = await run_in_threadpool(upload_func)
        
        upload_duration = time.time() - upload_start
        print(f"--> Image Upload took {upload_duration:.2f} seconds")
        
        if not image_id:
            raise HTTPException(status_code=500, detail="Failed to upload image to storage")
        
        # Encapsulate logic for URL construction
        # Use Proxy URL (Version agnostic)
        image_url = f"/proxy/images/{wardrobe_bucket}/{image_id}"

        # 5. Create Wardrobe Item in DB
        wardrobe_item = wardrobe_service.create_wardrobe_item(
            user_id=user_id,
            image_id=image_id,
            image_url=image_url,
            category="Uncategorized" # Can be updated later by AI analysis
        )
        wardrobe_id = wardrobe_item["$id"]
        
        # 6. Update User's wardrobe_id_list
        success = user_service.add_wardrobe_item(user_id, wardrobe_id)
        if not success:
             # Should we rollback? For now just log error, but image/wardrobe item exists
             print(f"Failed to link wardrobe {wardrobe_id} to user {user_id}")
        

        
        # 7. Auto-Analyze with Gemini (As requested: call and log time)
        import time
        from app.services.gemini_service import gemini_service
        
        print("--> Starting Gemini Analysis for uploaded item...")
        start_time = time.time()
        
        try:
            # Wrap blocking Gemini call
            analyze_func = functools.partial(gemini_service.analyze_image, image_data=contents)
            # await execute in threadpool
            analysis_result = await run_in_threadpool(analyze_func)
            
            duration = time.time() - start_time
            print(f"--> Gemini Analysis took {duration:.2f} seconds")
            print(f"--> Analysis Result: {analysis_result}")
            
            # 8. Save Analysis to Wardrobe Item
            if analysis_result:
                updates = {}
                
                # Map 'summary' -> 'caption'
                if "summary" in analysis_result:
                    updates["caption"] = analysis_result["summary"]
                
                # Check for items
                if "items" in analysis_result and len(analysis_result["items"]) > 0:
                    first_item = analysis_result["items"][0]
                    
                    # Map 'item_name' -> 'specific_category'
                    if "item_name" in first_item:
                         updates["specific_category"] = first_item["item_name"]
                    
                    # Map 'category' -> 'general_category' (Update existing)
                    if "category" in first_item:
                         updates["general_category"] = first_item["category"]
                         
                    # Map 'tags' -> 'tags' (Convert list to JSON string or use Appwrite array if configured. 
                    # Script said array=False for 'tags' in Wardrobe? Let me check schema script.)
                    # Checking wardrobe.py: create_string_attribute(..., "tags", 128, required=False) -> It is NOT an array in the script!
                    # "tags" is a string attribute (128 chars). So we must join them.
                    if "tags" in first_item and isinstance(first_item["tags"], list):
                         updates["tags"] = ",".join(first_item["tags"])
                    
                    # Map 'color' -> 'colors' (Wardrobe has 'colors' as array=True)
                    # Gemini returns single 'color' string usually, or list? Schema says 'color': str.
                    # Wardrobe schema: "colors", 64, array=True.
                    if "color" in first_item:
                        updates["colors"] = [first_item["color"]]
                
                if updates:
                    print(f"--> Updating Wardrobe Item {wardrobe_id} with AI logic...")
                    wardrobe_service.update_wardrobe_item(wardrobe_id, updates)

        except Exception as e:
            print(f"--> Auto-Analysis Failed: {e}")
            # Do not fail the upload request if analysis fails
            pass 
            
        # Prepare final response data 
        # User requested to match the Wardrobe table structure (flattened)
        response_data = {
             "wardrobe_id": wardrobe_id,
             "image_id": image_id,
             "image_url": image_url,
             "user_id": user_id,
             # Default Values
             "caption": "",
             "specific_category": "",
             "general_category": "Uncategorized",
             "tags": "",
             "colors": []
        }

        # Merge updates if available
        if analysis_result and updates:
             response_data.update(updates)
        
        final_response = {
            "status": "success", 
            "message": "Garment uploaded, analyzed, and saved to wardrobe",
            "data": response_data
        }
        
        print(f"--> Sending Response: {final_response}")
        return final_response

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file or processing error")

from app.services.gemini_service import gemini_service
from typing import Optional

@router.post("/analyze")
async def analyze_garment_image(
    file: UploadFile = File(...),
    # provider param is deprecated but kept for compatibility if needed, 
    # effectively ignored as we strictly use Gemini now.
    provider: str = "gemini" 
):
    """
    Analyze garment image to identify clothing items using Gemini.
    """
    # 1. Read content
    contents = await file.read()
        
    # 4. Analyze using Gemini
    try:
        # We process exclusively with Gemini now
        gemini_result = gemini_service.analyze_image(image_data=contents)
        print(f"--- Gemini Result ---\n{gemini_result}\n---------------------")
        
        # Return standard format expecting by client (list of items)
        return {
            "status": "success", 
            "items": gemini_result, 
            "provider": "gemini"
        }

    except Exception as e:
        print(f"Analysis Error: {e}")
        return {"status": "error", "message": "Failed to analyze image", "items": []}
