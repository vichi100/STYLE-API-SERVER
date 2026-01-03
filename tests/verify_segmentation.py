import requests
from PIL import Image
import io

def create_test_image():
    # Simple test image: Red dress-like shape on white background
    img = Image.new('RGB', (512, 512), color='white')
    # Draw something? For now simple color.
    return img

def test_segmentation():
    url = "http://localhost:8000/api/v1/images/remove-background"
    print(f"Testing Segmentation Service at {url}...")
    
    img = create_test_image()
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    
    files = {'file': ('test.jpg', buf, 'image/jpeg')}
    
    try:
        response = requests.post(url, files=files, timeout=300)
        
        if response.status_code == 200:
            print("Success! Image processed.")
            # Verify output
            out_img = Image.open(io.BytesIO(response.content))
            print(f"Output size: {out_img.size}")
            print(f"Output mode: {out_img.mode}")
            out_img.save("processed_output.png")
            print("Saved processed_output.png (Note: May be garbage if model weights are missing)")
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_segmentation()
