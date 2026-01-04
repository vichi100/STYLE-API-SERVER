import httpx
import random
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class OTPService:
    @staticmethod
    def generate_otp_code() -> str:
        return str(random.randint(1000, 9999))

    @staticmethod
    async def send_otp(mobile: str, otp: str) -> bool:
        # User provided API structure: 
        # https://2factor.in/API/V1/{OTP_API}/SMS/{mobile}/{OTP}/{TEMPLATE_NAME}
        
        url = f"https://2factor.in/API/V1/{settings.OTP_API_KEY}/SMS/{mobile}/{otp}/{settings.OTP_TEMPLATE_NAME}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Check 2factor specific response if needed, but usually 200 is success
                logger.info(f"OTP sent successfully to {mobile}")
                return True
        except Exception as e:
            logger.error(f"Failed to send OTP to {mobile}: {str(e)}")
            return False

otp_service = OTPService()
