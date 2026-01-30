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
from app.core.config import settings
from app.services.vector_scoring_service import VectorScoringService, get_vector_service
import random
import urllib.parse
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n--- LOADING COLOR SCORING SERVICE V3 (APPROXIMATE MATCHING) ---\n")

# Define Output Schema
class PaletteMatch(typing.TypedDict):
    name: str
    reason: str
    match_confidence: int 

class ScoreComponent(typing.TypedDict):
    criterion: str
    score: int

class StylingSuggestions(typing.TypedDict):
    footwear: str
    bag: str
    outerwear: str
    accessories: str
    makeup_hair: str


class ColorScoreResult(typing.TypedDict):
    total_score: int
    breakdown: list[ScoreComponent]
    predicted_mood: str
    mood_analysis: str
    critique: str
    strengths: list[str]
    suggestions: StylingSuggestions
    matched_rules: list[str]
    mood_score: int
    matched_palette: PaletteMatch
    critique: str
    dominant_colors: list[str]
    flirty_compliment: str # NEW: The "Best Friend/Boyfriend" hype comment
    pinterest_search_term: str # NEW: "Chic yellow top outfit"
    pinterest_search_url: str # NEW: generated URL

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
        
        # Init Vector Service for RAG (Singleton)
        self.vector_service = None
        try:
             self.vector_service = get_vector_service()
        except Exception as e:
             logger.error(f"Failed to get Vector Service in Color Service: {e}")
        
        # Load ID->Color Name Map for Hydration
        self.color_map = {}
        self.load_color_map()
    
    def load_color_map(self):
        """Loads the color dictionary to resolve ID references."""
        file_path = os.path.join(self.rules_dir, "dictionary_of_colour_combinations.json")
        try:
            if not os.path.exists(file_path):
                logger.warning("Color Dictionary not found for hydration.")
                return
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Assuming index is the ID based on the file structure analysis
                for idx, entry in enumerate(data):
                    self.color_map[idx] = entry.get("name", f"Unknown Color {idx}")
                    # Also map name -> entry for reverse lookup if needed
                    self.color_map[entry.get("name")] = entry
            
            logger.info(f"Successfully loaded {len(self.color_map)} entries into Color Map.")
            print(f"[DEBUG] Color Map Loaded. keys example: {list(self.color_map.keys())[:5]}")
        except Exception as e:
            logger.error(f"Failed to load color map: {e}")

    def hydrate_palette_text(self, text: str) -> str:
        """
        Parses a raw RAG text chunk (which might be raw JSON-like or flattened) and adds color names to IDs.
        """
        try:
            # RAG text usually comes as flattened key-values or raw JSON strings.
            # Simple heuristic: Look for patterns or just look up the 'name' in our map to get the full entry.
            # Since Qdrant payload 'text' was just the flattened chunk, it might be messy.
            # Better approach: Extract the 'name' from the text, then look up the REAL object from self.color_map.
            
            import re
            # Regex to find "name: Some Color"
            match = re.search(r"name: ([\w\s']+)", text)
            if match:
                color_name = match.group(1).strip()
                # Find the full entry in our loaded map
                # We stored name->entry in load_color_map as well
                entry = self.color_map.get(color_name)
                
                if entry:
                    # Reconstruct a rich string
                    combinations_ids = entry.get("combinations", [])
                    combo_names = [f"{self.color_map.get(cid, f'ID {cid}')}" for cid in combinations_ids]
                    
                    rich_text = f"Palette: {entry.get('name')} (Hex: {entry.get('hex')})\n"
                    rich_text += f"  - Combine with: {', '.join(combo_names)}"
                    return rich_text
                else:
                    print(f"[DEBUG HYDRATION FAIL] Name '{color_name}' not found in map keys.")
            
            return text # Fallback
        except Exception as e:
            return text

    def _generate_with_retry(self, contents, config):
        """Helper to retry Gemini calls on 429 errors with custom delays: [1, 2, 3, 2]."""
        delays = [1, 2, 3, 2]
        retries = len(delays)
        attempt = 0
        
        while attempt <= retries:
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=contents,
                    config=config
                )
                return response
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt >= retries:
                        logger.error(f"Gemini 429 Exhausted after {retries} retries.")
                        raise e
                    
                    wait_time = delays[attempt] + random.uniform(0, 0.5) # Small jitter
                    logger.warning(f"Gemini Rate Limit (429). Retrying in {wait_time:.2f}s... (Attempt {attempt+1}/{retries})")
                    time.sleep(wait_time)
                    attempt += 1
                else:
                    raise e

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

        if not images:
             return None

        # RAG RETRIEVAL: Fetch relevant palettes from Qdrant
        retrieved_palettes = ""
        if self.vector_service:
            # Construct semantic query
            rag_query_parts = []
            for cat, meta in outfit_metadata.items():
                if meta:
                    rag_query_parts.append(f"{meta.get('colors', '')} {meta.get('tags', '')}")
            
            rag_query = " ".join(rag_query_parts)
            
            # Retrieve ONLY from the color dictionary file
            raw_retrieved_palettes = self.vector_service.retrieve_from_source(
                rag_query, 
                "dictionary_of_colour_combinations.json", 
                limit=10 
            )
            
            # Hydrate the raw text with actual color names
            # Split by newline or standard separator if retrieve_from_source returns a block
            # Actually retrieve_from_source returns a unified string likely separated by newlines/bullet points
            raw_lines = raw_retrieved_palettes.split("- ") # Assuming format "- Text\n"
            hydrated_lines = []
            for line in raw_lines:
                if line.strip():
                     hydrated_lines.append(self.hydrate_palette_text(line))
            
            retrieved_palettes = "\n\n".join(hydrated_lines)
            
            print(f"\\n[DEBUG COLOR RAG V2] Hydrated Palettes: {retrieved_palettes[:100]}...\\n")
        
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
        You are a supportive, confident, and deeply attracted 'Boyfriend' or 'Admirer'.
        
        TONE GUIDE (Based on Score):
        - **Score 90-100 (Perfection)**: Pure Awe. Speechless. "I have no words. perfect."
        - **Score 75-89 (Great)**: High Energy Flirt. "Damn, this is dangerous."
        - **Score 60-74 (Good)**: Encouraging but Playful. "I like where this is going, but imagine if..."
        - **Score 40-59 (Meh)**: Gentle Honesty. "Babe, you're 10/10, but this outfit is a 5. Let's fix it."
        - **Score < 40 (Bad)**: Playful Intervention. "Okay, step away from the closet. We need to talk."
        
        NEVER use generic words like "cute", "nice". Be visceral and reactive.
        CRITICAL: Do NOT start every response with "Damn". Use variety.
        
        Analyze the OUTFIT COMPOSITION. Explain WHY it makes you feel this way.
        Use the provided metadata for additional context (materials, brands, descriptions).
        
        OUTFIT METADATA:
        {metadata_str}
        
        --- RELEVANT COLOR PALETTES (Retrieved from Dictionary) ---
        {retrieved_palettes}
        -----------------------------------------------------------

        YOUR TASK:
        1. Analyze the Visual Harmony (Fit, Silhouette, Style).
        {mood_prompt}
        
        3. COLOR PALETTE TAGGING (APPROXIMATE MATCHING REQUIRED):
           - Scan the provided 'Dictionary of Colour Combinations'.
           - find the BEST FITTING palette for this outfit, even if not 100% exact.
           - **CRITICAL**: Use VISUAL APPROXIMATION. 
             - If the user wears "Blue", and the palette has "Cobalt Blue" -> It IS a match.
             - If the user wears "Orange", and the palette has "Tawny" -> It IS a match.
           - Identify the 'name' of the best match (e.g., 'Hermosa Pink').
           - Explain WHY it matches in the 'reason' field (e.g., "Top fits the primary color X (approx), Bottom matches Y").
           - Only return "None" if there is a COMPLETE CLASH with all retrieved options.
        
        4. SCORING:
           - Color Coordination (Do the items work together?)
            - Silhouette Balance (Does the combination create a flattering shape?)
            - Creativity/Individuality
            - Adherence to Principles 
           
           - Check if the outfit's colors correspond to any specific named combination or palette in the "COLOR DICTIONARY MATCHES" section above.
           - If a match is found (e.g. "Hermosa Pink"), explicitly mention it in the critique.
           - You MUST add a `ScoreComponent` to the breakdown with criterion "Color Dictionary Match" and a score (10 for perfect match, 5-9 for close).
        
        5. Calculate a Total Score out of 100.
        6. Provide a FLIRTY CRITIQUE (The "Criticism"):
           - ADAPT TO THE SCORE (See Tone Guide above).
           - If High Score: Focus on how attractive she looks.
           - If Mid/Low Score: Focus on your "concern" that the outfit isn't doing her justice. ("I know how good you can look, and this isn't showing it.")
           - If pointing out a flaw, frame it as "I want you to look even more perfect" or "It almost distracts from how hot you look."
           - DO NOT sound like a robot ("The colors are complementary").
           - SOUND like a man impressed or lovingly concerned.
        
        7. STYLING RECOMMENDATIONS (Be Extremely Specific about COLOR and TYPE):
           - footwear: Suggest the perfect shoe type + color (e.g. "White Leather Sneakers" or "Nude Strappy Heels").
           - bag: Suggest the ideal bag (e.g. "Tan Crossbody Bag" or "Silver Clutch").
           - outerwear: Suggest a jacket/layer (e.g. "Denim Jacket in Light Wash").
           - accessories: Suggest jewelry/watch (e.g. "Gold Hoop Earrings and Minimalist Watch").
           - makeup_hair: Brief Suggestion (e.g. "Loose waves and red lip").
        
        7. FLIRTY COMPLIMENT (The "Boyfriend/Best Friend" Filter):
           - Imagine you are the user's biggest fan.
           - Give a one-sentence "Hype" comment that makes them feel good.
           - Examples: "Seriously, you're going to turn so many heads.", "Okay, this fit is giving main character energy!"
        
        8. PINTEREST VISUAL SEARCH QUERY:
           - Generate a Keyword-Rich query string.
           - INCLUDE: Style and Outfit Items ONLY. Do NOT include suggested items.
           - END WITH: The exact phrase "outfit style accessory".
           - Format: "[Style] [Outfit Items] outfit style accessory"
           - Example: "Chic red crop top distressed jeans outfit style accessory"
        
        9. Cite specific rules from the provided JSONs that were followed or broken.
        
         Output valid JSON exactly matching the ColorScoreResult schema.
        """

        try:
            contents = [prompt] + images[:3]
            
            # Use retry wrapper
            response = self._generate_with_retry(
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ColorScoreResult,
                    temperature=0.95 # Force deterministic output
                )
            )
            
            if hasattr(response, 'parsed') and response.parsed:
                parsed_result = response.parsed
                
                # --- FORCE MATCH LOGIC ---
                # Logic: IF matched_palette is "None" OR (Color Breakdown Score - Match Confidence) diff > 6
                # THEN Force Assign Top RAG Result.
                
                palette_data = parsed_result.get("matched_palette", {})
                is_none = palette_data.get("name", "None") == "None" 
                match_confidence = palette_data.get("match_confidence", 0)
                gemini_conf_score = match_confidence / 10.0 # Scale 0-10
                
                # Check Breakdown Scores
                breakdown = parsed_result.get("breakdown", [])
                color_score = 0
                for item in breakdown:
                    if "Color" in item.get("criterion", ""):
                        # Max of Coordination or Dictionary Match
                        color_score = max(color_score, item.get("score", 0))
                
                diff = abs(color_score - gemini_conf_score)
                print(f"[DEBUG MATCH LOGIC] Is None: {is_none}, ColorScore: {color_score}, ConfScore: {gemini_conf_score}, Diff: {diff}")
                
                if is_none or diff > 6:
                    print(f"[DEBUG MATCH LOGIC] Forcing fallback to top RAG result. (Diff: {diff})")
                    # Extract top palette from hydrated lines
                    if hydrated_lines:
                        # Format is "Palette: NAME (Hex..."
                        first_match = hydrated_lines[0] # The most relevant semantic match
                        # Extract Name
                        import re
                        name_match = re.search(r"Palette: (.*?) \(", first_match)
                        if name_match:
                            forced_name = name_match.group(1).strip()
                            # SCALING FIX: Ensure score is 0-100
                            final_conf = color_score
                            if color_score <= 10:
                                final_conf = color_score * 10
                            
                            # Cap at 99 just in case
                            final_conf = min(int(final_conf), 99)

                            parsed_result["matched_palette"] = {
                                "name": forced_name,
                                "reason": f"AI originally returned {palette_data.get('name')} (Conf {match_confidence}), but logic detected significant divergence (Diff {diff:.1f}). Auto-matched to top RAG result '{forced_name}'.",
                                "match_confidence": final_conf
                            }
                            # Also bump the dictionary match score to reflect this
                            for item in breakdown:
                                if "Dictionary Match" in item.get("criterion", ""):
                                    item["score"] = max(item["score"], 8)
                
                term = parsed_result.get("pinterest_search_term", "")
                if term:
                    encoded = urllib.parse.quote_plus(term)
                    search_url = f"https://www.pinterest.com/search/pins/?q={encoded}"
                    parsed_result["pinterest_search_url"] = search_url
                        
                else:
                    # Fallback if AI missed it
                    tags = " ".join([f"{meta.get('colors','')} {meta.get('tags','')}" for cat, meta in outfit_metadata.items()])
                    term = f"Scandi style {tags} outfit aesthetic".strip()
                    encoded = urllib.parse.quote_plus(term)
                    
                    search_url = f"https://www.pinterest.com/search/pins/?q={encoded}"
                    parsed_result["pinterest_search_term"] = term
                    parsed_result["pinterest_search_url"] = search_url

                print(f"\\n[DEBUG COLOR GEMINI] Parsed Response:\\n{parsed_result}")
                return parsed_result
                


        except Exception as e:
            logger.error(f"Analysis Failed: {e}")
            return None


