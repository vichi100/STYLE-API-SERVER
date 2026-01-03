import urllib.parse
import json
import os

# Load curated picks if available
CURATED_FILE = os.path.join(os.path.dirname(__file__), "curated_products.json")
CURATED_DB = {}
if os.path.exists(CURATED_FILE):
    try:
        with open(CURATED_FILE, 'r') as f:
            CURATED_DB = json.load(f)
    except:
        pass

def generate_shopping_links(item_name, color_list=None, gender="women"):
    """
    Generates search URLs for Google Shopping, Amazon, and Pinterest.
    Checks for Curated "Editor's Picks" first to provide specific item links.
    """
    links = {}
    
    # 1. Check Curated DB
    # We strip " (Work)" or " (Weekend)" annotations if present in naming
    base_name = item_name
    
    if base_name in CURATED_DB:
        pick = CURATED_DB[base_name]
        links["★ Editor's Pick"] = f"{pick['name']}: {pick['url']}"
    
    # 2. Generate Generic Search Links
    if not color_list:
        query = f"{item_name} {gender}".strip()
    else:
        primary_color = color_list[0] if isinstance(color_list, list) and color_list else ""
        query = f"{primary_color} {item_name} {gender}".strip()

    encoded_query = urllib.parse.quote(query)
    
    links["Google Shopping"] = f"https://www.google.com/search?tbm=shop&q={encoded_query}"
    links["Amazon"] = f"https://www.amazon.com/s?k={encoded_query}"
    
    return links

