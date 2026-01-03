from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from app.services.image_processing import clothing_segmenter
import io

router = APIRouter()

@router.post("/remove-background")
async def remove_background(file: UploadFile = File(...)):
    """
    Segment clothing and remove background using YOLOv8 (Production Pipeline).
    
    Uses a specialized ClothingSegmenter that:
    1. Filters for clothing/person classes.
    2. Applies segmentation.
    3. Refines mask (Morphology + Contour Filtering) to remove hangers/wires.
    
    - **file**: Image file to process
    
    Returns processed image as PNG.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        contents = await file.read()
        processed_image = clothing_segmenter.segment(contents)
        
        return StreamingResponse(
            io.BytesIO(processed_image), 
            media_type="image/png"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
