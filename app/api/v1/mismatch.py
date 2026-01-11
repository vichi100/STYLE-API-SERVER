from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.wardrobe_service import wardrobe_service

router = APIRouter()

class MismatchFetchRequest(BaseModel):
    user_id: str
    mobile: str

@router.post("/items")
async def get_mismatch_items(request: MismatchFetchRequest):
    """
    Fetch all wardrobe items for the Mismatch feature.
    """
    print(f"--> Received Mismatch Fetch Request: user_id={request.user_id}, mobile={request.mobile}")
    
    from app.core.config import settings

    # Reuse Wardrobe Service to fetch items
    items = wardrobe_service.get_user_wardrobe(request.user_id)
    
    # Enrich items with Image URL (path only)
    project_id = settings.APPWRITE_PROJECT_ID
    bucket_id = settings.APPWRITE_WARDROBE_BUCKET_ID
    
    enriched_items = []
    for item in items:
        image_id = item.get("image_id")
        if image_id:
            # Construct Proxy URL
            item["image_url"] = f"/proxy/images/{bucket_id}/{image_id}"
        else:
            item["image_url"] = None
        enriched_items.append(item)
    
    print(f"--> Sending back {len(enriched_items)} mismatch items for user {request.user_id}")
    return {
        "status": "success",
        "data": enriched_items
    }
