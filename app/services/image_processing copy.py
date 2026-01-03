from rembg import remove, new_session
from PIL import Image
import io

def remove_background_service(image_data: bytes) -> bytes:
    """
    Remove background from the input image data using rembg.
    
    Args:
        image_data (bytes): Input image data in bytes.
        
    Returns:
        bytes: Processed image data in PNG format with transparent background.
    """
    # Load image from bytes
    input_image = Image.open(io.BytesIO(image_data))
    
    # Remove background
    output_image = remove(input_image)
    
    # Save to bytes
    output_buffer = io.BytesIO()
    output_image.save(output_buffer, format="PNG")
    output_buffer.seek(0)
    
    return output_buffer.getvalue()
