import os
import time

if __name__ == "__main__":
    print("Stopping any running uvicorn servers...")
    # Kill existing uvicorn processes to free the port
    os.system("pkill -f 'uvicorn app.main:app'")
    time.sleep(1) # Wait for port to clear
    
    print("Starting Server on http://0.0.0.0:8000 ...")
    os.system("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
