from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

from app.api.v1 import garments
from app.api.v1 import auth
from app.api.v1 import wardrobe
from app.api.v1 import proxy

app.include_router(garments.router, prefix="/api/v1/garments", tags=["garments"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(wardrobe.router, prefix="/api/v1/wardrobe", tags=["wardrobe"])
app.include_router(proxy.router, prefix="/proxy", tags=["proxy"])

from app.api.v1 import mismatch
app.include_router(mismatch.router, prefix="/api/v1/mismatch", tags=["mismatch"])

from app.api.v1 import style
app.include_router(style.router, prefix="/api/v1/style", tags=["style"])

from app.api.v1 import rule_scoring
app.include_router(rule_scoring.router, prefix="/api/v1/rule-style", tags=["rule-style"])

from app.api.v1 import vector_scoring
app.include_router(vector_scoring.router, prefix="/api/v1/semantic", tags=["semantic-style"])

from app.api.v1 import color_scoring
app.include_router(color_scoring.router, prefix="/api/v1/color", tags=["color-theory"])

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
@app.on_event("startup")
async def startup_event():
    # Initialize Vector Service (Load Model & Ingest Rules)
    # This runs once on server start
    print("Initializing Vector Scoring Service...")
    vector_scoring.vector_service.initialize()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {"message": "Welcome to STYL API"}
