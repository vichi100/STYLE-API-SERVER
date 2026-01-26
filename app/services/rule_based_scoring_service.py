import os
import json
import glob
import logging
import typing_extensions as typing
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Re-use schema or define similar
class ScoreComponent(typing.TypedDict):
    criterion: str
    score: int
    reason: str

class RuleBasedScore(typing.TypedDict):
    total_score: int
    breakdown: List[ScoreComponent]
    matched_formulas: List[str]
    critique: str
    strengths: List[str]
    improvements: List[str]

class RuleBasedScoringService:
    def __init__(self, rules_dir: str = "rules_json"):
        self.rules_dir = rules_dir
        self.rules_cache = {}
        self.load_rules()

    def load_rules(self):
        """
        Loads useful JSON rules into memory.
        """
        json_files = glob.glob(os.path.join(self.rules_dir, "*.json"))
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    filename = os.path.basename(file_path)
                    self.rules_cache[filename] = data
            except Exception as e:
                logger.error(f"Error reading rule file {file_path}: {e}")

    def normalize_string(self, s: str) -> str:
        return s.lower().strip().replace("-", " ")

    def check_outfit_formulas(self, items: Dict[str, dict]) -> (int, List[str]):
        """
        Checks if the outfit matches any known formulas.
        Returns (score_boost, matched_formulas).
        """
        score = 0
        matches = []
        
        # Flatten current outfit items into a set of descriptors
        current_outfit_descriptors = set()
        for cat, item in items.items():
            if not item: continue
            
            # Add category descriptors
            if item.get("custom_category"):
                current_outfit_descriptors.add(self.normalize_string(item["custom_category"]))
            if item.get("specific_category"):
                current_outfit_descriptors.add(self.normalize_string(item["specific_category"]))
            if item.get("general_category"):
                current_outfit_descriptors.add(self.normalize_string(item["general_category"]))
            
            # Add tags?
            # if item.get("tags"):
            #     for tag in item["tags"].split(","):
            #         current_outfit_descriptors.add(self.normalize_string(tag))

        # Check against 'the_curated_closet.json' formulas
        curated_closet = self.rules_cache.get("the_curated_closet.json", {})
        formulas = curated_closet.get("wardrobe_construction", {}).get("outfit_formulas", [])
        
        # Check against 'the_little_dictionary_of_fashion.json'
        dior_rules = self.rules_cache.get("the_little_dictionary_of_fashion.json", {})
        formulas.extend(dior_rules.get("styling_logic", {}).get("outfit_formulas", []))

        for formula in formulas:
            formula_name = formula.get("formula_name")
            components = formula.get("components", []) # List[str] e.g. ["jeans", "T-shirt", "cardigan"]
            
            # Simple Component Matching
            # Check how many components are present in current outfit
            matched_count = 0
            for comp in components:
                # Descriptor match
                norm_comp = self.normalize_string(comp)
                # Check for partial match (e.g. "jeans" in "high-waisted jeans")
                if any(norm_comp in d or d in norm_comp for d in current_outfit_descriptors):
                    matched_count += 1
            
            # If we matched a significant portion of the formula (e.g. > 50%)
            if matched_count >= len(components) - 1 and len(components) > 1:
                 matches.append(f"Matched '{formula_name}' ({matched_count}/{len(components)} items)")
                 score += 20 # Big boost for matching a classic formula

        return min(score, 30), matches # Cap formula boost

    def check_color_harmony(self, items: Dict[str, dict]) -> (int, str):
        """
        Basic color harmony check.
        Returns (score, reason).
        """
        colors_present = []
        for cat, item in items.items():
            if item and item.get("colors"):
                # Handle list or comma string
                c_data = item["colors"]
                if isinstance(c_data, list):
                    colors_present.extend([c.lower() for c in c_data])
                elif isinstance(c_data, str):
                    colors_present.extend([c.strip().lower() for c in c_data.split(",")])

        unique_colors = set(colors_present)
        count = len(unique_colors)
        
        if count == 0:
            return 5, "No color data available."
        
        if count == 1:
            return 9, "Monochromatic look detected. Chic and streamlined."
        
        if count == 2:
            return 8, "Two-tone palette. Balanced and safe."
        
        if count == 3:
            return 7, "Three colors. Standard rule of three compliance."
            
        if count > 4:
            return 4, "More than 4 distinct colors detected. Risk of looking cluttered."

        # Bonus: Check for neutrals
        neutrals = {"white", "black", "grey", "gray", "navy", "beige", "cream", "denim", "blue"} # Blue is often neutral
        neutral_count = sum(1 for c in unique_colors if any(n in c for n in neutrals))
        
        if neutral_count >= 1:
            return 8, f"{count} colors with supporting neutrals. Good balance."
            
        return 6, "Multiple colors without obvious neutrals."

    def check_mood_appropriateness(self, items: Dict[str, dict], target_mood: str) -> (int, str):
        """
        Evaluates if items match the target mood based on weighted semantic attributes.
        Returns (score, reason).
        """
        if not target_mood:
            return 0, ""

        target = self.normalize_string(target_mood)
        
        # 1. Define Mood Weights (The "Semantic" Knowledge Base)
        # Maps keywords to their affinity with specific moods (-1.0 to 1.0)
        # 1.0 = Perfect Match, -1.0 = Complete Clash, 0 = Neutral
        keyword_weights = {
            # Fabrics / Textures
            "sequin": {"party": 1.0, "casual": -0.8, "office": -0.5, "gym": -1.0},
            "silk": {"party": 0.7, "office": 0.6, "date": 0.8, "casual": -0.2, "gym": -0.8},
            "satin": {"party": 0.8, "date": 0.8, "office": 0.4, "casual": -0.3},
            "velvet": {"party": 0.8, "date": 0.7, "casual": 0.2, "summer": -0.5},
            "cotton": {"casual": 0.8, "office": 0.4, "party": -0.3, "gym": 0.5},
            "denim": {"casual": 0.9, "office": -0.4, "party": -0.2, "date": 0.3, "gym": -0.6},
            "leather": {"party": 0.7, "date": 0.7, "casual": 0.5, "office": -0.2},
            "spandex": {"gym": 1.0, "casual": 0.4, "party": -0.8, "office": -0.9},
            "nylon": {"gym": 0.9, "casual": 0.6},
            "linen": {"casual": 0.8, "summer": 1.0, "office": 0.3, "party": -0.2},
            
            # Categories / Items
            "gown": {"party": 1.0, "formal": 1.0, "casual": -1.0, "office": -0.8},
            "dress": {"party": 0.6, "date": 0.8, "office": 0.5, "casual": 0.4},
            "t shirt": {"casual": 0.9, "gym": 0.6, "office": -0.7, "party": -0.6},
            "blazer": {"office": 1.0, "party": 0.4, "date": 0.5, "casual": -0.3},
            "suit": {"office": 1.0, "formal": 1.0, "party": 0.3, "casual": -0.9},
            "hoodie": {"casual": 0.9, "gym": 0.7, "office": -0.9, "party": -0.8, "date": -0.6},
            "sweatpants": {"casual": 1.0, "gym": 0.8, "office": -1.0, "party": -1.0, "date": -0.9},
            "jeans": {"casual": 0.9, "date": 0.4, "party": 0.2, "office": -0.4},
            "leggings": {"gym": 1.0, "casual": 0.7, "office": -0.8, "party": -0.7},
            "heels": {"party": 0.9, "date": 0.9, "office": 0.6, "casual": -0.4, "gym": -1.0},
            "sneakers": {"casual": 0.9, "gym": 0.9, "office": -0.6, "party": -0.5, "date": -0.3},
            "boots": {"casual": 0.7, "date": 0.6, "office": 0.4, "party": 0.4},
            "loafers": {"office": 0.8, "casual": 0.5, "date": 0.4, "party": -0.2},
            
            # Attributes
            "formal": {"party": 0.5, "office": 0.9},
            "casual": {"casual": 1.0, "office": -0.5},
            "embellished": {"party": 0.9, "date": 0.6, "office": -0.3},
            "fitted": {"date": 0.8, "party": 0.6, "gym": 0.4},
            "oversized": {"casual": 0.8, "gym": 0.3, "office": -0.6, "date": -0.4},
            "tailored": {"office": 0.9, "party": 0.5, "date": 0.6},
            "athletic": {"gym": 1.0, "casual": 0.5}
        }

        # 2. Extract Outfit Tokens
        outfit_tokens = set()
        for cat, item in items.items():
            if not item: continue
            
            # Normalize and split fields
            fields = [item.get("custom_category"), item.get("specific_category"), item.get("general_category")]
            if item.get("tags"):
                 fields.append(str(item["tags"]))
            
            for f in fields:
                if f:
                    # Clean punctuation
                    text = self.normalize_string(f).replace(",", " ")
                    outfit_tokens.update(text.split())

        # 3. Calculate Vector Score
        total_affinity = 0.0
        relevant_tokens_count = 0
        hits = []
        clashes = []

        for token in outfit_tokens:
            if token in keyword_weights:
                weights = keyword_weights[token]
                
                # Check direct match
                if target in weights:
                    affinity = weights[target]
                    total_affinity += affinity
                    relevant_tokens_count += 1
                    
                    if affinity > 0.4:
                        hits.append(token)
                    elif affinity < -0.4:
                        clashes.append(token)
                
                # Handle fuzzy mood mapping (e.g. "Clubbing" -> "Party")
                # Simple fallback for now: exact match required or use synonyms
                # You could add a mood_alias dict here.

        # 4. Normalize and Interpret
        final_score = 5 # Neutral start
        reason = f"Outfit is consistent with '{target_mood}'."

        if relevant_tokens_count > 0:
            avg_affinity = total_affinity / relevant_tokens_count
            # Scale -1.0...1.0 to 1...10
            # -1 -> 1, 0 -> 5.5, 1 -> 10
            # score = 5.5 + (4.5 * avg)
            final_score = 5.5 + (4.5 * avg_affinity)
            final_score = max(1, min(10, int(final_score)))
            
            if final_score >= 8:
                reason = f"Excellent fit for '{target_mood}'. Matches: {', '.join(hits[:3])}."
            elif final_score <= 3:
                reason = f"Clashes with '{target_mood}'. Problem items: {', '.join(clashes[:3])}."
            elif final_score < 6:
                reason = f"Slightly inappropriate for '{target_mood}'. Found: {', '.join(clashes[:2])}."
            else:
                 reason = f"Acceptable for '{target_mood}'."
        else:
            reason = f"Neutral. No specific '{target_mood}' attributes found."
            final_score = 5

        return final_score, reason

    def score_outfit(self, top: dict, bottom: dict, layer: dict = None, mood: str = None) -> RuleBasedScore:
        items = {"top": top, "bottom": bottom, "layer": layer}
        
        total_score = 0
        breakdown = []
        strengths = []
        improvements = []
        
        # 1. Completeness Check
        if not top or not bottom:
             return {
                 "total_score": 0,
                 "breakdown": [],
                 "critique": "Incomplete outfit. Missing Top or Bottom.",
                 "matched_formulas": [],
                 "strengths": [],
                 "improvements": ["Add a top and bottom to evaluate."]
             }

        # 2. Formula Matching (Max 30)
        formula_score, matched_formulas = self.check_outfit_formulas(items)
        formula_score = max(5, formula_score) # Base score
        breakdown.append({"criterion": "Outfit Structure", "score": min(10, int(formula_score/3)), "reason": f"Matches: {len(matched_formulas)} formulas"})
        total_score += formula_score
        
        if matched_formulas:
            strengths.append(f"Follows established style formulas: {', '.join(matched_formulas)}")
        else:
            improvements.append("Try following classic outfit formulas (e.g. Jeans + T-shirt + Layer) for guaranteed cohesion.")

        # 3. Color Harmony (Max 30)
        color_score, color_reason = self.check_color_harmony(items)
        breakdown.append({"criterion": "Color Harmony", "score": color_score, "reason": color_reason})
        total_score += (color_score * 3) # Weight it to 30
        
        if color_score >= 8:
            strengths.append(color_reason)
        elif color_score <= 5:
            improvements.append(color_reason)

        # 4. Item Balance / Logic (Max 40)
        # E.g. Top 't-shirt' matches Bottom 'jeans' -> Casual + Casual = Good
        # Top 'blouse' matches Bottom 'trousers' -> Formal + Formal = Good
        logic_score = 5 # Start neutral
        logic_reason = "Standard combination."
        
        top_cat = self.normalize_string(top.get("custom_category", ""))
        bot_cat = self.normalize_string(bottom.get("custom_category", ""))
        
        # Simple logical blocks
        casual_tops = ["t shirt", "tank", "hoodie", "sweatshirt"]
        casual_bots = ["jeans", "shorts", "leggings", "joggers"]
        
        formal_tops = ["blouse", "shirt", "button down"]
        formal_bots = ["trousers", "skirt"] # Skirt can be both but defaulting logic
        
        is_top_casual = any(c in top_cat for c in casual_tops)
        is_bot_casual = any(c in bot_cat for c in casual_bots)
        
        if is_top_casual and is_bot_casual:
            logic_score = 9
            logic_reason = "Consistent Casual Vibe."
        elif not is_top_casual and not is_bot_casual:
             logic_score = 9
             logic_reason = "Consistent Formal/Smart Vibe."
        else:
            # High-Low mix (can be good!)
            logic_score = 7
            logic_reason = "Mix of Casual and Formal items (High-Low style)."
            
        breakdown.append({"criterion": "Style Logic", "score": logic_score, "reason": logic_reason})
        total_score += (logic_score * 4) # Weight to 40

        # Critique Initialization (Before Mood Check)
        critique = f"{logic_reason} {color_reason}"
        if formula_score > 10:
             critique += " Adheres well to classic fashion formulas."

        # 5. Mood Check (Max 20 - Bonus/Penalty)
        if mood:
             mood_score, mood_reason = self.check_mood_appropriateness(items, mood)
             if mood_score > 0:
                  breakdown.append({"criterion": "Mood Appropriateness", "score": mood_score, "reason": mood_reason})
                  
                  # Re-calculate Total
                  # Formula: score/30 * 25
                  w_formula = (formula_score / 30) * 25
                  w_color   = (color_score / 10) * 25
                  w_logic   = (logic_score / 10) * 30
                  w_mood    = (mood_score / 10) * 20
                  
                  total_score = int(w_formula + w_color + w_logic + w_mood)
                  if mood_reason:
                       critique += f" {mood_reason}"

        # Final Tally
        final_total = min(100, total_score)
        
        return {
            "total_score": final_total,
            "breakdown": breakdown,
            "matched_formulas": matched_formulas,
            "critique": critique,
            "strengths": strengths,
            "improvements": improvements
        }
