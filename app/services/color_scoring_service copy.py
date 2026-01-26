import os
import sys
import glob
from PIL import Image
import io
import logging
import typing_extensions as typing
import json
from google import genai
from google.genai import types
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Output Schema
class PaletteMatch(typing.TypedDict):
    name: str
    match_confidence: int 

class ScoreComponent(typing.TypedDict):
    criterion: str
    score: int



class ColorScoreResult(typing.TypedDict):
    total_score: int
    breakdown: list[ScoreComponent]
    predicted_mood: str
    mood_analysis: str
    critique: str
    strengths: list[str]
    improvements: list[str]
    matched_rules: list[str]
    mood_score: int
    matched_palette: PaletteMatch
    critique: str
    dominant_colors: list[str]

class ColorScoringService:
    def __init__(self, rules_dir: str = "rules_json"):
        self.api_key = settings.GOOGLE_API_KEY
        self.rules_dir = rules_dir
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to init Gemini client: {e}")

    def load_color_dictionary(self) -> str:
        """
        Loads specifically the dictionary_of_colour_combinations.json.
        """
        file_path = os.path.join(self.rules_dir, "dictionary_of_colour_combinations.json")
        try:
            if not os.path.exists(file_path):
                return "Error: Color Dictionary file not found."
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                return json.dumps(data)
                
        except Exception as e:
            logger.error(f"Error reading color dictionary: {e}")
            return "Error loading color dictionary."

    def analyze_outfit_with_palette(self, outfit_images: dict[str, bytes], outfit_metadata: dict[str, dict], target_mood: str = None) -> ColorScoreResult:
        """
        Analyzes the outfit using Gemini's general knowledge + Specific Color Dictionary.
        Includes Mood Analysis.
        """
        if not self.client:
            logger.error("Gemini client not initialized.")
            return None

        # Load Images
        images = []
        try:
            for cat, data in outfit_images.items():
                if data:
                    img = Image.open(io.BytesIO(data))
                    images.append(img)
        except Exception as e:
            logger.error(f"Error loading images: {e}")
            return None

        if not images:
             return None

        # Load ONLY the Color Dictionary
        color_dictionary_json = self.load_color_dictionary()
        
        metadata_str = json.dumps(outfit_metadata, indent=2)

        mood_prompt = ""
        if target_mood:
            mood_prompt = f"""
             2. Mood / Occasion Analysis:
                - The user tried to dress for the following occasion: "{target_mood}".
                - DETECT the actual mood communicated by the combined outfit.
                - COMPARE the detected mood with the target mood "{target_mood}".
                - CRITICAL RULE: If the outfit DOES NOT MATCH the target occasion (e.g. wearing gym clothes to a formal party), the Total Score MUST BE BELOW 40, REGARDLESS of how good the colors or fit are.
                - If the mismatch is partial (e.g. slightly too casual for office), cap the score at 60.
                - In 'mood_analysis', be very specific about why it fails the occasion check.
             """
        else:
            mood_prompt = """
             2. Detect the Mood / Occasion:
                - Identify the most suitable occasion for this outfit combination.
                - Provide a brief reasoning for the detected mood.
             """

        prompt = f"""
        You are a highly critical and knowledgeable fashion stylist and judge.
        Analyze the OUTFIT COMPOSITION shown in the provided images (e.g., Top, Bottom, Layer).
        Use the provided metadata for additional context (materials, brands, descriptions).
        
        OUTFIT METADATA:
        {metadata_str}
        
        --- DICTIONARY OF COLOUR COMBINATIONS (Reference) ---
        {color_dictionary_json}
        -----------------------------------------------------

        YOUR TASK:
        1. Analyze the Visual Harmony (Fit, Silhouette, Style).
        {mood_prompt}
        
        3. COLOR PALETTE TAGGING:
           - Scan the provided 'Dictionary of Colour Combinations'.
           - Does this outfit's color scheme match a specific named palette?
           - If yes, identify the 'name' (e.g., 'Hermosa Pink').
           - If no exact match, find the closest one or return "None".
        
        4. SCORING:
           - Color Coordination (Do the items work together?)
            - Silhouette Balance (Does the combination create a flattering shape?)
            - Creativity/Individuality
            - Adherence to Principles 

         - Check if the outfit's colors correspond to any specific named combination or palette in the "COLOR DICTIONARY MATCHES" section above.
        - If a match is found (e.g. "Hermosa Pink"), explicitly mention it in the critique.
        - You MUST add a `ScoreComponent` to the breakdown with criterion "Color Dictionary Match" and a score (10 for perfect match, 5-9 for close).
        
        5. Calculate a Total Score out of 100.
        6. Provide a constructive critique.
        7. List strengths and improvements.
        8. Cite specific rules from the provided JSONs that were followed or broken.
        
         Output valid JSON exactly matching the ColorScoreResult schema.
        """

        try:
            contents = [prompt] + images[:3]
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ColorScoreResult
                )
            )
            
            if hasattr(response, 'parsed') and response.parsed:
                print(f"\\n[DEBUG COLOR GEMINI] Parsed Response:\\n{response.parsed}")
                return response.parsed
            
            print(f"\\n[DEBUG COLOR GEMINI] Raw Text:\\n{response.text}")
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Analysis Failed: {e}")
            return None
