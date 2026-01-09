# How to Start the Server

## Prerequisites
- **Python 3.9+** installed.
- **pip** (Python package installer).

## Installation

1.  **Create a Virtual Environment** (Recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Server

To start the server in development mode (with auto-reload):

```bash
# Option 1: Activate venv first (Recommended)
source venv/bin/activate
uvicorn app.main:app --reload

# Option 2: Run directly using venv binary
./venv/bin/uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`.

### Documentation
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Important Note regarding Background Removal
The first time you use the background removal feature (`/api/v1/images/remove-background`), the server will automatically download the U-2-Net model (~176MB). This may take a few moments depending on your internet connection. Subsequent requests will be much faster.



python3 server.py