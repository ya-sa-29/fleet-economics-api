from pydantic import BaseModel, EmailStr, ConfigDict
from src.models.user import UserRole


class UserRegisterRequest(BaseModel):
    company_name: str
    email: EmailStr
    password: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole


class UserUpdateRequest(BaseModel):
    role: UserRole


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    company_id: int
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"