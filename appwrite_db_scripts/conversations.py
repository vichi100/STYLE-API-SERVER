from appwrite.services.databases import Databases
from .utils import create_attr, get_or_create_collection

def setup_conversations(db_service: Databases, db_id: str):
    coll_name = "Conversations"
    coll_id = "conversations"
    
    get_or_create_collection(db_service, db_id, coll_id, coll_name)
    
    print(f"Ensuring Attributes for {coll_name}...")
    
    create_attr(db_service.create_string_attribute, db_id, coll_id, "name", 128, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "user_id", 36, required=True)
    create_attr(db_service.create_datetime_attribute, db_id, coll_id, "created_at", required=True)
