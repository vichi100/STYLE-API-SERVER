from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

from app.api.v1 import images
from app.api.v1 import garments
from app.api.v1 import auth
app.include_router(images.router, prefix="/api/v1/images", tags=["images"])
app.include_router(garments.router, prefix="/api/v1/garments", tags=["garments"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {"message": "Welcome to STYL API"}
