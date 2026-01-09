from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.wardrobe_service import wardrobe_service
from app.services.user_service import user_service # Optional: to verify user exists

router = APIRouter()

class WardrobeFetchRequest(BaseModel):
    user_id: str
    mobile: str

@router.post("/items")
async def get_wardrobe_items(request: WardrobeFetchRequest):
    """
    Fetch all wardrobe items for a user.
    """
    print(f"--> Received Fetch Wardrobe Request: user_id={request.user_id}, mobile={request.mobile}")
    # 1. Access Control (Optional verification)
    # in a real app, verify mobile matches user_id or use session token. 
    # For now, we trust the inputs as per requirements.
    
    from app.core.config import settings

    items = wardrobe_service.get_user_wardrobe(request.user_id)
    
    # Enrich items with Image URL (path only)
    # Format: /v1/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}
    # Note: We assume the base URL is handled by the client as requested.
    
    project_id = settings.APPWRITE_PROJECT_ID
    bucket_id = settings.APPWRITE_WARDROBE_BUCKET_ID
    
    enriched_items = []
    for item in items:
        image_id = item.get("image_id")
        if image_id:
            # Construct Proxy URL
            # Format: /proxy/images/{bucket_id}/{file_id}
            item["image_url"] = f"/proxy/images/{bucket_id}/{image_id}"
        else:
            item["image_url"] = None
        enriched_items.append(item)
    
    print(f"--> Sending back {len(enriched_items)} items for user {request.user_id}")
    return {
        "status": "success",
        "data": enriched_items
    }

class WardrobeRemoveRequest(BaseModel):
    user_id: str
    item_ids: list[str]

@router.post("/remove")
async def remove_wardrobe_items(request: WardrobeRemoveRequest):
    """
    Remove one or more items from the wardrobe.
    Executes deletions in PARALLEL for performance.
    """
    print(f"--> Received Remove Request: user_id={request.user_id}, items={request.item_ids}")
    
    import asyncio
    from starlette.concurrency import run_in_threadpool
    import functools
    
    deleted_count = 0
    errors = []

    async def remove_single_item(item_id):
        print(f"Processing item removal: {item_id}")
        # Wrap blocking service call in threadpool
        func = functools.partial(wardrobe_service.delete_wardrobe_item, request.user_id, item_id)
        success = await run_in_threadpool(func)
        return item_id, success

    # Create tasks
    tasks = [remove_single_item(iid) for iid in request.item_ids]
    
    # Run in parallel
    results = await asyncio.gather(*tasks)
    
    for item_id, success in results:
        if success:
            print(f"Successfully deleted item: {item_id}")
            deleted_count += 1
        else:
            print(f"Failed to delete item: {item_id}")
            errors.append(item_id)
            
    return {
        "status": "success",
        "message": f"Deleted {deleted_count} items",
        "deleted_count": deleted_count,
        "errors": errors
    }
