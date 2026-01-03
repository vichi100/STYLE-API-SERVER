import requests
from PIL import Image
import io

def create_test_image():
    # Simple test image
    img = Image.new('RGB', (200, 200), color='white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def test_yolov8_segmentation():
    url = "http://localhost:8000/api/v1/images/remove-background"
    print(f"Testing YOLOv8 segmentation at {url}...")
    
    img_buf = create_test_image()
    files = {'file': ('test.jpg', img_buf, 'image/jpeg')}
    
    try:
        response = requests.post(url, files=files, timeout=300)
        
        if response.status_code == 200:
            print("Success! Image processed.")
            # Verify output
            out_img = Image.open(io.BytesIO(response.content))
            print(f"Output size: {out_img.size}")
            print(f"Output mode: {out_img.mode}")
            out_img.save("test_clothing_seg.png")
            print("Saved test_clothing_seg.png")
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_yolov8_segmentation()
