from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.vector_scoring_service import VectorScoringService, get_vector_service

router = APIRouter()
# Initialize service (this loads model and DB, may take a moment on startup)
vector_service = get_vector_service()

class VectorItemMetadata(BaseModel):
    general_category: str
    specific_category: Optional[str] = None
    custom_category: Optional[str] = None
    tags: Optional[str] = None

class VectorScoreRequest(BaseModel):
    top: Optional[VectorItemMetadata] = None
    bottom: Optional[VectorItemMetadata] = None
    mood: Optional[str] = None

@router.post("/vector-score")
async def score_outfit_vector(request: VectorScoreRequest):
    """
    Score outfit using Qdrant Vector Search + Semantic Similarity.
    """
    try:
        top_dict = request.top.dict() if request.top else None
        bottom_dict = request.bottom.dict() if request.bottom else None
        
        result = vector_service.score_outfit_semantic(top_dict, bottom_dict, request.mood)
        
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
