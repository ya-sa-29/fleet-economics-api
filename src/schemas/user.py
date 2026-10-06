from pydantic import BaseModel, EmailStr, ConfigDict
from src.models.user import UserRole

# Схема того, що юзер відправляє при реєстрації
class UserRegisterRequest(BaseModel):
    company_name: str
    email: EmailStr
    password: str

# Схема того, що ми віддаємо назад (без пароля!)
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    company_id: int
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

# Схема для токена авторизації
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"