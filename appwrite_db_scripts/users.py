from appwrite.services.databases import Databases
from .utils import create_attr, get_or_create_collection

def setup_users(db_service: Databases, db_id: str):
    coll_name = "Users"
    coll_id = "users"
    
    get_or_create_collection(db_service, db_id, coll_id, coll_name)
    
    print(f"Ensuring Attributes for {coll_name}...")
    
    create_attr(db_service.create_string_attribute, db_id, coll_id, "name", 128, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "email", 128, required=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "mobile", 32, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "auth_user_id", 36, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "gender", 32, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "height", 32, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "weight", 32, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "skin_color", 64, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "image_id", 36, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "full_length_image_id", 36, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "close_up_image_id", 36, required=False)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "dress_id_list", 36, required=False, array=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "accessory_id_list", 36, required=False, array=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "top_matches_id_list", 36, required=False, array=True)
    create_attr(db_service.create_string_attribute, db_id, coll_id, "mis_match_id_list", 36, required=False, array=True)
