from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.entities import User
from app.schemas.auth import (
    BootstrapAdminRequest,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    Token,
    UserRead,
)
from app.services.account_scope import get_active_subscription, get_current_account
from app.services.auth import EmailNotVerifiedError, authenticate_user, bootstrap_admin, register_new_account, verify_email_token

router = APIRouter()


@router.post("/bootstrap", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def bootstrap(payload: BootstrapAdminRequest, db: Session = Depends(get_db)) -> User:
    existing_user = db.query(User).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap already completed")
    return bootstrap_admin(db, payload)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except EmailNotVerifiedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="กรุณายืนยันอีเมลก่อนเข้าสู่ระบบ",
        )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    try:
        user = register_new_account(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return RegisterResponse(
        message="สร้างบัญชีสำเร็จ กรุณายืนยันอีเมลเพื่อเข้าสู่ระบบ",
        verification_token=user.email_verification_token,
    )


@router.get("/verify-email", response_model=Token)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)) -> Token:
    try:
        user = verify_email_token(db, token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    current_account = get_current_account(db, current_user)
    if current_account:
        setattr(current_account, "active_subscription", get_active_subscription(current_account))
        setattr(current_user, "account", current_account)
    return current_user
