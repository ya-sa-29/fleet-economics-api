from src.api.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, UserRole
from src.models.company import Company
from src.schemas.user import UserRegisterRequest, UserResponse, TokenResponse
from src.api.auth_utils import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_company_and_admin(request: UserRegisterRequest, db: Session = Depends(get_db)):
    # 1. Перевіряємо, чи не зайнятий email
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач з таким email вже існує"
        )

    # 2. Створюємо компанію (Tenant)
    new_company = Company(name=request.company_name)
    db.add(new_company)
    db.flush()  # Замість commit(). Отримуємо ID, але транзакція ще відкрита

    # 3. Створюємо першого користувача
    new_user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        company_id=new_company.id,
        role=UserRole.ADMIN
    )
    db.add(new_user)
    db.commit()  # Фіксуємо компанію і юзера разом!
    db.refresh(new_user)

    # Повертаємо дані користувача (Pydantic сам приховає пароль завдяки UserResponse)
    return new_user

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Зверни увагу: form_data.username — це стандарт OAuth2, ми передаємо туди email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Користувач деактивований",
        )

    # Генеруємо JWT токен, вшиваючи туди email користувача
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Повертає профіль поточного авторизованого користувача.
    Якщо токена немає або він недійсний - поверне 401 Unauthorized.
    """
    return current_user