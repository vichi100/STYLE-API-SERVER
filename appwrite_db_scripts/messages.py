from appwrite.services.databases import Databases
from .utils import create_attr, get_or_create_collection

def setup_messages(db_service: Databases, db_id: str):
    coll_name = "Messages"
    coll_id = "messages"
    
    get_or_create_collection(db_service, db_id, coll_id, coll_name)
    
    print(f"Ensuring Attributes for {coll_name}...")
    
    create_attr(db_service.create_string_attribute, db_id, coll_id, "conversation_id", 36, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "sender", 128, required=True)
    # text can be optional if message is just an image
    create_attr(db_service.create_string_attribute, db_id, coll_id, "text", 5000, required=False)
    # array=True for imageIds
    create_attr(db_service.create_string_attribute, db_id, coll_id, "image_ids", 36, required=False, array=True)
    create_attr(db_service.create_datetime_attribute, db_id, coll_id, "timestamp", required=True)
