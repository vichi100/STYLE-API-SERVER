import sys
import os
import logging

# Mock Setup
logging.basicConfig(level=logging.INFO)

# Add app to path
sys.path.append(os.getcwd())

from app.services.color_scoring_service import ColorScoringService

def test_hydration():
    print("--- Starting Hydration Test ---")
    
    # Init service (will skip Gemini/Qdrant if keys missing, but that's fine for this test)
    # We only care about load_color_map and hydrate_palette_text
    service = ColorScoringService()
    
    # Check map
    print(f"Map Size: {len(service.color_map)}")
    if "Hermosa Pink" in service.color_map:
        print("Hermosa Pink found in map.")
    else:
        print("Hermosa Pink NOT found in map.")
        
    # Test Cases
    inputs = [
        "0: name: Hermosa Pink",
        "- 14: name: Vinaceous Tawny",
        "name: Cobalt Blue",
        "Just some random text",
        "5: combinations: 0: 176"
    ]
    
    for text in inputs:
        print(f"\nInput: '{text}'")
        result = service.hydrate_palette_text(text)
        print(f"Output: '{result[:50]}...'") # Truncate for readability
        if "Combine with" in result:
             print(">> SUCCESS: Hydrated")
        else:
             print(">> FAILED: Not Hydrated")

if __name__ == "__main__":
    test_hydration()
