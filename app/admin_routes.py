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
