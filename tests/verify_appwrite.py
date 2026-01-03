import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.appwrite import get_appwrite_client
from app.core.config import settings

def main():
    print("Testing Appwrite Client Initialization...")
    try:
        client = get_appwrite_client()
        print("Client initialized successfully.")
        print(f"Endpoint: {settings.APPWRITE_ENDPOINT}")
        print(f"Project ID: {settings.APPWRITE_PROJECT_ID}")
        
        # We can't really call API without valid keys, but we can print success of import and setup
        if not settings.APPWRITE_PROJECT_ID or not settings.APPWRITE_API_KEY:
             print("\n[WARNING] Project ID or API Key is missing. Connection test will likely fail if attempted.")
        
    except Exception as e:
        print(f"Failed to initialize client: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
