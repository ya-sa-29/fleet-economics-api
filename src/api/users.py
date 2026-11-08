from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, UserRole
from src.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
)
from src.api.dependencies import get_current_user
from src.api.auth_utils import get_password_hash


router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_in: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ADMIN та DISPATCHER можуть створювати співробітників
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостатньо прав для створення користувачів",
        )

    # DISPATCHER може створювати лише DRIVER
    if current_user.role == UserRole.DISPATCHER:
        if user_in.role != UserRole.DRIVER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Диспетчер може створювати лише водіїв",
            )

    # ADMIN не може створювати другого ADMIN
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неможливо створити додаткового адміністратора",
        )

    # Email має бути унікальним глобально
    existing_user = db.query(User).filter(
        User.email == user_in.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач з таким email вже існує",
        )

    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        company_id=current_user.company_id,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.DRIVER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Водій не має доступу до списку співробітників",
        )

    return db.query(User).filter(
        User.company_id == current_user.company_id,
        User.deleted_at.is_(None),
    ).offset(skip).limit(limit).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.DRIVER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Водій не має доступу до профілів інших співробітників",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id,
        User.deleted_at.is_(None),
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувача не знайдено",
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Змінювати ролі може лише адміністратор",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id,
        User.deleted_at.is_(None),
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувача не знайдено",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна змінювати власну роль",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна змінювати роль адміністратора",
        )

    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна призначити додаткового адміністратора",
        )

    user.role = user_in.role

    db.commit()
    db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Деактивувати користувачів може лише адміністратор",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id,
        User.deleted_at.is_(None),
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувача не знайдено",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна деактивувати власний обліковий запис",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна деактивувати адміністратора",
        )

    user.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return None