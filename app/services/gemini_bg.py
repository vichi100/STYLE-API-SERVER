from google import genai
from google.genai import types
from PIL import Image
from rembg import remove
import io
import os
from pydantic import BaseModel
import sys
import os

# 1. Setup path to import app settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from app.core.config import settings
    api_key = settings.GOOGLE_API_KEY
except ImportError:
    api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY not found in settings or environment.")
    exit(1)

# 2. Setup the NEW Google Gen AI Client
client = genai.Client(api_key=api_key)

# 2. Define the Output Schema (Structured Output)
class DetectedItem(BaseModel):
    name: str
    box_2d: list[int] # [ymin, xmin, ymax, xmax] in 0-1000 scale

class ImageAnalysis(BaseModel):
    main_item: DetectedItem

def smart_background_remove(image_path: str, output_path: str):
    print(f"Analyzing {image_path}...")
    original_img = Image.open(image_path).convert("RGBA")
    width, height = original_img.size

    # --- STEP 1: Gemini 2.0 Flash finds the object ---
    # We use 2.0 Flash because it is fast and cheap for bounding boxes
    prompt = """
    Locate the main fashion garment in this image. 
    Ignore hangers, hands holding the item, or background furniture.
    Return the bounding box of ONLY the garment.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[prompt, original_img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ImageAnalysis,
                temperature=0.1
            )
        )
        
        analysis = response.parsed
        if not analysis or not analysis.main_item:
            print("Gemini could not find the item.")
            return

        print(f"Gemini found: {analysis.main_item.name}")
        
        # --- STEP 2: Crop & Remove Background ---
        ymin, xmin, ymax, xmax = analysis.main_item.box_2d

        # Convert 0-1000 coordinates to Pixels
        # Add a small buffer (padding) to ensure we don't clip the edges
        buffer = 15 
        left = max(0, int((xmin / 1000) * width) - buffer)
        top = max(0, int((ymin / 1000) * height) - buffer)
        right = min(width, int((xmax / 1000) * width) + buffer)
        bottom = min(height, int((ymax / 1000) * height) + buffer)

        # Crop to the box Gemini found
        cropped_img = original_img.crop((left, top, right, bottom))
        
        # Use RemBG to remove background from this cropped area
        # This is much more accurate than running RemBG on the whole image
        clean_img = remove(cropped_img)

        # --- STEP 3: Save Result ---
        clean_img.save(output_path)
        print(f"✅ Saved transparent image to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

# Run it
smart_background_remove("IMG_2907.jpg", "geminiclean_result.png")