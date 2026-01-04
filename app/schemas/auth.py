from pydantic import BaseModel, constr

class LoginRequest(BaseModel):
    mobile: constr(min_length=10, max_length=15) # Basic validation for mobile number

class CheckUserRequest(BaseModel):
    mobile: constr(min_length=10, max_length=15)
