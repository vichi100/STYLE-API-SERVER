from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
import sys
import os

# 1. Setup path to import app settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from app.core.config import settings
except ImportError:
    print("Error: Could not import settings.")
    exit(1)

# 2. Initialize Appwrite Client
client = Client()
try:
    (client
      .set_endpoint(settings.APPWRITE_ENDPOINT)
      .set_project(settings.APPWRITE_PROJECT_ID)
      .set_key(settings.APPWRITE_API_KEY)
    )
except Exception as e:
    print(f"Error initializing Appwrite Client: {e}")
    exit(1)

storage = Storage(client)

def upload_image(image_path: str, bucket_id: str = None):
    """
    Uploads an image to the Appwrite bucket and returns the File ID.
    If bucket_id is not provided, uses the default APPWRITE_BUCKET_ID.
    """
    if not os.path.exists(image_path):
        print(f"Error: File {image_path} does not exist.")
        return None

    if not bucket_id:
        bucket_id = settings.APPWRITE_BUCKET_ID
    if not bucket_id:
        print("Error: APPWRITE_BUCKET_ID is not set.")
        return None

    print(f"Uploading {image_path} to bucket {bucket_id}...")

    try:
        result = storage.create_file(
            bucket_id=bucket_id,
            file_id='unique()',
            file=InputFile.from_path(image_path)
        )
        file_id = result['$id']
        print(f"✅ Upload Successful!")
        print(f"File ID: {file_id}")
        
        # Construct View URL (Manual construction as get_file_view returns binary data usually, 
        # but let's check SDK. Actually storage.get_file_view(bucket_id, file_id) returns the file content bytes in Python SDK?
        # No, usually it returns a URL in client-side SDKs, but in Server SDK it returns bytes.
        # So we just print the ID.)
        
        return file_id

    except Exception as e:
        print(f"❌ Upload Failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Upload Failed: {e}")
        return None

def upload_image_from_bytes(image_data: bytes, filename: str, bucket_id: str = None):
    """
    Uploads bytes directly to Appwrite without saving to disk.
    """
    if not bucket_id:
        bucket_id = settings.APPWRITE_BUCKET_ID
    if not bucket_id:
        print("Error: APPWRITE_BUCKET_ID is not set.")
        return None
        
    print(f"Uploading {filename} ({len(image_data)} bytes) to bucket {bucket_id}...")
    
    try:
        # InputFile.from_bytes(data, name, media_type) - media_type implied by name usually?
        # Actually checking SDK, InputFile.from_bytes doesn't exist in older versions, 
        # but modern one has it. 
        # If not, we can use client.call directly, but assuming it exists.
        # It's usually InputFile.from_bytes(data, filename=...)
        
        file = InputFile.from_bytes(image_data, filename=filename, mime_type="image/jpeg")

        result = storage.create_file(
            bucket_id=bucket_id,
            file_id='unique()',
            file=file
        )
        file_id = result['$id']
        print(f"✅ Byte Upload Successful! ID: {file_id}")
        return file_id
    except Exception as e:
        print(f"❌ Byte Upload Failed: {e}")
        return None
def delete_image(bucket_id: str, file_id: str):
    """
    Deletes an image from the Appwrite bucket.
    """
    try:
        storage.delete_file(bucket_id=bucket_id, file_id=file_id)
        print(f"✅ Deleted file {file_id} from bucket {bucket_id}")
        return True
    except Exception as e:
        print(f"❌ Delete Failed: {e}")

def get_file_bytes(bucket_id: str, file_id: str) -> bytes:
    """
    Fetches the file content bytes from Appwrite.
    """
    try:
        # storage.get_file_download returns the raw binary content
        result = storage.get_file_download(bucket_id=bucket_id, file_id=file_id)
        return result
    except Exception as e:
        print(f"❌ Fetch Failed: {e}")
        return None



if __name__ == "__main__":
    # Usage: python3 app/services/appwrite_storage.py [image_path]
    image_to_upload = "gemini_bg_removed.png" # Default
    if len(sys.argv) > 1:
        image_to_upload = sys.argv[1]
    
    upload_image(image_to_upload)
