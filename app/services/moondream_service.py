import moondream as md
from PIL import Image
import io
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class MoondreamService:
    def __init__(self):
        # Initialize with settings
        self.api_key = settings.MOONDREAM_API_KEY
        if not self.api_key:
            logger.warning("MOONDREAM_API_KEY not found in settings.")
            self.model = None
        else:
            try:
                self.model = md.vl(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Error initializing Moondream client: {e}")
                self.model = None

    def analyze_garment(self, image_data: bytes) -> list[str]:
        if not self.model:
            logger.error("Moondream model not initialized.")
            return []

        try:
            image = Image.open(io.BytesIO(image_data))
            
            # The specific prompt requested by the user
            # question = "List the main clothing, fashion or styling items visible in this image, separated by commas. also give the color of each item. do not consider background object in image and the accessory which can not be use for styling."
            
            question = """
"First, describe the outfit in one natural sentence. Then List the main clothing, fashion or styling items visible in this image, separated by commas. also give the color of each item. do not consider background object in image and the accessory which can not be use for styling.

For each item, list:
- item name
-  color
- descriptive tags (such as sleeve length, neckline, fit, pattern) 

Ignore hair, makeup, body features, and background objects.

For each clothing item, write ONE complete line in this exact format:
[item name] - [color] - [comma-separated descriptive tags]

CRITICAL RULE: Treat a piece of clothing and all its details (logos, text, numbers, prints, colored trims, pockets) as ONE single item. 
- Do NOT list "prints" or "logos" as separate lines.
- Do NOT list "trims" or "collars" as separate lines.
- Include these details in the "descriptive tags" section of the main garment instead.

Rules:
- One line per clothing item
- Do NOT create separate sections
- Do NOT list attributes on new lines
- Ignore hair, makeup, body features, and background objects
"""

            answer_data = self.model.query(image, question)
            
            # Flexible handling if the SDK returns a dict or direct string
            answer = answer_data['answer'] if isinstance(answer_data, dict) else answer_data
            print(f"Identified Items before parsing: {answer}")
            # Parse response using new logic
            items = self.parse_and_dedupe(answer)
            print(f"Identified Items after parsing: {items}")
            return items

        except Exception as e:
            logger.error(f"Error analyzing garment: {e}")
            return []

    def parse_and_dedupe(self, text: str):
        items = {}

        for line in text.splitlines():
            line = line.strip()
            if " - " not in line:
                continue

            # ✅ SAFE split (max 3 parts)
            parts = line.split(" - ", 2)
            if len(parts) < 2:
                continue

            item = parts[0].strip().lower()
            color = parts[1].strip().lower()

            tags = []
            if len(parts) == 3:
                REJECT_TAGS = {
                    "wrinkled",
                    "creased",
                    "crumpled",
                    "folded",
                    "dirty",
                    "stained",
                    # "faded",
                    "worn out"
                }
                tags = [
                    t.strip().lower()
                    for t in parts[2].split(",")
                    if t.strip() and t.strip().lower() not in REJECT_TAGS
                ]

            key = (item, color)

            if key not in items:
                items[key] = {
                    "item": item,
                    "color": color,
                    "tags": set()
                }

            for tag in tags:
                items[key]["tags"].add(tag)

        return [
            {
                "item": v["item"],
                "color": v["color"],
                "tags": sorted(v["tags"])
            }
            for v in items.values()
        ]

moondream_service = MoondreamService()
