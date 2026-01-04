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
            question = "List the main clothing, fashion or styling items visible in this image, separated by commas. do not consider background object in image and the accessory which can not be use for styling."
            
            answer_data = self.model.query(image, question)
            
            # Flexible handling if the SDK returns a dict or direct string
            answer = answer_data['answer'] if isinstance(answer_data, dict) else answer_data
            
            # Parse comma-separated list
            items = [item.strip() for item in answer.split(',') if item.strip()]
            print(f"Identified Items: {items}")
            return items

        except Exception as e:
            logger.error(f"Error analyzing garment: {e}")
            return []

moondream_service = MoondreamService()
