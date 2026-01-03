import io
import torch
import numpy as np
import cv2
import os
from PIL import Image
from torchvision import transforms
from torchvision.models.segmentation import deeplabv3_resnet50
from ultralytics import YOLO
from typing import Optional

class ClothingSegmenter:
    """
    Hybrid Segmentation Pipeline:
    1. YOLOv8-Seg: Removes general background (Room, clutter).
    2. DeepLabV3+: Performs pixel-perfect clothing segmentation on the cleaned image.
    """

    def __init__(
        self,
        deeplab_path: str,
        yolo_path: str = "yolov8n-seg.pt",
        device: Optional[str] = None
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # --- Load YOLOv8 (Stage 1) ---
        print(f"Loading YOLOv8 model: {yolo_path}")
        self.yolo = YOLO(yolo_path)

        # --- Load DeepLabV3+ (Stage 2) ---
        # Assuming 5 classes: 0=bg, 1=dress, 2=top, 3=pants, 4=outerwear
        self.deeplab = deeplabv3_resnet50(num_classes=5)
        
        if os.path.exists(deeplab_path):
            try:
                self.deeplab.load_state_dict(
                    torch.load(deeplab_path, map_location=self.device)
                )
                print(f"Loaded DeepLabV3+ model from {deeplab_path}")
            except Exception as e:
                print(f"Failed to load DeepLab weights: {e}")
        else:
            print(f"WARNING: DeepLab model not found at {deeplab_path}. Stage 2 will produce noise.")

        self.deeplab.to(self.device)
        self.deeplab.eval()

        self.transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])
        
        # Clothing Classes for DeepLab (Keep these, drop background)
        self.cloth_class_ids = [1, 2, 3, 4]

    def segment(self, image_bytes: bytes) -> bytes:
        """
        Runs the 2-step pipeline.
        """
        # Decode original
        original_image = self._load_image_cv2(image_bytes) # OpenCV (BGR)
        
        # --- STAGE 1: YOLO Background Removal ---
        cleaned_image_bgr = self._run_yolo_cleanup(original_image)
        
        # --- STAGE 2: DeepLab Semantic Segmentation ---
        # Convert BGR (OpenCV) -> RGB (PIL) for Torch
        cleaned_image_rgb = cv2.cvtColor(cleaned_image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(cleaned_image_rgb)
        
        final_mask = self._run_deeplab(pil_image, original_size=original_image.shape[:2][::-1])
        
        # --- Final Composition ---
        # Apply Detailed Mask to the YOLO-Cleaned Image (or Original? User said "on image")
        # Usually we apply it to the original, but since DeepLab saw the Cleaned one, 
        # let's apply the mask to the Original for best color fidelity, 
        # ensuring the mask is the intersection of both logic implicitly.
        
        rgba = self._apply_alpha(original_image, final_mask)
        return self._encode_png(rgba)

    # ---------------- INTERNALS ----------------

    def _load_image_cv2(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image input")
        return img

    def _run_yolo_cleanup(self, image: np.ndarray) -> np.ndarray:
        """
        Uses YOLO to find "Person" or "Main Object" and black out the rest.
        """
        results = self.yolo(image, verbose=False)[0]
        
        if results.masks is None:
            # If nothing detected, return original (DeepLab might find something)
            # or return black? Let's return original to be safe.
            return image

        # Strategy: Keep Person (Class 0) or Largest Object
        masks = results.masks.data.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()
        names = self.yolo.names

        h, w = image.shape[:2]
        
        # 1. Look for Person
        person_indices = [i for i, c in enumerate(classes) if names[int(c)] == "person"]
        
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        
        if person_indices:
            # Merge all person masks
            for i in person_indices:
                m = cv2.resize(masks[i], (w, h))
                combined_mask |= (m > 0.5).astype(np.uint8)
        else:
            # No person? Keep everything that was detected (Context: hanger, dress, etc.)
            # Or just largest? Let's keeping "all detected objects" to show to DeepLab.
            for i, _ in enumerate(masks):
                m = cv2.resize(masks[i], (w, h))
                combined_mask |= (m > 0.5).astype(np.uint8)

        # Apply YOLO mask to image (Black out background)
        # 255 if Mask, 0 if Background
        combined_mask = combined_mask * 255
        
        # Result: Object on Black Background
        cleaned = cv2.bitwise_and(image, image, mask=combined_mask)
        return cleaned

    @torch.no_grad()
    def _run_deeplab(self, image: Image.Image, original_size: tuple) -> np.ndarray:
        """
        Runs DeepLabV3+ on the image and returns a uint8 mask (0 or 255).
        """
        orig_w, orig_h = original_size
        
        input_tensor = self.transform(image).unsqueeze(0).to(self.device)
        output = self.deeplab(input_tensor)["out"][0]
        
        # Argmax
        pred = torch.argmax(output, dim=0).cpu().numpy()
        
        # Filter for Cloth Classes
        mask = np.zeros_like(pred, dtype=np.uint8)
        for cid in self.cloth_class_ids:
            mask[pred == cid] = 255
            
        # Resize to original
        mask = cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        return mask

    def _apply_alpha(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        bgra = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = mask
        return bgra

    def _encode_png(self, bgra: np.ndarray) -> bytes:
        success, buffer = cv2.imencode(".png", bgra)
        if not success:
            raise RuntimeError("PNG encoding failed")
        return buffer.tobytes()

# Global Instance
clothing_segmenter = ClothingSegmenter(
    deeplab_path="app/models/deeplabv3_fashion.pth",
    yolo_path="yolov8n-seg.pt"
)
