import os
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from PIL import Image
from io import BytesIO
import time

def search_products(query, max_results=10):
    """
    Search for products using DuckDuckGo.
    """
    print(f"  Searching for: '{query}'...")
    results = []
    try:
        # DDGS instance
        with DDGS() as ddgs:
            # text() returns an iterable of dicts {title, href, body}
            ddg_gen = ddgs.text(query, max_results=max_results, region="us-en") 
            for r in ddg_gen:
                link = r['href']
                # Filter out junk domains
                skip_domains = ['apple.com', 'youtube.com', 'wikipedia.org', 'facebook.com', 'pinterest.com']
                if any(d in link for d in skip_domains):
                    continue
                results.append(r)
    except Exception as e:
        print(f"  [Search Error]: {e}")
    return results

def get_og_image(url):
    """
    Extracts the OpenGraph image URL from a web page.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.content, 'html.parser')
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
            
        # Fallback: find first large image? Risky. Stick to OG image for reliability.
        return None
    except Exception as e:
        return None

def verify_image_with_moondream(client, image_url, item_name, color, gender="women"):
    """
    Downloads image and uses Moondream to QUERY it.
    Returns: (Score (0-100), Reasoning/Description)
    """
    try:
        resp = requests.get(image_url, stream=True, timeout=5)
        if resp.status_code != 200:
            return 0, "Failed to download"
            
        image = Image.open(BytesIO(resp.content))
        
        # Construct specific prompt
        target_desc = f"{color} {item_name}"
        if gender == "women":
            target_desc = f"women's {target_desc}"
        elif gender == "men":
             target_desc = f"men's {target_desc}"
             
        question = f"Look at the main item in this image. Is it a {target_desc}? Answer YES or NO, then describe the item's color, style, and who is wearing it."
        
        # Query API
        answer = client.query(image, question)['answer']
        answer_lower = answer.lower()
        
        print(f"    [AI Analysis]: {answer[:100]}...")
        
        score = 0
        
        # 1. Primary Yes/No check
        if answer_lower.startswith("yes") or "yes," in answer_lower:
            score += 50
        
        # 2. Gender Check (if not already covered by Yes)
        # Sometimes it says "Yes, this is a women's..."
        gender_terms = ["woman", "women", "lady", "ladies", "female", "girl"]
        if gender == "men":
             gender_terms = ["man", "men", "male", "boy", "gentleman"]
             
        if any(t in answer_lower for t in gender_terms):
            score += 10
            
        # 3. Color Check
        if color.lower() in answer_lower:
            score += 20
            
        # 4. Item Keyword Check
        item_terms = [t.lower() for t in item_name.split()]
        matched = [t for t in item_terms if t in answer_lower]
        if len(matched) >= len(item_terms) / 2:
            score += 20
            
        return score, answer
        
    except Exception as e:
        print(f"  [Verification Error]: {e}")
        return 0, str(e)

def find_verified_product(client, item_name, color, gender="women"):
    """
    Main orchestration function.
    Finds Top 10 images, scores them all, returns the BEST match.
    """
    full_query = f"buy {color} {item_name} {gender}"
    print(f"  [Verifying]: Searching 10 images for '{full_query}'...")
    
    results = []
    # Retry logic for rate limits
    for attempt in range(2):
        try:
            time.sleep(2) # Initial cool-down
            with DDGS() as ddgs:
                results = list(ddgs.images(full_query, max_results=10, region="us-en"))
            break # Success
        except Exception as e:
            print(f"  [Search Error (Attempt {attempt+1})]: {e}")
            if "403" in str(e) or "Ratelimit" in str(e):
                print("  [Cooling down] Waiting 10 seconds...")
                time.sleep(10)
            else:
                break
    
    if not results:
        print("  No search results found.")
        return None
            
    print(f"  Found {len(results)} candidates. Scoring them...")
    
    scored_candidates = []
    
    for i, res in enumerate(results):
        img_url = res['image']
        page_url = res['url']
        title = res['title']
        
        # Skip junk domains
        skip_domains = ['youtube.com', 'facebook.com', 'wordpress.com']
        if any(d in page_url for d in skip_domains):
            continue

        print(f"    [{i+1}/10] Scoring: {title[:30]}...")
        
        score, reasoning = verify_image_with_moondream(client, img_url, item_name, color, gender)
        
        if score > 0:
            scored_candidates.append({
                "title": title,
                "url": page_url,
                "image_url": img_url,
                "score": score,
                "reasoning": reasoning
            })
            
        time.sleep(1) # Polite delay

    # Find the best
    if not scored_candidates:
        print("  No valid candidates found.")
        return None
        
    # Sort by Score DESC
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)
    best = scored_candidates[0]
    
    print(f"  [WINNER]: {best['title']} (Score: {best['score']})")
    print(f"  Reason: {best['reasoning'][:100]}...")
    
    # Threshold check? If best score is too low (< 50), maybe reject?
    if best['score'] < 50:
         print("  Winner score too low (<50). Rejecting.")
         return None
         
    return {
        "title": best['title'],
        "url": best['url'],
        "image_url": best['image_url'],
        "match_reason": f"Score {best['score']}/100. AI: {best['reasoning']}"
    }
