from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Account, AccountSubscription, PaymentRequest, SubscriptionPlan, User
from app.schemas.billing import PaymentRequestCreate, PaymentRequestRead, RejectRequest
from app.services.account_scope import is_platform_admin, require_account

router = APIRouter()


def _attach_account_names(requests: list[PaymentRequest], db: Session) -> list[PaymentRequest]:
    ids = {r.account_id for r in requests}
    names = {a.id: a.name for a in db.query(Account).filter(Account.id.in_(ids)).all()}
    for r in requests:
        setattr(r, "account_name", names.get(r.account_id))
    return requests


@router.post("/payment-requests", response_model=PaymentRequestRead, status_code=status.HTTP_201_CREATED)
def create_payment_request(
    payload: PaymentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", check_subscription=False)),
) -> PaymentRequest:
    account_id = require_account(current_user)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.plan_code, SubscriptionPlan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    req = PaymentRequest(
        account_id=account_id,
        plan_code=payload.plan_code,
        amount=plan.price_monthly,
        payment_method=payload.payment_method,
        bank_name=payload.bank_name,
        reference_number=payload.reference_number,
        transfer_date=payload.transfer_date,
        note=payload.note,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    setattr(req, "account_name", None)
    return req


@router.get("/payment-requests", response_model=list[PaymentRequestRead])
def list_payment_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", check_subscription=False)),
) -> list[PaymentRequest]:
    if is_platform_admin(current_user):
        reqs = db.query(PaymentRequest).order_by(PaymentRequest.created_at.desc()).all()
    else:
        account_id = require_account(current_user)
        reqs = db.query(PaymentRequest).filter(PaymentRequest.account_id == account_id).order_by(PaymentRequest.created_at.desc()).all()
    return _attach_account_names(reqs, db)


@router.post("/payment-requests/{request_id}/approve", response_model=PaymentRequestRead)
def approve_payment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentRequest:
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can approve payments")

    req = db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {req.status}")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == req.plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    db.query(AccountSubscription).filter(
        AccountSubscription.account_id == req.account_id,
        AccountSubscription.status == "active",
    ).update({"status": "canceled"})

    db.add(AccountSubscription(account_id=req.account_id, plan_id=plan.id, status="active", auto_renew=False))

    req.status = "approved"
    req.reviewed_by_id = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    _attach_account_names([req], db)
    return req


@router.post("/payment-requests/{request_id}/reject", response_model=PaymentRequestRead)
def reject_payment_request(
    request_id: int,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentRequest:
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can reject payments")

    req = db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {req.status}")

    req.status = "rejected"
    req.reject_reason = payload.reason
    req.reviewed_by_id = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    _attach_account_names([req], db)
    return req
