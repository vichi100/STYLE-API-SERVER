from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginRequest
from app.services.otp_service import otp_service

router = APIRouter()

@router.post("/otp", status_code=status.HTTP_200_OK)
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
    
    
    # Encode OTP for client-side decoding
    encoded_otp = otp_service.encode_otp(otp)
    
    return {"status": "success", "message": "OTP sent successfully", "otp": encoded_otp}

from app.schemas.auth import CheckUserRequest
from app.services.user_service import user_service

@router.post("/login", status_code=status.HTTP_200_OK)
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
        # Extract requested fields
        dress_list = user.get("dress_id_list") or []
        accessory_list = user.get("accessory_id_list") or []
        
        response_data = {
            "Name": user.get("name"),
            "Id": user.get("$id"),
            "Mobile": user.get("mobile"),
            "Email": user.get("email"),
            "Height": user.get("height"),
            "Weight": user.get("weight"),
            "full_lenght_Image_id": user.get("full_length_image_id"), # DB has full_length_image_id
            "close_up_image_id": user.get("close_up_image_id"),
            "dress_id_list_count": len(dress_list),
            "accessory_id_list_count": len(accessory_list)
        }
        return {"status": "existing_user", "data": response_data}
    
    # 2. If not, create new user
    new_user = user_service.create_user(mobile)
    
    # Return formatted info for new user too (fields will be empty/placeholder)
    return {
        "status": "new_user", 
        "data": {
            "Name": new_user.get("name"),
            "Id": new_user.get("$id"),
            "Mobile": new_user.get("mobile"),
            "Email": new_user.get("email"),
            "Height": new_user.get("height"),
            "Weight": new_user.get("weight"),
            "full_lenght_Image_id": None,
            "close_up_image_id": None,
            "dress_id_list_count": 0,
            "accessory_id_list_count": 0
        }
    }
