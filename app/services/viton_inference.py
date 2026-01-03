from __future__ import annotations

from typing import Optional

import modal
import os
import time

# Define the volume where weights are stored
vol = modal.Volume.from_name("idm-vton-weights", create_if_missing=False)

# Define the image with necessary dependencies
# IDM-VTON requires diffusers, accelerate, transformers, etc.
image = (
    modal.Image.debian_slim()
    .apt_install(
        "git",
        "libgl1",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender1",
    )
    .pip_install(
        "diffusers==0.25.1",
        "transformers==4.38.1",
        "accelerate==0.27.2",
        "huggingface_hub<0.22.0", # Required for cached_download in older diffusers
        "torch",
        "numpy<2",
        "Pillow",
        "opencv-python-headless",
        "protobuf<5",
        "einops",
        "omegaconf",
        "torchvision",
        "controlnet_aux==0.0.7",
        "mediapipe==0.10.14",
        "onnxruntime",
        "rembg"
    )
)

app = modal.App("idm-vton-inference")

@app.cls(
    gpu="A10G",
    volumes={"/weights": vol},
    image=image,
    timeout=600,
    max_containers=1,
)
class Model:
    @modal.enter()
    def build(self):
        import sys
        import os
        import torch
        import shutil
        from huggingface_hub import snapshot_download
        from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

        # 1. Setup IDM-VTON Codebase
        repo_url = "https://github.com/yisol/IDM-VTON"
        local_repo_path = "/root/IDM-VTON"
        
        if not os.path.exists(local_repo_path):
            print(f"Cloning {repo_url}...")
            # We use subprocess because git clone is easiest
            import subprocess
            subprocess.run(["git", "clone", repo_url, local_repo_path], check=True)
        
        # Add to path to import src
        sys.path.append(local_repo_path)
        
        # 2. Import Custom Classes
        # IDM-VTON has custom UNet and Pipeline in its src folder
        try:
            from src.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline
            from src.unet_hacked_tryon import UNet2DConditionModel
            from src.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
        except ImportError as e:
            print(f"Failed to import custom IDM-VTON classes: {e}")
            raise e

        print("Loading IDM-VTON pipeline with custom UNet...")
        self.device = "cuda"
        self.torch_dtype = torch.float16
        
        base_path = "/weights"
        
        # 3. Load UNet with Custom Class
        # The config has 'ip_image_proj' which fails standard UNet, but works with UNet2DConditionModel from unet_hacked_tryon
        unet = UNet2DConditionModel.from_pretrained(
            base_path,
            subfolder="unet",
            torch_dtype=self.torch_dtype
        ).to(self.device)

        # 3.1 Load UNet Encoder (GarmentNet) with Custom Class
        # This is required for IDM-VTON but not in standard model_index
        try:
             unet_encoder = UNet2DConditionModel_ref.from_pretrained(
                base_path,
                subfolder="unet_encoder", 
                torch_dtype=self.torch_dtype
             ).to(self.device)
        except Exception as e:
             print(f"Failed to load UNet Encoder: {e}")
             # Fallback: maybe it's in a different path or needs different loading?
             # For now, let's assume standard structure.
             raise e
        
        # 3.2 Load Feature Extractor (Image Processor)
        try:
             image_processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-large-patch14")
        except Exception as e:
             print(f"Failed to load standard CLIPImageProcessor: {e}")
             raise e

        # 3.3 Load Pose Detector
        # IDM-VTON training/inference commonly uses a DensePose-style map.
        # We prefer DensePose if available, otherwise fall back to OpenPose, otherwise dummy.
        self.densepose = None
        self.openpose = None
        try:
            from controlnet_aux import DenseposeDetector

            self.densepose = DenseposeDetector.from_pretrained("lllyasviel/ControlNet")
            if torch.cuda.is_available() and hasattr(self.densepose, "to"):
                self.densepose.to("cuda")
            print("✅ DensePose detector loaded.")
        except Exception as e:
            print(f"WARNING: DensePose unavailable ({type(e).__name__}: {e}).")

        if self.densepose is None:
            # NOTE: `controlnet_aux` imports optional detectors (incl. mediapipe) at import time.
            # If mediapipe/native deps are missing, we fall back to dummy pose.
            try:
                from controlnet_aux import OpenposeDetector

                self.openpose = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
                if torch.cuda.is_available() and hasattr(self.openpose, "to"):
                    self.openpose.to("cuda")
                print("✅ OpenPose detector loaded.")
            except Exception as e:
                self.openpose = None
                print(f"WARNING: OpenPose unavailable ({type(e).__name__}: {e}). Will use dummy pose.")

        # ... (image encoder loading code) ...
        # Load Image Encoder manually (since it failed to load automatically)
        try:
             image_encoder = CLIPVisionModelWithProjection.from_pretrained(
                 "/weights/image_encoder",
                 torch_dtype=self.torch_dtype
             ).to(self.device)
        except Exception as e:
             print(f"Failed to load Image Encoder: {e}")
             raise e

        # We assume the volume has the full diffusers structure
        self.pipe = TryonPipeline.from_pretrained(
            base_path,
            unet=unet,
            unet_encoder=unet_encoder, # Inject manual unet_encoder
            feature_extractor=image_processor, 
            image_encoder=image_encoder, # Inject manual image encoder
            torch_dtype=self.torch_dtype,
            use_safetensors=True,
        ).to(self.device)
        
        print("✅ IDM-VTON Custom Pipeline loaded successfully.")

    @modal.method()
    def try_on(
        self,
        person_image_bytes,
        cloth_image_bytes,
        person_mask_bytes=None,
        prompt=None,
        cloth_prompt: Optional[str] = None,
        denoise_steps=30,
        strength: float = 1.0,
        guidance_scale: float = 10.0,
        pose_mode: str = "auto",
        debug: bool = False,
        seed=42,
    ):
        import io
        import torch
        import numpy as np
        import cv2
        from PIL import Image

        print(
            f"Starting IDM-VTON Inference. Steps={denoise_steps}, Strength={strength}, Guidance={guidance_scale}, PoseMode={pose_mode}, Seed={seed}"
        )
        
        # 1. Load Images
        person_img = Image.open(io.BytesIO(person_image_bytes)).convert("RGB")
        cloth_img = Image.open(io.BytesIO(cloth_image_bytes)).convert("RGB")
        
        # Resize/Standardize input (IDM-VTON often likes 768x1024 or similar)
        # Using 768x1024 as commonly used in VTON-HD / IDM-VTON
        target_size = (768, 1024)
        person_img = person_img.resize(target_size, Image.Resampling.LANCZOS)
        cloth_img = cloth_img.resize(target_size, Image.Resampling.LANCZOS)

        # 2. Prepare Inpainting Mask (person-side)
        # IMPORTANT: The mask controls *where the person image is repainted*.
        # A full-image mask often changes the identity/background ("different person").
        if person_mask_bytes:
            mask = Image.open(io.BytesIO(person_mask_bytes)).convert("L").resize(
                target_size, Image.Resampling.NEAREST
            )
        else:
            print("No person mask provided; auto-generating a body mask (excluding head).")

            # Use rembg to get a foreground (person) mask, then carve out a torso band.
            # This keeps face/background mostly intact while allowing clothing changes.
            from rembg import remove

            # rembg can return a binary mask image when only_mask=True
            # (returns bytes of a PNG-like mask).
            fg_mask_out = remove(person_img, only_mask=True)
            if isinstance(fg_mask_out, Image.Image):
                fg_mask = fg_mask_out.convert("L")
            else:
                fg_mask = Image.open(io.BytesIO(fg_mask_out)).convert("L")

            fg_mask = fg_mask.resize(target_size, Image.Resampling.NEAREST)

            fg = np.array(fg_mask)

            # Heuristic: if rembg returns an (almost) full-white mask, it's likely inverted (background=white).
            # Invert so that foreground/person is white.
            white_ratio = float((fg > 0).mean()) if fg.size else 0.0
            if white_ratio > 0.90:
                fg = 255 - fg

            ys, xs = np.where(fg > 0)
            if len(xs) == 0 or len(ys) == 0:
                # Fallback: big center band (most of body)
                w, h = target_size
                x0, x1 = int(w * 0.15), int(w * 0.85)
                y0, y1 = int(h * 0.18), int(h * 0.92)
                band_arr = np.zeros((h, w), dtype=np.uint8)
                band_arr[y0:y1, x0:x1] = 255
                mask = Image.fromarray(band_arr, mode="L")
            else:
                x0, x1 = int(xs.min()), int(xs.max())
                y0, y1 = int(ys.min()), int(ys.max())
                box_h = max(1, y1 - y0)

                # Expand bbox a bit horizontally to cover loose garments
                h, w = fg.shape
                pad_x = int((x1 - x0) * 0.08)
                x0p = max(0, x0 - pad_x)
                x1p = min(w - 1, x1 + pad_x)

                # Inpaint most of the body, but keep the head/upper hair intact.
                # This makes the change visible while preserving identity.
                cut_head_y = y0 + int(box_h * 0.18)
                cut_bottom_y = y0 + int(box_h * 0.95)

                keep = np.zeros((h, w), dtype=np.uint8)
                keep[max(0, cut_head_y) : min(h, cut_bottom_y), x0p : x1p] = 255

                # Intersect with foreground
                inpaint = np.minimum(keep, (fg > 0).astype(np.uint8) * 255)

                # Slight dilation to cover edges
                kernel = np.ones((9, 9), np.uint8)
                inpaint = cv2.dilate(inpaint, kernel, iterations=1)

                # Clamp pathological cases (empty or almost full-frame)
                inpaint_ratio = float((inpaint > 0).mean()) if inpaint.size else 0.0
                if inpaint_ratio < 0.01 or inpaint_ratio > 0.60:
                    w, h = target_size
                    band_arr = np.zeros((h, w), dtype=np.uint8)
                    band_arr[int(h * 0.18) : int(h * 0.92), int(w * 0.15) : int(w * 0.85)] = 255
                    inpaint = band_arr

                mask = Image.fromarray(inpaint, mode="L")
            
        # 3. Pose Image (Required by IDM-VTON custom pipeline)
        # Prefer DensePose-style maps if available; otherwise OpenPose; otherwise dummy.
        from torchvision import transforms
        
        pose_mode_norm = (pose_mode or "auto").strip().lower()
        if pose_mode_norm not in {"auto", "densepose", "openpose", "none"}:
            pose_mode_norm = "auto"

        pose_img = None
        if pose_mode_norm in {"auto", "densepose"} and self.densepose is not None:
            try:
                pose_img = self.densepose(person_img)
                pose_img = pose_img.resize(target_size, Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"DensePose failed: {e}.")

        if pose_img is None and pose_mode_norm in {"auto", "openpose"} and self.openpose is not None:
            try:
                pose_img = self.openpose(person_img, include_body=True, include_hand=True, include_face=True)
                pose_img = pose_img.resize(target_size, Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"OpenPose failed: {e}.")

        if pose_img is None:
            pose_img = Image.new("RGB", person_img.size, (0, 0, 0))

        # Define Transforms
        # Tensor transform for standard images
        tf_image = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
        ])
        
        # Preprocess pose into Tensor
        # IDM-VTON pipeline encodes the pose image using the adapter/VAE.
        # We must pass the HIGH-RES tensor, matching the input image tensor shape.
        pose_tensor = tf_image(pose_img).unsqueeze(0).to(self.device, dtype=self.torch_dtype)
        
        # Preprocess cloth into Tensor (Required for 'cloth' arg which goes to VAE)
        # Cloth goes to VAE, so it stays High-Res
        cloth_tensor = tf_image(cloth_img).unsqueeze(0).to(self.device, dtype=self.torch_dtype)

        # 5. Run Pipeline
        if not prompt:
            prompt = "a photo of a person wearing the dress from the reference image"

        neg_prompt = (
            "monochrome, lowres, bad anatomy, worst quality, low quality, "
            "different person, different face, different background"
        )
        
        # Generate text embeddings for cloth (required by unet_encoder)
        # The unet_encoder needs full prompt embeddings (not pooled) for the garment
        if not cloth_prompt:
            cloth_prompt = "a photo of a dress"
        (
            prompt_embeds_cloth,
            _,
            _,
            _,
        ) = self.pipe.encode_prompt(
            prompt=cloth_prompt,
            device=self.device,
            num_images_per_prompt=1,
            do_classifier_free_guidance=False,
        )
        
        generator = torch.Generator(device=self.device).manual_seed(seed)
        
        try:
            result = self.pipe(
                prompt=prompt,
                negative_prompt=neg_prompt,
                image=person_img,
                mask_image=mask,
                ip_adapter_image=cloth_img,
                cloth=cloth_tensor,
                pose_img=pose_tensor,
                text_embeds_cloth=prompt_embeds_cloth,
                num_inference_steps=denoise_steps,
                strength=strength,
                guidance_scale=guidance_scale,
                generator=generator,
                height=1024,
                width=768,
            )
            
            # Handle both tuple and object return types
            if isinstance(result, tuple):
                output = result[0][0]  # (images, has_nsfw) -> images[0]
            else:
                output = result.images[0]
            
            # 6. Return Result
            byte_stream = io.BytesIO()
            output.save(byte_stream, format="PNG")
            result_bytes = byte_stream.getvalue()

            if not debug:
                return result_bytes

            mask_buf = io.BytesIO()
            mask.convert("L").save(mask_buf, format="PNG")

            pose_buf = io.BytesIO()
            pose_img.convert("RGB").save(pose_buf, format="PNG")

            return {
                "result_png": result_bytes,
                "mask_png": mask_buf.getvalue(),
                "pose_png": pose_buf.getvalue(),
                "pose_mode": pose_mode_norm,
            }
            
        except Exception as e:
            print(f"Inference Failed: {e}")
            raise e

@app.local_entrypoint()
def main(
    person: str = "redshorts.png",
    cloth: str = "clean_dress.png",
    mask: Optional[str] = None,
    prompt: str = "model is wearing a dress",
    cloth_prompt: str = "",
    steps: int = 30,
    strength: float = 1.0,
    guidance: float = 10.0,
    pose_mode: str = "auto",
    debug: bool = False,
    seed: int = 42,
    out: str = "result.png",
):
    import io
    from PIL import Image

    print("Loading input images...")

    person_img = Image.open(person).convert("RGB")
    person_buf = io.BytesIO()
    person_img.save(person_buf, format="PNG")
    person_bytes = person_buf.getvalue()

    cloth_img = Image.open(cloth).convert("RGB")
    cloth_buf = io.BytesIO()
    cloth_img.save(cloth_buf, format="PNG")
    cloth_bytes = cloth_buf.getvalue()

    mask_bytes = None
    if mask:
        mask_img = Image.open(mask).convert("L")
        mask_buf = io.BytesIO()
        mask_img.save(mask_buf, format="PNG")
        mask_bytes = mask_buf.getvalue()

    print("Sending request to remote model...")
    model = Model()
    try:
        res = model.try_on.remote(
            person_image_bytes=person_bytes,
            cloth_image_bytes=cloth_bytes,
            person_mask_bytes=mask_bytes,
            prompt=prompt,
            cloth_prompt=cloth_prompt or None,
            denoise_steps=steps,
            strength=strength,
            guidance_scale=guidance,
            pose_mode=pose_mode,
            debug=debug,
            seed=seed,
        )

        if isinstance(res, dict):
            with open(out, "wb") as f:
                f.write(res["result_png"])
            with open(f"{out}.mask.png", "wb") as f:
                f.write(res["mask_png"])
            with open(f"{out}.pose.png", "wb") as f:
                f.write(res["pose_png"])
            print(
                f"✅ Success! Saved result to {out} ({len(res['result_png'])} bytes) + debug mask/pose"
            )
            if "pose_mode" in res:
                print(f"Pose mode used: {res['pose_mode']}")
        else:
            with open(out, "wb") as f:
                f.write(res)
            print(f"✅ Success! Saved result to {out} ({len(res)} bytes)")
    except Exception as e:
        print(f"❌ Verification failed (check remote logs for signature): {e}")
