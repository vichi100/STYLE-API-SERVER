from app.services.appwrite import get_appwrite_db
from app.core.config import settings
from appwrite.queries import Query
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
            raise e

user_service = UserService()
