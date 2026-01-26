import os
import sys
import glob
from PIL import Image
import io
import logging
import typing_extensions as typing
import json

# Ensure we can import from 'app' when running directly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from google import genai
from google.genai import types
from app.core.config import settings
import logging
import typing_extensions as typing
from app.services.vector_scoring_service import VectorScoringService, get_vector_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Output Schema
class ScoreComponent(typing.TypedDict):
    criterion: str
    score: int

class StyleScore(typing.TypedDict):
    total_score: int
    breakdown: list[ScoreComponent]
    predicted_mood: str
    mood_analysis: str
    critique: str
    strengths: list[str]
    improvements: list[str]
    matched_rules: list[str]

class StyleScoringService:
    def __init__(self, rules_dir: str = "rules_json"):
        self.api_key = settings.GOOGLE_API_KEY
        self.rules_dir = rules_dir
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to init Gemini client: {e}")
        
        # Init Vector Service for RAG (Use Singleton)
        self.vector_service = None
        try:
             self.vector_service = get_vector_service()
             # self.vector_service.initialize() # Initialization handled by main.py
        except Exception as e:
             logger.error(f"Failed to get Vector Service in Style Service: {e}")

    def load_rules(self) -> str:
        """
        Loads all JSON files from the rules directory and combines them into a single context string.
        """
        rules_context = ""
        json_files = glob.glob(os.path.join(self.rules_dir, "*.json"))
        
        if not json_files:
            logger.warning(f"No JSON rules found in {self.rules_dir}")
            return "No specific style rules provided. Use general fashion knowledge."

        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    filename = os.path.basename(file_path)
                    rules_context += f"\n--- Rules from {filename} ---\n"
                    rules_context += json.dumps(data, indent=2)
            except Exception as e:
                logger.error(f"Error reading rule file {file_path}: {e}")
        
        return rules_context

    def analyze_image(self, image_path: str = None, image_data: bytes = None, target_mood: str = None) -> StyleScore:
        if not self.client:
            logger.error("Gemini client not initialized.")
            return None

        # Load Image
        try:
            if image_data:
                img = Image.open(io.BytesIO(image_data))
            elif image_path:
                img = Image.open(image_path)
            else:
                raise ValueError("No image provided")
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None

        # Load Rules
        rules_context = self.load_rules()

        # Construct Mood Instruction
        if target_mood:
             mood_instruction = f"""
             2. Mood / Occasion Analysis:
                - The user tried to dress for the following occasion: "{target_mood}".
                - DETECT the actual mood communicated by the outfit.
                - COMPARE the detected mood with the target mood "{target_mood}".
                - CRITICAL RULE: If the outfit DOES NOT MATCH the target occasion (e.g. wearing gym clothes to a formal party), the Total Score MUST BE BELOW 40, REGARDLESS of how good the colors or fit are.
                - If the mismatch is partial (e.g. slightly too casual for office), cap the score at 60.
                - In 'mood_analysis', be very specific about why it fails the occasion check.
             """
        else:
             mood_instruction = """
             2. Detect the Mood / Occasion:
                - Identify the most suitable occasion for this outfit (e.g., Party, Office/Meeting, Casual/Shopping, Lunch Date, Gym/Active, Evening Gala, etc.).
                - Provide a brief reasoning for the detected mood.
             """

        # Construct Prompt
        prompt = f"""
        You are a highly critical and knowledgeable fashion stylist and judge.
        Analyze the person's outfit in the image based strictly on the Fashion Rules provided below.
        
        YOUR TASK:
        1. Identify the outfit components.
        {mood_instruction}
        3. Evaluate the outfit against the provided rules (Color combinations, Logic, Fit, Occasion, Balance, etc.).
        4. Assign a score out of 10 for:
            - Color Coordination
            - Fit & Silhouette
            - Creativity/Individuality
            - Adherence to Principles (Quality, Grooming, etc.)
        5. Calculate a Total Score out of 100.
        6. Provide a constructive critique.
        7. List strengths and improvements.
        8. Cite specific rules from the provided JSONs that were followed or broken.

        --- FASHION RULES ---
        {rules_context}
        ---------------------
        
        Output valid JSON exactly matching the StyleScore schema.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, img],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StyleScore
                )
            )
            
            if hasattr(response, 'parsed') and response.parsed:
                print(f"\\n[DEBUG GEMINI] Parsed Response:\\n{response.parsed}")
                return response.parsed
            
            print(f"\\n[DEBUG GEMINI] Raw Text:\\n{response.text}")
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Style Analysis Failed: {e}")
            return None

    def analyze_outfit(self, outfit_images: dict[str, bytes], outfit_metadata: dict[str, dict], target_mood: str = None, use_rag: bool = False) -> StyleScore:
        """
        Analyzes a composition of items (Top, Bottom, Layer, etc.).
        outfit_images: dict of {category: image_bytes}
        outfit_metadata: dict of {category: item_metadata_dict}
        use_rag: If True, uses Vector Search to retrieve specific rules. If False, uses loose context.
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
            logger.error(f"Error loading outfit images: {e}")
            return None

        if not images:
             logger.error("No valid images provided for outfit analysis.")
             return None

        # Load Rules
        rules_context = self.load_rules()
        
        # Format Metadata Context
        metadata_str = json.dumps(outfit_metadata, indent=2)

        # Construct Mood Instruction
        if target_mood:
             mood_instruction = f"""
             2. Mood / Occasion Analysis:
                - The user tried to dress for the following occasion: "{target_mood}".
                - DETECT the actual mood communicated by the combined outfit.
                - COMPARE the detected mood with the target mood "{target_mood}".
                - CRITICAL RULE: If the outfit DOES NOT MATCH the target occasion (e.g. wearing gym clothes to a formal party), the Total Score MUST BE BELOW 40, REGARDLESS of how good the colors or fit are.
                - If the mismatch is partial (e.g. slightly too casual for office), cap the score at 60.
                - In 'mood_analysis', be very specific about why it fails the occasion check.
             """
        else:
             mood_instruction = """
             2. Detect the Mood / Occasion:
                - Identify the most suitable occasion for this outfit combination.
                - Provide a brief reasoning for the detected mood.
             """

        # RAG RETRIEVAL STEP
        retrieved_rules = ""
        retrieved_color_rules = ""
        
        if use_rag and self.vector_service:
            # Construct semantic query from metadata
            rag_query_parts = []
            for cat, meta in outfit_metadata.items():
                if meta:
                    rag_query_parts.append(f"{meta.get('custom_category', '')} {meta.get('tags', '')} {meta.get('colors', '')}")
            
            rag_query = " ".join(rag_query_parts)
            # Retrieve top 5 most relevant general rules
            retrieved_rules = self.vector_service.retrieve_relevant_rules(rag_query, limit=5)
            
            # Retrieve SPECIFIC Color Dictionary Matches
            retrieved_color_rules = self.vector_service.retrieve_from_source(
                rag_query, 
                "dictionary_of_colour_combinations.json", 
                limit=3
            )
            print(f"\\n[DEBUG RAG] General Context: {retrieved_rules[:50]}...")
            print(f"[DEBUG RAG] Color Dictionary Context: {retrieved_color_rules[:50]}...\\n")
        
        else:
            print(f"\\n[DEBUG RAG] RAG Retrieval Skipped (use_rag={use_rag})\\n")

        # Construct Prompt
        prompt = f"""
        You are a highly critical and knowledgeable fashion stylist and judge.
        Analyze the OUTFIT COMPOSITION shown in the provided images (e.g., Top, Bottom, Layer).
        Use the provided metadata for additional context (materials, brands, descriptions).
        
        OUTFIT METADATA:
        {metadata_str}

        YOUR TASK:
        1. Identify the visual harmony between the provided items.
        {mood_instruction}
        3. Evaluate the outfit against the provided rules and specifically the RETRIEVED RULES below.
        
        CRITICAL COLOR/STYLE CHECK (RAG):
        Review the following SPECIFIC rules retrieved from our style database that match this outfit.
        If the outfit follows or breaks these specific rules, cite them explicitly.
        
        --- RETRIEVED RELEVANT RULES ---
        # {retrieved_rules}
        
        --- COLOR DICTIONARY MATCHES (High Priority) ---
        {retrieved_color_rules}
        --------------------------------
        
        CRITICAL COLOR STEP:
        - Check if the outfit's colors correspond to any specific named combination or palette in the "COLOR DICTIONARY MATCHES" section above.
        - If a match is found (e.g. "Hermosa Pink"), explicitly mention it in the critique.
        - You MUST add a `ScoreComponent` to the breakdown with criterion "Color Dictionary Match" and a score (10 for perfect match, 5-9 for close).
        
        4. Assign a score out of 10 for:
            - Color Coordination (Do the items work together?)
            - Silhouette Balance (Does the combination create a flattering shape?)
            - Creativity/Individuality
            - Adherence to Principles 
        5. Calculate a Total Score out of 100.
        6. Provide a constructive critique.
        7. List strengths and improvements.
        8. Cite specific rules from the provided JSONs that were followed or broken.

        --- FASHION RULES ---
        {rules_context}
        ---------------------
        
        Output valid JSON exactly matching the StyleScore schema.
        """

        try:
            # Pass prompt + list of images
            contents = [prompt] + images
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StyleScore
                )
            )
            
            if hasattr(response, 'parsed') and response.parsed:
                print(f"\\n[DEBUG GEMINI] Parsed Response:\\n{response.parsed}")
                return response.parsed
            
            print(f"\\n[DEBUG GEMINI] Raw Text:\\n{response.text}")
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Outfit Analysis Failed: {e}")
            return None

# Command Line Interface for testing
if __name__ == "__main__":
    import argparse
    import sys
    
    # Ensure app directory is in python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(current_dir))
    sys.path.append(parent_dir)

    parser = argparse.ArgumentParser(description="Score an outfit based on style rules.")
    parser.add_argument("image_path", help="Path to the image file")
    parser.add_argument("--mood", help="Target mood/occasion (e.g., 'Party', 'Office')", default=None)
    args = parser.parse_args()

    service = StyleScoringService(rules_dir="rules_json") # Assumes run from root or rules_json exists
    
    # Adjust rules_dir if running from a different location, or rely on absolute path if needed.
    # For this CLI, assuming running from project root.
    if not os.path.exists(service.rules_dir):
         # Try absolute path based on this file
         service.rules_dir = os.path.join(parent_dir, "rules_json")

    print(f"Analyzing {args.image_path} with mood: {args.mood if args.mood else 'Auto-Detect'}...")
    result = service.analyze_image(image_path=args.image_path, target_mood=args.mood)
    
    if result:
        print("\n--- Style Score Analysis ---")
        print(json.dumps(result, indent=2))
    else:
        print("Analysis Failed.")
