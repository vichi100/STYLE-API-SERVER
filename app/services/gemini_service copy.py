from google import genai
from google.genai import types
import json
import typing_extensions as typing
from PIL import Image, UnidentifiedImageError
import logging
import io
from app.core.config import settings

logger = logging.getLogger(__name__)

# 1. Define the Strict JSON Schema
class ClothingItem(typing.TypedDict):
    item_name: str
    category: str  # e.g., "Top", "Bottom", "Footwear", "Accessory"
    color: str
    tags: list[str] # e.g., ["long-sleeve", "cotton", "distressed"]

class OutfitAnalysis(typing.TypedDict):
    summary: str
    items: list[ClothingItem]

class GeminiFashionService:
    def __init__(self):
        # Initialize the new Google GenAI Client
        self.api_key = settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found in settings.")
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Error initializing Gemini client: {e}")
                self.client = None

    def analyze_image(self, image_path: str = None, image_data: bytes = None):
        """
        Analyze image from path or bytes using Gemini.
        """
        if not self.client:
            logger.error("Gemini client not initialized.")
            return None

        try:
            # Load Image
            img = None
            if image_data:
                img = Image.open(io.BytesIO(image_data))
            elif image_path:
                img = Image.open(image_path)
            else:
                logger.error("No image provided.")
                return None

            # 3. The Prompt
            prompt = """
            You are an expert fashion stylist AI for the app 'Adā'.
            Analyze the clothing worn by the person in this image.

            STRICT RULES:
            1. Identify only CLEARLY VISIBLE items.
            2. Ignore background objects, furniture, or people in the distance.
            3. If the image is cropped (e.g., no feet visible), do NOT guess the shoes.
            4. Treat a garment and its details (logos, prints) as ONE item.
            
            # For 'category', use one of: "Top", "Bottom", "Footwear", "Outerwear", "Dress", "Accessory".
            # For 'tags', include details like fit, fabric texture, pattern, neckline, and sleeve length.
            """

            # 4. Generate Content
            # The new SDK uses client.models.generate_content
            # 'contents' accepts text and images (PIL Image is supported)
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", # Using strict name or 'gemini-2.0-flash' as seen in logs
                contents=[prompt, img],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=OutfitAnalysis
                )
            )
            
            # 5. Return parsed JSON (It is already a dict/object or text)
            print(f"Gemini Response: {response.text}")
            
            # response.parsed should be available if schema is respected, otherwise parse text
            if hasattr(response, 'parsed') and response.parsed:
                return response.parsed
            
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Gemini Analysis Failed: {e}")
            return None

gemini_service = GeminiFashionService()
