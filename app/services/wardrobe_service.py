from app.services.appwrite import get_appwrite_db
from app.core.config import settings
from appwrite.exception import AppwriteException
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WardrobeService:
    def __init__(self):
        self.db = get_appwrite_db()
        self.db_id = settings.APPWRITE_DATABASE_ID
        self.coll_id = "wardrobe"

    def create_wardrobe_item(self, user_id: str, image_id: str, image_url: str = None, category: str = "Uncategorized"):
        """
        Creates a new wardrobe item.
        """
        try:
            data = {
                "user_id": user_id,
                "image_id": image_id,
                "image_url": image_url,
                "general_category": category,
                "add_date": datetime.now().isoformat()
            }
            
            result = self.db.create_document(
                database_id=self.db_id,
                collection_id=self.coll_id,
                document_id="unique()",
                data=data
            )
            return result
        except AppwriteException as e:
            logger.error(f"Error creating wardrobe item: {e}")
            raise e

    def get_user_wardrobe(self, user_id: str):
        """
        Retrieves all wardrobe items for a specific user.
        """
        from appwrite.query import Query
        try:
            response = self.db.list_documents(
                database_id=self.db_id,
                collection_id=self.coll_id,
                queries=[
                    Query.equal("user_id", user_id),
                    Query.order_desc("add_date"), # Newest first
                    Query.limit(1000) # Retrieve up to 1000 items (Appwrite default is 25)
                ]
            )
            return response["documents"]
        except AppwriteException as e:
            logger.error(f"Error fetching wardrobe for user {user_id}: {e}")
            logger.error(f"Error fetching wardrobe for user {user_id}: {e}")
            return []

    def delete_wardrobe_item(self, user_id: str, item_id: str):
        """
        Deletes a wardrobe item, its image, and unlinks from user.
        """
        from app.services.appwrite_storage import delete_image
        from app.services.user_service import user_service
        from app.core.config import settings

        try:
            # 1. Fetch Item to get details (Image ID)
            print(f"WS: Fetching item {item_id} for deletion...")
            try:
                print(f"WS: Attempting to get document with ID: {item_id}")
                item = self.db.get_document(self.db_id, self.coll_id, item_id)
                print(f"WS: Item found via Doc ID. Owner: {item.get('user_id')}")
            except AppwriteException as e:
                print(f"WS: Item {item_id} NOT found by Doc ID. Error: {e}")
                print(f"WS: Checking if {item_id} is an Image ID...")
                # Fallback: Check if item_id is actually an image_id
                from appwrite.query import Query
                try:
                    res = self.db.list_documents(
                        self.db_id, 
                        self.coll_id, 
                        [Query.equal("image_id", item_id)]
                    )
                    if res["total"] > 0:
                        item = res["documents"][0]
                        # Important: switch item_id to the actual document ID
                        print(f"WS: Found item via Image ID! Swapping {item_id} -> {item['$id']}")
                        item_id = item['$id'] 
                    else:
                        print(f"WS: Item not found by ID or Image ID.")
                        return False
                except Exception as ex:
                    print(f"WS: Error searching by Image ID: {ex}")
                    return False
            
            # Verify ownership
            if item.get("user_id") != user_id:
                print(f"WS: Ownership mismatch! Request User: {user_id}, Item Owner: {item.get('user_id')}")
                logger.warning(f"User {user_id} attempted to delete non-owned item {item_id}")
                return False

            # 2. Delete Image from Storage
            image_id = item.get("image_id")
            wardrobe_bucket = settings.APPWRITE_WARDROBE_BUCKET_ID
            print(f"WS: Deleting Image {image_id} from bucket {wardrobe_bucket}...")
            
            if image_id and wardrobe_bucket:
                delete_image(wardrobe_bucket, image_id)
            else:
                print("WS: No image_id or bucket_id found, skipping storage delete.")

            # 3. Unlink from User
            print(f"WS: Unlinking item {item_id} from user {user_id}...")
            user_service.remove_wardrobe_item(user_id, item_id)

            # 4. Delete Wardrobe Document
            print(f"WS: Deleting document {item_id}...")
            self.db.delete_document(self.db_id, self.coll_id, item_id)
            print(f"WS: Document deleted.")
            
            return True

        except AppwriteException as e:
            print(f"WS: Exception during deletion: {e}")
            logger.error(f"Error deleting wardrobe item {item_id}: {e}")
            return False

    def update_wardrobe_item(self, item_id: str, updates: dict):
        """
        Updates a wardrobe item with new attributes.
        """
        try:
            print(f"WS: Updating item {item_id} with {updates.keys()}")
            result = self.db.update_document(
                database_id=self.db_id,
                collection_id=self.coll_id,
                document_id=item_id,
                data=updates
            )
            return result
        except AppwriteException as e:
            logger.error(f"Error updating wardrobe item {item_id}: {e}")
            print(f"WS: Error updating item {item_id}: {e}")
            return None

wardrobe_service = WardrobeService()
