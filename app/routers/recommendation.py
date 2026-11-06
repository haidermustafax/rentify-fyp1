from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.services.recommender import get_ai_recommendations

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])

@router.get("")
def recommend(current_user: dict = Depends(get_current_user)):
    # Calls the AI module using the currently logged-in user's ID
    recommendations = get_ai_recommendations(user_id=current_user["id"])
    return recommendations
