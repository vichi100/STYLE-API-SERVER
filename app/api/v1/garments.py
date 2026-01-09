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
        image_id = await run_in_threadpool(upload_func)
        
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
        
        return {
            "status": "success", 
            "message": "Garment uploaded and saved to wardrobe",
            "data": {
                "wardrobe_id": wardrobe_id,
                "image_id": image_id
            }
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file or processing error")

from app.services.moondream_service import moondream_service
from app.services.gemini_service import gemini_service
from typing import Optional

@router.post("/analyze")
async def analyze_garment_image(
    file: UploadFile = File(...),
    provider: str = "all" #"moondream" # Options: "moondream", "gemini", "all"
):
    """
    Analyze garment image to identify clothing items using Moondream.
    """
    # 1. Validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # 2. Validate File Type (Strictly JPEG)
    if file.content_type not in ["image/jpeg", "image/jpg"]:
         raise HTTPException(status_code=400, detail="Only JPEG images are allowed")

    # 3. Verify actual format with Pillow
    try:
        img = Image.open(io.BytesIO(contents))
        if img.format not in ["JPEG", "MPO"]:
            raise HTTPException(status_code=400, detail="Invalid file format. Only JPEG is allowed.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
        
    # 4. Analyze based on provider
    results = {}
    
    if provider in ["moondream", "all"]:
        results["moondream"] = moondream_service.analyze_garment(contents)
        print(f"--- Moondream Result ---\n{results['moondream']}\n------------------------")
        
    if provider in ["gemini", "all"]:
        results["gemini"] = gemini_service.analyze_image(image_data=contents)
        print(f"--- Gemini Result ---\n{results['gemini']}\n---------------------")
        
    if provider == "all":
        return {"status": "success", "results": results}
    elif provider == "gemini":
        return {"status": "success", "items": results.get("gemini"), "provider": "gemini"}
    else:
        return {"status": "success", "items": results.get("moondream"), "provider": "moondream"}
