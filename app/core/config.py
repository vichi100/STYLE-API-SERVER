from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "STYL-API-SERVER"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Appwrite Settings
    APPWRITE_PROJECT_ID: str = ""
    APPWRITE_API_KEY: str = ""
    APPWRITE_ENDPOINT: str = "https://cloud.appwrite.io/v1"
    APPWRITE_DATABASE_ID: str = ""
    APPWRITE_BUCKET_ID: str = ""
    APPWRITE_WARDROBE_BUCKET_ID: str = ""

    # OTP Settings
    OTP_API_KEY: str = ""
    OTP_TEMPLATE_NAME: str = "FlickSickOTP1"

    # Moondream
    MOONDREAM_API_KEY: str = ""
    
    # Gemini
    GOOGLE_API_KEY: str = ""


    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
