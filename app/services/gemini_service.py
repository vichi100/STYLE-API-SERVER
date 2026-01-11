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
    category: str
    custom_category: str
    color: str
    tags: list[str]

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
            Analyze the image to identify any clothing items.
            The image may contain a full outfit on a person, OR a standalone garment (flat lay, hanger, or product shot).
            
            1. Identify all visible clothing items (Top, Bottom, Footwear, Dress, Outerwear, etc.).
            
            STRICT RULES:
            - If it is a floral pattern or texture on a cloth, identify the cloth itself (e.g. 'Floral Dress', 'Patterned Shirt').
            - Only label items that are clearly visible.
            - If the item is occluded, estimate the visible region.
            - Do not hallucinate items outside the frame.

            CLASSIFICATION RULE:
            For each identified item, determine its 'custom_category' based on the following JSON rules. 
            If it matches an item in a list, use the key (e.g. "tops", "shirts", "Layer", "active", "ethnic") as the 'custom_category'.
            If it does not match exactly, you MUST select the closest semantic match from the provided keys. 
            DO NOT USE 'Other'. Everything must be classified into one of the categories below.

            CONSTRAINT FOR FOOTWEAR:
            Any item identified as footwear MUST be classified into "heels", "shoes", or "sandals". Do not use 'Other' for footwear.

            CONSTRAINT FOR BAGS:
            Any item identified as a bag, purse, or clutch MUST be classified as "bags".
            
            {
              "tops": [
                "t-shirt", "tank top", "crop top", "camisole", "bodysuit", "tube top", 
                "muscle tee", "long sleeve tee", "corset", "bustier", "halter top", 
                "off-shoulder top", "one-shoulder top", "cold-shoulder top", 
                "sheer top", "backless top", "wrap top", "peplum top", "blouse", "tunic"
              ],
              "shirts": [
                "button-down shirt", "oxford shirt", "chiffon blouse", "bow-tie blouse"
              ],
              "Layer": [
                "jacket", "blazer", "coat", "trench coat", "vest", "gilet", "denim jacket", 
                "leather jacket", "bomber jacket", "kimono", "sweater", "cardigan", 
                "turtleneck", "pullover", "jumper", "shrug", "bolero", "poncho"
              ],
              "active": [
                "sports bra", "hoodie", "sweatshirt", "track jacket", "performance tee", 
                "gym tank", "rash guard", "fleece pullover"
              ],
              "ethnic": [
                "kurti", "kurta", "choli", "saree blouse", "kameez", "kaftan", 
                "short kurti", "anarkali top"
              ],
              "jeans": [
                "skinny jeans", "straight-leg jeans", "boyfriend jeans", "mom jeans", 
                "bootcut jeans", "flare jeans", "wide-leg jeans"
              ],
              "trousers": [
                "cigarette pants", "palazzo pants", "culottes", "chinos", "cargo pants", 
                "paperbag trousers", "leather pants", "capris", "trousers", 
                "straight-leg pants", "wide-leg pants"
              ],
              "skirts": [
                "mini skirt", "midi skirt", "maxi skirt", "pencil skirt", "a-line skirt", 
                "pleated skirt", "wrap skirt", "denim skirt"
              ],
              "shorts": [
                "denim shorts", "bermuda shorts", "hot pants", "high-waisted shorts", 
                "skorts", "shorts"
              ],
              "ethnic_bottoms": [
                "salwar", "churidar", "patiala", "sharara", "gharara", "dhoti pants", 
                "ethnic skirt", "lehenga", "ghagra"
              ],
              "active_lounge": [
                "leggings", "joggers", "yoga pants", "sweatpants", "track pants", 
                "cycling shorts"
              ],
              "oomph": [
                "sundress", "shirt dress", "t-shirt dress", "wrap dress", "slip dress", 
                "denim dress", "pinafore dress", "mini dress", "midi dress", "maxi dress", 
                "bodycon dress", "a-line dress", "skater dress", "sheath dress", 
                "cocktail dress", "little black dress", "sequin dress", "halter neck dress", 
                "off-shoulder dress"
              ],
              "gown": [
                "evening gown", "mermaid gown", "ball gown", "party gown"
              ],
              "Romps": [
                "jumpsuit", "playsuit", "romper", "dungarees", "overalls", "boiler suit"
              ],
              "heels": [
                "stiletto", "kitten heel", "wedge", "pump", "block heel", "platform", 
                "peep toe", "slingback", "mule", "ankle strap heel", "cone heel", "spool heel"
              ],
              "shoes": [
                "sneaker", "boot", "loafer", "oxford", "ballet flat", "espadrille", 
                "moccasin", "derby", "brogue", "chelsea boot", "ankle boot", "combat boot",
                "running shoe", "trainer", "slip-on"
              ],
              "sandals": [
                "slide", "gladiator", "flip flop", "teva", "birkenstock", "wedge sandal", 
                "strappy sandal", "thong sandal", "sport sandal", "clog"
              ],
              "bags": [
                "crossbody bag", "sling bag", "messenger bag", "saddle bag", "camera bag", 
                "waist bag", "fanny pack", "clutch", "minaudière", "box clutch", 
                "envelope bag", "wristlet", "potli bag", "tote bag", "satchel", "hobo bag", 
                "shoulder bag", "bucket bag", "bowling bag", "handbag"
              ]
            }
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
