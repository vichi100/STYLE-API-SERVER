from qdrant_client import QdrantClient
import qdrant_client

# print(f"Qdrant Client Version: {qdrant_client.__version__}")

try:
    client = QdrantClient(path="qdrant_db_debug")
    print("Methods available on client:")
    methods = [m for m in dir(client) if not m.startswith('_')]
    for m in methods:
        print(f" - {m}")
    
    if hasattr(client, 'search'):
        print("SUCCESS: 'search' method found.")
    else:
        print("FAILURE: 'search' method NOT found.")

except Exception as e:
    print(f"Error initializing client: {e}")
