import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.appwrite import get_appwrite_db
from appwrite.services.databases import Databases

def main():
    print("Testing Appwrite Database Service Initialization...")
    try:
        db = get_appwrite_db()
        if isinstance(db, Databases):
            print("Database service initialized successfully.")
        else:
            print("Failed: Object is not an instance of Databases")
            sys.exit(1)
            
    except Exception as e:
        print(f"Failed to initialize database service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
