import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import get_session
from app.models import Product
from app.payment_routes import PaymentOrder
from app.push_service import get_public_key, save_subscription, delete_subscription

router = APIRouter(prefix="/admin", tags=["Admin"])

# Shared admin access PIN. Change this value here if you ever want a new PIN.
ADMIN_PIN = "5831"

# Fixed signing key for 12-hour admin sessions. Keep this value private.
ADMIN_TOKEN_SECRET = b"fish-spot-malpe-admin-session-key-2026-10-13-7f3c9a2e"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_token() -> str:
    payload = _b64(json.dumps({"role": "admin", "exp": int(time.time()) + 60 * 60 * 12}).encode())
    signature = _b64(hmac.new(ADMIN_TOKEN_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def require_admin(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin login required")
    token = authorization[7:].strip()
    try:
        payload_part, signature = token.split(".", 1)
        expected = _b64(hmac.new(ADMIN_TOKEN_SECRET, payload_part.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)))
        if payload.get("role") != "admin" or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Expired token")
    except Exception:
        raise HTTPException(status_code=401, detail="Admin session expired. Please log in again.")
    return True


class LoginRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class ProductUpdate(BaseModel):
    price: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    size: Optional[str] = Field(default=None, max_length=100)
    fish_size: Optional[str] = Field(default=None, max_length=100)
    pieces: Optional[str] = Field(default=None, max_length=100)


@router.post("/login")
def admin_login(data: LoginRequest):
    if not hmac.compare_digest(data.pin, ADMIN_PIN):
        raise HTTPException(status_code=401, detail="Incorrect admin PIN")
    return {"access_token": _make_token(), "token_type": "bearer", "expires_in": 43200}


@router.get("/products", dependencies=[Depends(require_admin)])
def admin_products(session: Session = Depends(get_session)):
    return session.exec(select(Product).order_by(Product.category, Product.name, Product.id)).all()


@router.patch("/products/{product_id}", dependencies=[Depends(require_admin)])
def update_product(product_id: int, data: ProductUpdate, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(product, key, value)
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    from app.product_cache import invalidate_products_cache
    invalidate_products_cache()
    return product


class PushSubscriptionRequest(BaseModel):
    subscription: dict

class PushUnsubscribeRequest(BaseModel):
    endpoint: str

class OrderStatusRequest(BaseModel):
    status: str = Field(pattern="^(preparing|out_for_delivery|delivered)$")

@router.get("/orders", dependencies=[Depends(require_admin)])
def admin_orders(session: Session = Depends(get_session)):
    rows = session.exec(
        select(PaymentOrder).where(PaymentOrder.status == "paid").order_by(PaymentOrder.created_at.desc()).limit(200)
    ).all()
    result = []
    for order in rows:
        try:
            items = json.loads(order.items_json)
        except Exception:
            items = []
        try:
            address = json.loads(order.address_json)
        except Exception:
            address = {}
        result.append({
            "id": order.id,
            "razorpay_order_id": order.razorpay_order_id,
            "customer_name": order.customer_name or "Customer",
            "customer_phone": order.customer_phone or "",
            "address": address,
            "items": items,
            "amount_rupees": round(order.amount_paise / 100, 2),
            "delivery_status": order.delivery_status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "tracking_url": order.tracking_url,
        })
    return result

@router.patch("/orders/{razorpay_order_id}/status", dependencies=[Depends(require_admin)])
def update_order_status(razorpay_order_id: str, data: OrderStatusRequest, session: Session = Depends(get_session)):
    order = session.exec(select(PaymentOrder).where(PaymentOrder.razorpay_order_id == razorpay_order_id)).first()
    if not order or order.status != "paid":
        raise HTTPException(status_code=404, detail="Paid order not found")
    order.delivery_status = data.status
    session.add(order)
    session.commit()
    session.refresh(order)
    return {"success": True, "razorpay_order_id": order.razorpay_order_id, "delivery_status": order.delivery_status}

@router.get("/push/public-key", dependencies=[Depends(require_admin)])
def admin_push_public_key():
    key = get_public_key()
    if not key:
        raise HTTPException(status_code=503, detail="Push notifications are not configured on the API yet.")
    return {"public_key": key}

@router.post("/push/subscribe", dependencies=[Depends(require_admin)])
def admin_push_subscribe(data: PushSubscriptionRequest, session: Session = Depends(get_session)):
    try:
        save_subscription(session, data.subscription)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"success": True}

@router.post("/push/unsubscribe", dependencies=[Depends(require_admin)])
def admin_push_unsubscribe(data: PushUnsubscribeRequest, session: Session = Depends(get_session)):
    delete_subscription(session, data.endpoint)
    return {"success": True}
