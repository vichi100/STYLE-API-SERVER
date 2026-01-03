import os
import json
import moondream as md
from PIL import Image
from dotenv import load_dotenv
try:
    from app.services.shopping_assistant import generate_shopping_links
except ImportError:
    # Fallback for when running directly as script
    from shopping_assistant import generate_shopping_links

# Load environment variables
load_dotenv()

WARDROBE_FILE = "wardrobe_analysis.json"
RULES_DIR = "rules_json"

def get_moondream_client():
    api_key = os.getenv("MOONDREAM_API_KEY")
    if not api_key:
        raise ValueError("MOONDREAM_API_KEY not found in .env")
    return md.vl(api_key=api_key)


def analyze_image_multi(client, image_path):
    """
    Uses Moondream to extract ALL clothing items from an image.
    Returns a list of dictionaries.
    """
    print(f"Analyzing {image_path}...")
    try:
        image = Image.open(image_path)
        
        # Prompt for structured detection
        prompt = (
            "Identify all clothing items in this image (e.g., shirts, pants, dresses, shoes). "
            "For each item, provide: Category (Must be one of: Top, Bottom, One-Piece, Shoe, Outerwear, Accessory), "
            "Color (Name), Hex (Approximate #RRGGBB), and Description (Brief style). "
            "Return the result as a strictly valid JSON list of objects. "
            "Example: [{'category': 'Top', 'color': 'White', 'hex': '#FFFFFF', 'description': 'Cotton t-shirt'}, ...]"
        )
        
        answer = client.query(image, prompt)['answer'].strip()
        
        # Cleanup markdown code blocks if present
        if answer.startswith("```json"):
            answer = answer.split("```json")[1].split("```")[0].strip()
        elif answer.startswith("```"):
            answer = answer.split("```")[1].split("```")[0].strip()
            
        try:
            items = json.loads(answer)
        except json.JSONDecodeError:
            print(f"  [Warn] Could not parse JSON for {image_path}. Raw: {answer[:50]}...")
            # Fallback: simple single item analysis if JSON fails
            # (Reusing the old simple logic idea but adapting to list)
            return []

        # Validate and normalize
        valid_items = []
        for item in items:
            if 'category' in item and 'color' in item:
                valid_items.append({
                    "filename": os.path.basename(image_path),
                    "path": os.path.abspath(image_path),
                    "category": item['category'],
                    "color": item['color'],
                    "hex": item.get('hex', '#000000'),
                    "style": item.get('description', '')
                })
        
        return valid_items

    except Exception as e:
        print(f"Error analysing {image_path}: {e}")
        return []

def scan_wardrobe(client, root_directory="wardrobe"):
    """
    Recursively scans directory for images and analyzes them.
    Checks cache first.
    """
    # Load cache if exists
    if os.path.exists(WARDROBE_FILE):
        with open(WARDROBE_FILE, 'r') as f:
            wardrobe_data = json.load(f)
    else:
        wardrobe_data = {}

    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
    
    # Walk through logical directories
    files_to_process = []
    
    if os.path.exists(root_directory):
        for root, dirs, files in os.walk(root_directory):
            for f in files:
                if os.path.splitext(f)[1].lower() in valid_exts:
                    files_to_process.append(os.path.join(root, f))
    else:
        # Fallback to current dir if wardrobe doesn't exist
        print(f"Directory {root_directory} not found, scanning current directory.")
        for f in os.listdir("."):
            if os.path.splitext(f)[1].lower() in valid_exts:
                if "debug_" not in f and "segmented_" not in f:
                    files_to_process.append(os.path.join(".", f))

    updates = False
    for file_path in files_to_process:
        abs_path = os.path.abspath(file_path)
        rel_key = os.path.relpath(abs_path, start=os.getcwd()) # Use relative path as key for readability
        
        if rel_key not in wardrobe_data:
            items = analyze_image_multi(client, abs_path)
            if items:
                wardrobe_data[rel_key] = items
                updates = True
        else:
            print(f"Skipping {rel_key} (cached)")
            
    if updates:
        with open(WARDROBE_FILE, 'w') as f:
            json.dump(wardrobe_data, f, indent=2)
            print(f"Updated {WARDROBE_FILE}")
            
    return wardrobe_data



# Valid hex code helper
def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

class ColorMatcher:
    def __init__(self, color_dict_path):
        with open(color_dict_path, 'r') as f:
            self.colors = json.load(f)
        # Pre-calculate RGBs for speed
        for i, c in enumerate(self.colors):
            c['param_id'] = i  # Store index as ID if not present
            if 'rgb' not in c and 'hex' in c:
                c['rgb'] = hex_to_rgb(c['hex'])

    def get_color_distance(self, rgb1, rgb2):
        # Simple Euclidean distance in RGB space
        # (Could use Lab for better accuracy but requires conversion lib)
        return sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)) ** 0.5

    def find_closest_color_id(self, hex_color):
        """Finds dictionary color closest to the input hex."""
        try:
            target_rgb = hex_to_rgb(hex_color)
            best_dist = float('inf')
            best_id = -1
            
            for i, c in enumerate(self.colors):
                if 'rgb' not in c: continue
                dist = self.get_color_distance(target_rgb, c['rgb'])
                if dist < best_dist:
                    best_dist = dist
                    best_id = i
            
            return best_id
        except:
            return -1

    def get_compatible_colors(self, color_id, tolerance=10):
        """Returns list of compatible color entries."""
        if color_id < 0 or color_id >= len(self.colors):
            return []
        
        source = self.colors[color_id]
        if 'combinations' not in source:
            return []
            
        # The 'combinations' array contains IDs (likely 1-based indices from the book)
        # We need to map them to our array indices (which are 0-based)
        # Checking logic: if max combination > length, assume IDs. If IDs are present?
        # Let's assume the json follows the book where ID = index + 1 or similar.
        # But 'combinations' usually refers to OTHER colors in the palette.
        
        matching_colors = []
        for combo_id in source['combinations']:
            # Handling potential 1-based indexing if standard
            # We'll try direct index first, if out of bounds, adjust.
            idx = combo_id - 1 # Assuming 1-based ID in the file
            if 0 <= idx < len(self.colors):
                matching_colors.append(self.colors[idx])
                
        return matching_colors

class OutfitRecommender:
    def __init__(self, rules_path):
        with open(rules_path, 'r') as f:
            self.rules = json.load(f)
            
    def suggest_outfits(self, wardrobe_items):
        suggestions = []
        # Basic heuristic: 
        # 1. Take an item from wardrobe
        # 2. Find a rule that mentions this item type
        # 3. Check if other components in rule exist in wardrobe
        
        # Flattener for simple "Dress Your Best" parsing
        # We will look at "women" -> "essentials" and "body_types"
        
        formulas = []
        # Extract all formulas from the JSON
        # (Simplified: just grabbing from one section for MVP)
        # In real world, we'd iterate recursively or ask user for body type.
        # Let's assume 'average_height' 'not_curvy' for a default logic or just grab ALL formulas.
        
        women_types = self.rules.get('women', {}).get('body_types', {})
        for btype in women_types.values():
            for height in btype.values():
                if isinstance(height, dict) and 'outfit_formulas' in height:
                     formulas.extend(height['outfit_formulas'])

        for note in wardrobe_items.values():
            item_cat = note['category'].lower()
            
            for formula in formulas:
                components = [c.lower() for c in formula['components']]
                # Check if item matches any component
                matched_component = None
                for c in components:
                    if item_cat in c or c in item_cat:
                        matched_component = c
                        break
                
                if matched_component:
                    # We found a formula that uses this item!
                    suggestions.append({
                        "base_item": note['filename'],
                        "formula_name": formula['formula_name'],
                        "components": formula['components'],
                        "missing": [c for c in components if c != matched_component] # Rough logic
                    })
                    

def recommend_office_outfits(all_items, color_matcher):
    """
    Generates 'Casual Office' recommendations by pairing Tops and Bottoms.
    """
    tops = [i for i in all_items if i['category'].lower() in ['top', 'shirt', 'blouse', 'jacket', 'outerwear']]
    bottoms = [i for i in all_items if i['category'].lower() in ['bottom', 'pants', 'jeans', 'skirt', 'shorts']]
    one_pieces = [i for i in all_items if i['category'].lower() in ['one-piece', 'dress']]

    print(f"Found {len(tops)} Tops, {len(bottoms)} Bottoms, {len(one_pieces)} One-Pieces.")

    combinations = []

    # 1. Top + Bottom Pairs
    for top in tops:
        for bottom in bottoms:
            score = 0
            reasons = []

            # A. Color Harmony
            # Check if top color and bottom color are compatible via dictionary
            t_cid = color_matcher.find_closest_color_id(top['hex'])
            b_cid = color_matcher.find_closest_color_id(bottom['hex'])
            
            is_compatible = False
            if t_cid != -1 and b_cid != -1:
                # Check if bottom color is in top's compatible list
                t_compat = color_matcher.get_compatible_colors(t_cid)
                # Check IDs
                # We need to map compat entries (which are dicts) back to IDs or check names
                # Ideally get_compatible_colors returns list of dicts.
                # Let's check name match for simplicity
                b_name = color_matcher.colors[b_cid]['name']
                if any(c['name'] == b_name for c in t_compat):
                    score += 5
                    reasons.append(f"Excellent color match ({top['color']} + {bottom['color']})")
                    is_compatible = True

            # B. Contrast (Light Top + Dark Bottom is classic office)
            # Rough hex luminance check
            def get_lum(hex_code):
                r, g, b = hex_to_rgb(hex_code)
                return (0.299*r + 0.587*g + 0.114*b)
            
            t_lum = get_lum(top['hex'])
            b_lum = get_lum(bottom['hex'])
            
            if abs(t_lum - b_lum) > 50:
                 score += 2
                 reasons.append("Good contrast")
            
            # C. Office Appropriateness (Heuristic)
            # Downrank shorts/leggings for office
            if 'short' in bottom['category'].lower() or 'legging' in bottom['category'].lower():
                score -= 10
                reasons.append("Too casual (Shorts/Leggings)")
            
            if 'skirt' in bottom['category'].lower() or 'pants' in bottom['category'].lower() or 'jeans' in bottom['category'].lower():
                score += 3
            
            combinations.append({
                "type": "Pair",
                "items": [top, bottom],
                "score": score,
                "reasons": reasons
            })

    # 2. One-Piece Outfits
    for op in one_pieces:
        score = 5 # Baseline for a dress
        if 'dress' in op['category'].lower():
            score += 2
        combinations.append({
            "type": "Single",
            "items": [op],
            "score": score,
            "reasons": ["Simple one-piece solution"]
        })

    # Sort and Display
    combinations.sort(key=lambda x: x['score'], reverse=True)

    print(f"\nTop 10 Recommended Casual Office Outfits:")
    for i, combo in enumerate(combinations[:10]):
        names = " + ".join([f"{item['color']} {item['category']}" for item in combo['items']])
        origin = ", ".join([os.path.basename(item['filename']) for item in combo['items']])
        print(f"#{i+1}: {names}")
        print(f"     Source: {origin}")
        print(f"     Score: {combo['score']} | Why: {', '.join(combo['reasons'])}")

def suggest_shopping_list(all_items, rules_mgr, color_matcher, client=None):
    """
    Analyzes all wardrobe items against all rules to find missing key pieces.
    Prioritizes items that work with MULTIPLE existing wardrobe items (Versatility).
    """
    # ... (rest of logic same until printing) ...
    # This replace_file_content is messy because I need to change signature AND usage.
    # It's better to verify carefully.
    # I should use multi_replace for signature + logic change, or just modify signature first.
    pass
    """
    Analyzes all wardrobe items against all rules to find missing key pieces.
    Prioritizes items that work with MULTIPLE existing wardrobe items (Versatility).
    """
    print("\n--- 5. Gap Analysis & Shopping List ---")
    
    # Structure: "Item Name" -> {
    #   'formulas': count, 
    #   'partners': { 'filename': item_obj }  <-- Use dict to track unique partners
    # }
    missing_data = {} 
    
    # 1. Flatten all formulas
    formulas = []
    women_types = rules_mgr.rules.get('women', {}).get('body_types', {})
    for btype in women_types.values():
        for height in btype.values():
            if isinstance(height, dict) and 'outfit_formulas' in height:
                 formulas.extend(height['outfit_formulas'])

    # 2. Check each item against formulas
    for item in all_items:
        item_cat = item['category'].lower()
        
        for formula in formulas:
            components = [c.lower() for c in formula['components']]
            
            # Does this formula require our item?
            matched_component = None
            for c in components:
                if item_cat in c or c in item_cat:
                    matched_component = c
                    break
            
            if matched_component:
                # Identify missing parts
                missing = [c for c in components if c != matched_component]
                for m in missing:
                    key = m.title() # Normalize
                    if key not in missing_data:
                         missing_data[key] = {'formulas': 0, 'partners': {}}
                    
                    missing_data[key]['formulas'] += 1
                    # Track unique partners
                    # We store the item obj to analyze colors later
                    missing_data[key]['partners'][item['filename']] = item

    # 3. Score and Sort
    # Score = (Unique Partners * 10) + (Total Formulas)
    # This prioritizes items that unlock outfits for MANY distinct clothes you own.
    scored_items = []
    for m_item, data in missing_data.items():
        unique_count = len(data['partners'])
        score = (unique_count * 10) + data['formulas']
        scored_items.append((m_item, data, score))
        
    scored_items.sort(key=lambda x: x[2], reverse=True)
    
    print(f"Top 10 Missing Items (Ranked by Versatility):")
    
    for i, (m_item, data, score) in enumerate(scored_items[:10]):
        unique_partners = list(data['partners'].values())
        
        # Color Analysis: Find "Common Denominator" colors
        # Which colors work with the MOST partners?
        color_votes = {} # ColorName -> Count
        
        for p_item in unique_partners:
            if 'hex' in p_item:
                cid = color_matcher.find_closest_color_id(p_item['hex'])
                if cid != -1:
                    compat = color_matcher.get_compatible_colors(cid)
                    for c in compat:
                        c_name = c['name']
                        color_votes[c_name] = color_votes.get(c_name, 0) + 1
        
        # Sort colors by how many partners they match
        sorted_colors = sorted(color_votes.items(), key=lambda x: x[1], reverse=True)
        top_colors = [c[0] for c in sorted_colors[:3]]
        
        # Format output
        suggested_colors_str = ", ".join(top_colors) if top_colors else "Neutral (Black/White/Tan)"
        
        # Generate Links
        # Use top 1 color for query if available
        color_for_link = [top_colors[0]] if top_colors else []
        links = generate_shopping_links(m_item, color_for_link)

        # Format "Pairs with" to show diversity
        # Show top 3 distinct partner categories/colors
        partner_summaries = [f"{p['color']} {p['category']}" for p in unique_partners[:3]]
        partner_str = ", ".join(partner_summaries)
        if len(unique_partners) > 3:
            partner_str += f", and {len(unique_partners) - 3} others"

        print(f"#{i+1}: {m_item}")
        print(f"     Versatility: High (Compatible with {len(unique_partners)} items in your wardrobe)")
        print(f"     Suggested Colors: {suggested_colors_str} (Matches the most items)")
        print(f"     Pairs well with your: {partner_str}")
        
        # Try verified shopping for top 3 items
        verified_match = None
        if client and i < 3: 
             try:
                 from verified_shopping import find_verified_product
                 # Use first suggested color or standard
                 v_color = top_colors[0] if top_colors else "black" 
                 print(f"     [Verifying]: Searching for the best visual match for '{v_color} {m_item}'...")
                 verified_match = find_verified_product(client, m_item, v_color)
             except Exception as e: 
                 print(f"     [Verification Failed]: {e}")

        if verified_match:
             print(f"     ★ Visual Match Verified: {verified_match['title']}")
             print(f"       Link: {verified_match['url']}")
             print(f"       Reason: {verified_match['match_reason']}")
             # HIDE generic links if verified match found to reduce clutter
             # print(f"     [More Options]: Google: {links['Google Shopping']} | Amzn: {links['Amazon']}")
        elif "★ Editor's Pick" in links:
             pick_link = links["★ Editor's Pick"]
             print(f"     {pick_link}")
             print(f"     [More Options]: Google: {links['Google Shopping']} | Amzn: {links['Amazon']}")
        else:
             print(f"     [Buy]: Google: {links['Google Shopping']} | Amzn: {links['Amazon']}")

def main():
    try:
        client = get_moondream_client()
        print("--- 1. Scanning Wardrobe ---")
        wardrobe = scan_wardrobe(client)
        print(f"Wardrobe items found: {sum(len(v) for v in wardrobe.values())}")
        
        if not wardrobe:
            print("Wardrobe is empty.")
            return

        # --- 2. Color Analysis ---
        print("\n--- 2. Color Analysis ---")
        color_db_path = os.path.join(RULES_DIR, "dictionary_of_colour_combinations.json")
        matcher = ColorMatcher(color_db_path)
        
        # Flatten wardrobe: list of all individual items
        all_items = []
        for file_key, items_list in wardrobe.items():
            for item in items_list:
                all_items.append(item)

        for item in all_items:
            if 'hex' in item:
                cid = matcher.find_closest_color_id(item['hex'])
                if cid != -1:
                    c_name = matcher.colors[cid]['name']
                    print(f"- [{item['category']}] {item['color']} (from {item['filename']}) matches '{c_name}'")
        
        # --- 3. Casual Office Recommendations ---
        print("\n--- 3. Casual Office Advisor ---")
        # Implement Office Logic locally or in class
        recommend_office_outfits(all_items, matcher)
        
        # --- 4. Gap Analysis ---
        # Reuse OutfitRecommender class just to load rules
        rules_path = os.path.join(RULES_DIR, "dress_your_best_the_complete_guide_to_finding_the_style_thats_right_for_your_body.json")
        recommender = OutfitRecommender(rules_path)
        
        suggest_shopping_list(all_items, recommender, matcher, client=client)
            
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
