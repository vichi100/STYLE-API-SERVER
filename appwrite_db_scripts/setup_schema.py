import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.appwrite import get_appwrite_db
from app.core.config import settings
from appwrite.exception import AppwriteException

# Import collection scripts
from appwrite_db_scripts.users import setup_users
from appwrite_db_scripts.dresses import setup_closet # Kept function name same in dresses.py? No, likely user just renamed file. I should check dresses.py content again but typically safe to assume rename. Wait, previous output showed `def setup_closet` inside `dresses.py`.
from appwrite_db_scripts.conversations import setup_conversations
from appwrite_db_scripts.messages import setup_messages
from appwrite_db_scripts.top_matches import setup_top_matches
from appwrite_db_scripts.mis_match import setup_mis_match
from appwrite_db_scripts.accessories import setup_accessories

def setup_schema():

    print("--- Setting up Appwrite Schema (Modular) ---")
    
    try:
        db_service = get_appwrite_db()
        
        # 1. Check or Create Database
        db_id = settings.APPWRITE_DATABASE_ID
        if not db_id:
            db_id = "STYL_DB" # Default name
            
        try:
            db_service.get(db_id)
            print(f"Database '{db_id}' already exists.")
        except AppwriteException as e:
            if e.code == 404:
                print(f"Creating Database '{db_id}'...")
                db_service.create(db_id, "STYL Database")
            else:
                raise e

        # 2. Run Collection Setups
        print("\n--- Setup Users Collection ---")
        setup_users(db_service, db_id)

        print("\n--- Setup Closet/Dresses Collection ---")
        setup_closet(db_service, db_id)

        print("\n--- Setup Conversations Collection ---")
        setup_conversations(db_service, db_id)

        print("\n--- Setup Messages Collection ---")
        setup_messages(db_service, db_id)

        print("\n--- Setup TopMatches Collection ---")
        setup_top_matches(db_service, db_id)

        print("\n--- Setup MisMatch Collection ---")
        setup_mis_match(db_service, db_id)

        print("\n--- Setup Accessories Collection ---")
        setup_accessories(db_service, db_id)

        print("\nSchema setup complete!")
        print(f"Database ID: {db_id}")
        
        if not settings.APPWRITE_DATABASE_ID:
            print(f"\n[IMPORTANT] Please update your .env file with:\nAPPWRITE_DATABASE_ID={db_id}")

    except Exception as e:
        print(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_schema()
