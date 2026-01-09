from app.services.appwrite import get_appwrite_db
from app.core.config import settings
from appwrite.query import Query
from appwrite.exception import AppwriteException
import logging

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self):
        self.db = get_appwrite_db()
        self.db_id = settings.APPWRITE_DATABASE_ID
        self.coll_id = "users"

    def get_user_by_mobile(self, mobile: str):
        try:
            # Query Appwrite for user with matching mobile
            response = self.db.list_documents(
                database_id=self.db_id,
                collection_id=self.coll_id,
                queries=[Query.equal("mobile", mobile)]
            )
            
            if response["total"] > 0:
                return response["documents"][0]
            return None
        except AppwriteException as e:
            logger.error(f"Error fetching user by mobile: {e}")
            raise e

    def create_user(self, mobile: str):
        try:
            # Since name and email are required by schema but we only have mobile,
            # we use placeholders until user updates profile.
            data = {
                "mobile": mobile,
                "name": "New User", 
                "email": f"{mobile}@placeholder.styl.com", # Mock email to satisfy constraint
                "gender": "unknown" 
            }
            
            result = self.db.create_document(
                database_id=self.db_id,
                collection_id=self.coll_id,
                document_id="unique()",
                data=data
            )
            return result
        except AppwriteException as e:
            logger.error(f"Error creating user: {e}")
    
    def add_wardrobe_item(self, user_id: str, wardrobe_id: str):
        """
        Appends a wardrobe ID to the user's wardrobe_id_list.
        """
        try:
            # 1. Get current user to fetch existing list
            user = self.db.get_document(self.db_id, self.coll_id, user_id)
            current_list = user.get("wardrobe_id_list") or []
            
            # 2. Append new ID
            if wardrobe_id not in current_list:
                current_list.append(wardrobe_id)
                
            # 3. Update document
            self.db.update_document(
                database_id=self.db_id,
                collection_id=self.coll_id,
                document_id=user_id,
                data={"wardrobe_id_list": current_list}
            )
            return True
        except AppwriteException as e:
            logger.error(f"Error adding wardrobe item to user: {e}")
            return False

    def remove_wardrobe_item(self, user_id: str, wardrobe_id: str):
        """
        Removes a wardrobe ID from the user's wardrobe_id_list.
        """
        try:
            # 1. Get current user
            print(f"US: Fetching user {user_id}...")
            user = self.db.get_document(self.db_id, self.coll_id, user_id)
            current_list = user.get("wardrobe_id_list") or []
            print(f"US: Current list count: {len(current_list)}")
            
            # 2. Remove ID if exists
            if wardrobe_id in current_list:
                current_list.remove(wardrobe_id)
                print(f"US: Removed {wardrobe_id}. New count: {len(current_list)}")
                
                # 3. Update document
                self.db.update_document(
                    database_id=self.db_id,
                    collection_id=self.coll_id,
                    document_id=user_id,
                    data={"wardrobe_id_list": current_list}
                )
                print("US: Update successful.")
                return True
            
            print(f"US: Item {wardrobe_id} not found in user's list.")
            return False # ID was not in list, but operation "succeeded" in not changing anything
        except AppwriteException as e:
            print(f"US: Error in removal: {e}")
            logger.error(f"Error removing wardrobe item from user: {e}")
            return False

user_service = UserService()
