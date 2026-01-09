from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation
from PIL import Image
import torch.nn as nn
import torch
import numpy as np

# 1. Load the Model (Runs locally, no API cost)
processor = SegformerImageProcessor.from_pretrained("mattmdjaga/segformer_b2_clothes")
model = AutoModelForSemanticSegmentation.from_pretrained("mattmdjaga/segformer_b2_clothes")

def segment_clothing(image_path):
    image = Image.open(image_path).convert("RGB")
    
    # 2. Run Inference
    inputs = processor(images=image, return_tensors="pt")
    outputs = model(**inputs)
    logits = outputs.logits.cpu()

    # Upscale logits to original image size
    upsampled_logits = nn.functional.interpolate(
        logits,
        size=image.size[::-1],
        mode="bilinear",
        align_corners=False,
    )

    # Get the label for every pixel (0-17)
    pred_seg = upsampled_logits.argmax(dim=1)[0]
    
    # 3. Define "What to Keep"
    # These are the IDs for clothing items in this specific model:
    # 4: Upper-clothes, 5: Skirt, 6: Pants, 7: Dress, 8: Belt, 9/10: Shoes, 16: Bag, 17: Scarf
    CLOTHING_LABELS = [4, 5, 6, 7, 8, 9, 10, 16, 17]

    # Create a mask: True if pixel is clothing, False if Hand/Hanger/Background
    mask = np.isin(pred_seg.numpy(), CLOTHING_LABELS)

    # 4. Apply Mask (Cut out the clothes)
    image_rgba = image.convert("RGBA")
    data = np.array(image_rgba)
    
    # Set Alpha to 0 (Transparent) wherever the mask is False
    data[~mask, 3] = 0 
    
    result = Image.fromarray(data)
    result.save("clean_outfit.png")
    print("Saved clean outfit. Hands and hangers are gone.")

# Run it
if __name__ == "__main__":
    segment_clothing("IMG_2907.jpg")