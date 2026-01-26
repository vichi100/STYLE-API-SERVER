from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.style_scoring_service import StyleScoringService
from app.services.appwrite_storage import get_file_bytes
from app.core.config import settings

router = APIRouter()
scoring_service = StyleScoringService()

class WardrobeItem(BaseModel):
    user_id: str
    general_category: str
    specific_category: Optional[str] = None
    custom_category: Optional[str] = None
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    tags: Optional[str] = None
    colors: Optional[list[str]] = None
    caption: Optional[str] = None

class OutfitRequest(BaseModel):
    top: Optional[WardrobeItem] = None
    bottom: Optional[WardrobeItem] = None
    layer: Optional[WardrobeItem] = None
    layer: Optional[WardrobeItem] = None
    mood: Optional[str] = None
    use_rag: Optional[bool] = True

@router.post("/score")
async def score_outfit(request: OutfitRequest):
    """
    Score an outfit composed of Top, Bottom, and optional Layer.
    Fetches images from Appwrite Storage and uses Gemini Vision for analysis.
    """
    
    outfit_images = {}
    outfit_metadata = {}
    
    items = {
        "top": request.top,
        "bottom": request.bottom,
        "layer": request.layer
    }
    
    # 1. Fetch Images & Prepare Metadata
    for category, item in items.items():
        if item and item.image_id:
            # Metadata
            outfit_metadata[category] = item.dict(exclude={"image_url", "image_id"})
            
            # Fetch Image Bytes
            # Assuming bucket_id is the standard wardrobe bucket
            bucket_id = settings.APPWRITE_WARDROBE_BUCKET_ID
            if not bucket_id:
                 # Fallback or error?
                 print("Warning: WARDROBE_BUCKET_ID not set")
                 continue
                 
            print(f"Fetching image for {category}: {item.image_id}")
            img_bytes = get_file_bytes(bucket_id, item.image_id)
            
            if img_bytes:
                outfit_images[category] = img_bytes
            else:
                print(f"Failed to fetch image for {category}")
        elif item:
            # Metadata only if no image
            outfit_metadata[category] = item.dict(exclude={"image_url", "image_id"})

    if not outfit_images:
        raise HTTPException(status_code=400, detail="No images could be retrieved for the outfit items.")

    # 2. Analyze
    try:
        score = scoring_service.analyze_outfit(
            outfit_images=outfit_images,
            outfit_metadata=outfit_metadata,
            target_mood=request.mood,
            use_rag=request.use_rag
        )
        
        if not score:
            raise HTTPException(status_code=500, detail="Style analysis failed to generate a score.")
            
        return {
            "status": "success",
            "data": score
        }

    except Exception as e:
        print(f"Error scoring outfit: {e}")
        raise HTTPException(status_code=500, detail=str(e))
