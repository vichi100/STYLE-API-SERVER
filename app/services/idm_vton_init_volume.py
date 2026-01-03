import modal
import os
import shutil

# Define volume for IDM-VTON
vol = modal.Volume.from_name("idm-vton-weights", create_if_missing=True)
app = modal.App("idm-vton-init")

image = modal.Image.debian_slim().pip_install("huggingface_hub")

@app.function(volumes={"/weights": vol}, image=image, timeout=3600)
def download_weights():
    from huggingface_hub import snapshot_download

    repo_id = "yisol/IDM-VTON"
    print(f"Downloading {repo_id} snapshot...")
    
    # Download entire repo to cache
    # allow_patterns can be used if we only need specific files, but IDM-VTON usually needs the full diffusers structure
    download_dir = snapshot_download(repo_id=repo_id)
    
    print(f"Download completed to {download_dir}")
    print("Moving files to Volume /weights...")
    
    # We want the contents of download_dir to be in /weights
    # /weights is a mount.
    
    # Simple copy approach
    for item in os.listdir(download_dir):
        s = os.path.join(download_dir, item)
        d = os.path.join("/weights", item)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
            
    vol.commit()
    print("✅ All IDM-VTON weights saved to volume 'idm-vton-weights'.")

if __name__ == "__main__":
    # verification
    pass
