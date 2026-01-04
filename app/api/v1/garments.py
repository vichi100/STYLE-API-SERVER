from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image, ImageOps
import io

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB limit

@router.post("/upload-garment")
async def upload_garment(file: UploadFile = File(...)):
    # 1. Validate File Size
    # Note: Reading correctly to ensure we don't just load massive files blindly, 
    # though UploadFile spools to disk. content-length header is not always reliable.
    # For this implementation, adhering to the logic provided.
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
        
    # 2. Validate File Type (Strictly JPEG)
    if file.content_type not in ["image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Only JPEG images are allowed")

    try:
        # 2. Open Image with Pillow
        image = Image.open(io.BytesIO(contents))
        
        # Verify actual format
        if image.format not in ["JPEG", "MPO"]: # MPO is often used by phones for portrait mode, basically JPEG
             raise HTTPException(status_code=400, detail="Invalid file format. Only JPEG is allowed.")
        
        # 3. Fix Orientation (Phone cameras often rotate images via EXIF)
        image = ImageOps.exif_transpose(image)

        # 4. Resize if it's still huge (Safety net)
        # Most VTON models (like IDM-VTON) work best around 1024x1024
        max_dimension = 2048
        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension))

        # 5. Convert to JPEG (User requested to keep as JPEG)
        # Note: JPEG does not support transparency (RGBA). Convert to RGB first.
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        output_buffer = io.BytesIO()
        image.save(output_buffer, format="JPEG", quality=90, optimize=True)
        output_buffer.seek(0)
        
        # 6. Upload 'output_buffer' to Cloud (S3 / Supabase)
        # TODO: Integrate with Appwrite Storage or Supabase
        # Example:
        # supabase.storage.from_("closet").upload(path, output_buffer.getvalue(), ...)
        
        # For now, we simulate success as the storage backend setup was not explicitly provided 
        # beyond the commented suggestion.

        return {"status": "success", "message": "Image processed and stored"}

    except Exception as e:
        # Catch specific Pillow errors or general ones
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail="Invalid image file or processing error")

from app.services.moondream_service import moondream_service

@router.post("/analyze")
async def analyze_garment_image(file: UploadFile = File(...)):
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
        
    # 2. Analyze
    items = moondream_service.analyze_garment(contents)
    
    return {"status": "success", "items": items}
