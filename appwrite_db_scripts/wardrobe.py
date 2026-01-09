from appwrite.services.databases import Databases
from .utils import create_attr, get_or_create_collection

def setup_wardrobe(db_service: Databases, db_id: str):
    coll_name = "Wardrobe"
    coll_id = "wardrobe"
    
    get_or_create_collection(db_service, db_id, coll_id, coll_name)
    
    print(f"Ensuring Attributes for {coll_name}...")
    
    create_attr(db_service.create_string_attribute, db_id, coll_id, "user_id", 36, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "general_category", 128, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "specific_category", 128, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "image_id", 36, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "tag", 128, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "colors", 64, required=False, array=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "image_url", 2048, required=False) # Long for URL
    create_attr(db_service.create_string_attribute, db_id, coll_id, "caption", 1000, required=False) # AI or User Caption
    create_attr(db_service.create_datetime_attribute, db_id, coll_id, "add_date", required=False)
