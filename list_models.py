import google.generativeai as genai
import os
from app.core.config import settings

# Configure API key
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    print(f"Using API Key: {settings.GOOGLE_API_KEY[:5]}...{settings.GOOGLE_API_KEY[-5:]}")
else:
    print("Error: GOOGLE_API_KEY not found in settings.")
    exit(1)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
