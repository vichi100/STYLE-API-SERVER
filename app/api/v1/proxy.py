from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from app.core.config import settings

router = APIRouter()

# Shared client for efficiency (global is okay for this scope, or use lifespan)
# Limits: 100 connections max, 30s timeout
proxy_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20, max_connections=100), timeout=30.0)

@router.get("/images/{bucket_id}/{file_id}")
async def get_proxy_image(bucket_id: str, file_id: str):
    """
    Proxies image requests to Appwrite using streaming to save RAM.
    """
    project_id = settings.APPWRITE_PROJECT_ID
    endpoint = settings.APPWRITE_ENDPOINT
    api_key = settings.APPWRITE_API_KEY
    
    # Construct Appwrite View URL
    url = f"{endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}&mode=admin"
    
    # Appwrite requires X-Appwrite-Project and X-Appwrite-Key headers for admin access
    headers = {
        "X-Appwrite-Project": project_id,
        "X-Appwrite-Key": api_key
    }
    
    # Create a generator to stream the content
    async def iterfile():
        # Use the shared client
        try:
            async with proxy_client.stream("GET", url, headers=headers) as r:
                if r.status_code != 200:
                    # Log error but return what we got or yield error bytes
                    pass 
                    
                async for chunk in r.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as exc:
             print(f"Proxy Error: {exc}")
             # Connection failed, nothing to yield
             return

    return StreamingResponse(iterfile(), media_type="image/jpeg")
