from fastapi import APIRouter, HTTPException
from app.api.v1.style import OutfitRequest
from app.services.appwrite_storage import get_file_bytes
from app.core.config import settings
from app.services.color_scoring_service import ColorScoringService

router = APIRouter()
color_service = ColorScoringService()

@router.post("/color-score")
async def color_score_outfit(request: OutfitRequest):
    """
    Score outfit specifically against the Dictionary of Colour Combinations.
    Uses 'pure' Gemini analysis with the full dictionary loaded.
    """
    outfit_images = {}
    outfit_metadata = {}
    
    items = {
        "top": request.top,
        "bottom": request.bottom,
        "layer": request.layer
    }
    
    # 1. Fetch Images & Metadata (Reused logic, could be refactored to shared utility)
    for category, item in items.items():
        if item and item.image_id:
            outfit_metadata[category] = item.dict(exclude={"image_url", "image_id"})
            
            bucket_id = settings.APPWRITE_WARDROBE_BUCKET_ID
            if bucket_id:
                img_bytes = get_file_bytes(bucket_id, item.image_id)
                if img_bytes:
                    outfit_images[category] = img_bytes
        elif item:
             outfit_metadata[category] = item.dict(exclude={"image_url", "image_id"})

    if not outfit_images:
        raise HTTPException(status_code=400, detail="No images could be retrieved.")

    # 2. Analyze Colors
    try:
        result = color_service.analyze_outfit_with_palette(
            outfit_images, 
            outfit_metadata, 
            target_mood=request.mood
        )
        
        if not result:
             raise HTTPException(status_code=500, detail="Analysis failed.")
             
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
