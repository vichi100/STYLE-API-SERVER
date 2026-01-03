import modal
import os

vol = modal.Volume.from_name("hr-viton-weights", create_if_missing=True)
app = modal.App("hr-viton-init")

@app.function(volumes={"/weights": vol})
def check_weights():
    required_files = ["alias_final.pth", "segment_final.pth", "G_final.pth"]
    missing_files = []
    
    print("\nChecking for HR-VITON weights in Volume '/weights'...")
    files_in_vol = os.listdir("/weights")
    
    for f in required_files:
        if f not in files_in_vol:
            missing_files.append(f)
        else:
            print(f"✅ Found {f}")

    if not missing_files:
        print("\n🎉 SUCCESS: All required weights are present!")
    else:
        print("\n❌ MISSING WEIGHTS:")
        for f in missing_files:
            print(f" - {f}")
            
        print("\n" + "="*60)
        print("AUTOMATIC DOWNLOAD FAILED (All mirrors are gated/private).")
        print("YOU MUST UPLOAD THESE FILES MANUALLY.")
        print("="*60)
        print("\nStep 1: Download them from the official HR-VITON Google Drive.")
        print("Step 2: Run these commands locally (adjust paths):")
        
        for f in missing_files:
            print(f"  modal volume put hr-viton-weights /local/path/to/{f} /weights/{f}")
        
        print("\n" + "="*60 + "\n")
        # Exit with error to indicate setup is incomplete
        exit(1)

    vol.commit()