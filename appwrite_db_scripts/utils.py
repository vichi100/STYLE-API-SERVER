from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

def create_attr(func, *args, **kwargs):
    """
    Helper to create an attribute, ignoring 'Attribute already exists' (409) errors.
    """
    try:
        func(*args, **kwargs)
        print(f"  Created attribute.")
    except AppwriteException as e:
        if e.code == 409: # Conflict - already exists
            print(f"  Attribute already exists.")
        else:
            print(f"  Error creating attribute: {e}")

def get_or_create_collection(db_service: Databases, db_id: str, coll_id: str, coll_name: str):
    """
    Checks if a collection exists, otherwise creates it.
    """
    try:
        db_service.get_collection(db_id, coll_id)
        print(f"Collection '{coll_name}' already exists.")
    except AppwriteException as e:
        if e.code == 404:
            print(f"Creating Collection '{coll_name}'...")
            db_service.create_collection(db_id, coll_id, coll_name)
        else:
            raise e
