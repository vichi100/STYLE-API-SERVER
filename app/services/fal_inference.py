import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import fal_client
import io
import base64
from PIL import Image

# Ensure FAL_KEY is set
# export FAL_KEY="your-key-here"

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return f.read()

def main():
    print("Starting Fal.ai IDM-VTON Inference...")
    
    # 1. Upload Images
    # Fal.ai requires URLs. We can use their storage API or any public URL.
    # Here we use fal_client.upload assuming the client supports local file upload helper.
    # If not, we might need to base64 encode or host them.
    
    person_path = "redshorts.png"
    cloth_path = "clean_dress.png"
    
    print(f"Uploading {person_path}...")
    person_url = fal_client.upload_file(person_path)
    print(f"Person URL: {person_url}")
    
    print(f"Uploading {cloth_path}...")
    cloth_url = fal_client.upload_file(cloth_path)
    print(f"Cloth URL: {cloth_url}")

    # 2. Setup Arguments
    # Using the IDM-VTON endpoint on Fal.ai
    # Endpoint ID: "fashn/model/v1/a/idm-vton"  <-- Verify current endpoint ID
    # or "fal-ai/idm-vton"
    
    # Endpoint from user screenshot
    endpoint = "fal-ai/image-apps-v2/virtual-try-on" 
    
    arguments = {
        "person_image_url": person_url,
        "clothing_image_url": cloth_url,
        "garment_category": "dress",
        "preserve_pose": True
    }
    
    print(f"Sending request to {endpoint}...")
    handler = fal_client.submit(
        endpoint,
        arguments=arguments,
    )
    
    # 3. Get Result
    result = handler.get()
    print("Result received!")
    
    if "images" in result and len(result["images"]) > 0:
        image_url = result["images"][0]["url"]
        print(f"Output Image URL: {image_url}")
        
        # Download and save
        import requests
        response = requests.get(image_url)
        with open("fal_result.png", "wb") as f:
            f.write(response.content)
        print("Saved to fal_result.png")
    elif "image" in result: # Fallback for other endpoints
        image_url = result["image"]["url"]
        print(f"Output Image URL: {image_url}")
        
        # Download and save
        import requests
        response = requests.get(image_url)
        with open("fal_result.png", "wb") as f:
            f.write(response.content)
        print("Saved to fal_result.png")
    else:
        print("No image in result:")
        print(result)

if __name__ == "__main__":
    if "FAL_KEY" not in os.environ:
        print("❌ Error: FAL_KEY environment variable not set.")
        print("Please export FAL_KEY='your_api_key'")
    else:
        main()
