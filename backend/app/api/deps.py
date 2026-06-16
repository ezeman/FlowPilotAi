from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.entities import User
from app.services.account_scope import get_active_subscription, get_current_account, is_platform_admin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")

    return user


def require_roles(*roles: str, check_subscription: bool = True):
    def checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if is_platform_admin(current_user):
            return current_user
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        if check_subscription:
            account = get_current_account(db, current_user)
            if not get_active_subscription(account):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "code": "subscription_required",
                        "th": "ไม่มี subscription ที่ใช้งานได้ กรุณาชำระเงินและรอการยืนยันจาก platform ก่อนใช้งาน",
                        "en": "No active subscription. Please submit a payment request and wait for platform approval.",
                    },
                )
        return current_user

    return checker
