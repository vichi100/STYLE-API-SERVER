from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.services.rule_based_scoring_service import RuleBasedScoringService

router = APIRouter()
rule_service = RuleBasedScoringService()

# Re-use similar models or define new ones for clarity
class WardrobeItemMetadata(BaseModel):
    user_id: str
    general_category: str
    specific_category: Optional[str] = None
    custom_category: Optional[str] = None
    # We don't need image_id or url for rule based
    tags: Optional[str] = None
    colors: Optional[list[str]] = None
    caption: Optional[str] = None

class RuleScoreRequest(BaseModel):
    top: Optional[WardrobeItemMetadata] = None
    bottom: Optional[WardrobeItemMetadata] = None
    layer: Optional[WardrobeItemMetadata] = None
    mood: Optional[str] = None

@router.post("/rule-score")
async def score_outfit_rules(request: RuleScoreRequest):
    """
    Score an outfit using deterministic JSON rules (no AI).
    Analyzes metadata like categories, tags, and colors.
    """
    try:
        # Convert Pydantic models to dicts for the service
        top_dict = request.top.dict() if request.top else None
        bottom_dict = request.bottom.dict() if request.bottom else None
        layer_dict = request.layer.dict() if request.layer else None
        
        score = rule_service.score_outfit(top_dict, bottom_dict, layer_dict, mood=request.mood)
        
        return {
            "status": "success",
            "data": score
        }

    except Exception as e:
        print(f"Error in rule scoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
