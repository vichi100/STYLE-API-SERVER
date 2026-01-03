import requests
from PIL import Image, ImageDraw
import io

def create_test_image():
    # Create a red square with a blue circle
    img = Image.new('RGB', (200, 200), color='red')
    d = ImageDraw.Draw(img)
    d.ellipse((50, 50, 150, 150), fill='blue')
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def test_remove_background():
    url = "http://localhost:8000/api/v1/images/remove-background"
    
    img_buf = create_test_image()
    files = {'file': ('test.jpg', img_buf, 'image/jpeg')}
    
    try:
        response = requests.post(url, files=files)
        
        if response.status_code == 200:
            print("Success! Image processed.")
            
            # Verify it's an image
            out_img = Image.open(io.BytesIO(response.content))
            print(f"Output image size: {out_img.size}")
            print(f"Output image mode: {out_img.mode}")
            
            # Check if it has alpha channel
            if 'A' in out_img.mode:
                print("Output has alpha channel (transparency).")
            else:
                print("WARNING: Output does NOT have alpha channel.")
                
            out_img.save("processed_test_image.png")
            print("Saved processed_test_image.png")
            
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("Connection failed. Is the server running?")

if __name__ == "__main__":
    test_remove_background()
