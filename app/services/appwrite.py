from appwrite.client import Client
from app.core.config import settings

def get_appwrite_client() -> Client:
    """
    Returns a configured Appwrite Client instance.
    """
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)
    return client

from appwrite.services.databases import Databases

def get_appwrite_db(client: Client = None) -> Databases:
    """
    Returns a configured Appwrite Databases service instance.
    """
    if client is None:
        client = get_appwrite_client()
    return Databases(client)
