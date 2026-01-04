from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginRequest
from app.services.otp_service import otp_service

router = APIRouter()

@router.post("/login", status_code=status.HTTP_200_OK)
async def login(request: LoginRequest):
    """
    Initiate login by sending an OTP to the provided mobile number.
    """
    mobile = request.mobile
    
    # 1. Generate OTP
    otp = otp_service.generate_otp_code()
    
    # 2. Send OTP
    success = await otp_service.send_otp(mobile, otp)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )
    
    # In a real app, you might want to store the OTP/hash in a DB or cache (Redis) 
    # mapped to the phone number with an expiration to verify it later.
    # For this task, we are just sending it.
    
    
    return {"status": "success", "message": "OTP sent successfully"}

from app.schemas.auth import CheckUserRequest
from app.services.user_service import user_service

@router.post("/check-user", status_code=status.HTTP_200_OK)
async def check_user(request: CheckUserRequest):
    """
    Check if user exists by mobile.
    If yes -> Return user details.
    If no -> Create new user with mobile (and placeholder data) and return details.
    """
    mobile = request.mobile
    
    # 1. Check if user exists
    user = user_service.get_user_by_mobile(mobile)
    
    if user:
        return {"status": "existing_user", "data": user}
    
    # 2. If not, create new user
    new_user = user_service.create_user(mobile)
    
    # Return minimal info as requested (mobile and id) or full doc
    return {
        "status": "new_user", 
        "data": {
            "$id": new_user["$id"],
            "mobile": new_user["mobile"]
        }
    }
