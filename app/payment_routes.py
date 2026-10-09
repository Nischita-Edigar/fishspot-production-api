
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, Session, SQLModel, select

from app.database import get_session
from app.models import Product
from app.uber_service import get_uber_delivery_quote

router = APIRouter(prefix="/payments", tags=["Payments"])

PACKING_FEE_PAISE = 500

PICKUP_ADDRESS = {
    "street_address": ["98 1st Cross Road"],
    "city": "Bengaluru",
    "state": "Karnataka",
    "zip_code": "560078",
    "country": "IN",
}


class PaymentOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    razorpay_order_id: str = Field(unique=True, index=True)
    amount_paise: int
    status: str = "created"
    items_json: str
    address_json: str
    delivery_quote_id: str
    payment_id: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CartLine(BaseModel):
    product_id: int
    quantity: int = PydanticField(ge=1, le=100)


class CreateOrderRequest(BaseModel):
    items: list[CartLine] = PydanticField(min_length=1)
    dropoff_address: dict[str, Any]
    dropoff_latitude: float
    dropoff_longitude: float


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def get_razorpay_keys():
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail="Payment gateway is not configured.",
        )

    return key_id, key_secret


@router.post("/create-order")
async def create_order(
    request: CreateOrderRequest,
    session: Session = Depends(get_session),
):
    key_id, key_secret = get_razorpay_keys()

    product_ids = {item.product_id for item in request.items}
    products = session.exec(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.is_active == True,
        )
    ).all()

    product_map = {product.id: product for product in products}

    if set(product_map) != product_ids:
        raise HTTPException(
            status_code=400,
            detail="One or more products are unavailable.",
        )

    subtotal_paise = 0
    order_items = []

    for item in request.items:
        product = product_map[item.product_id]
        price_paise = round(float(product.price) * 100)

        if price_paise <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid price for {product.name}.",
            )

        subtotal_paise += price_paise * item.quantity
        order_items.append({
            "product_id": item.product_id,
            "name": product.name,
            "quantity": item.quantity,
            "unit_price_paise": price_paise,
        })

    if not request.dropoff_address.get("zip_code"):
        raise HTTPException(
            status_code=400,
            detail="Delivery pincode is required.",
        )

    if not str(request.dropoff_address["zip_code"]).strip().startswith("560"):
        raise HTTPException(
            status_code=400,
            detail="Delivery is currently available only in Bangalore.",
        )

    try:
        quote = await get_uber_delivery_quote(
            pickup_address=PICKUP_ADDRESS,
            dropoff_address=request.dropoff_address,
            pickup_latitude=12.890616,
            pickup_longitude=77.582438,
            dropoff_latitude=request.dropoff_latitude,
            dropoff_longitude=request.dropoff_longitude,
        )

        if str(quote.get("currency", "")).lower() != "inr":
            raise HTTPException(
                status_code=502,
                detail="Uber returned an unsupported currency.",
            )

        delivery_fee_paise = int(quote["fee"])
        quote_id = quote.get("id")

        if delivery_fee_paise < 0 or not quote_id:
            raise ValueError("Invalid Uber delivery quote.")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Unable to confirm delivery charges. Please try again.",
        )

    total_paise = (
        subtotal_paise
        + delivery_fee_paise
        + PACKING_FEE_PAISE
    )

    receipt = f"fsm_{uuid.uuid4().hex[:20]}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(key_id, key_secret),
                json={
                    "amount": total_paise,
                    "currency": "INR",
                    "receipt": receipt,
                    "notes": {"source": "Fish Spot Malpe"},
                },
            )
            response.raise_for_status()
            razorpay_order = response.json()

        payment_order = PaymentOrder(
            razorpay_order_id=razorpay_order["id"],
            amount_paise=total_paise,
            status="created",
            items_json=json.dumps(order_items),
            address_json=json.dumps(request.dropoff_address),
            delivery_quote_id=str(quote_id),
        )

        session.add(payment_order)
        session.commit()

    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=502,
            detail="Could not create a payment order. Please try again.",
        )

    return {
        "key_id": key_id,
        "order_id": razorpay_order["id"],
        "amount": total_paise,
        "currency": "INR",
        "subtotal_paise": subtotal_paise,
        "delivery_fee_paise": delivery_fee_paise,
        "packing_fee_paise": PACKING_FEE_PAISE,
        "total_paise": total_paise,
    }


@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    session: Session = Depends(get_session),
):
    _, key_secret = get_razorpay_keys()

    payment_order = session.exec(
        select(PaymentOrder).where(
            PaymentOrder.razorpay_order_id
            == request.razorpay_order_id
        )
    ).first()

    if not payment_order:
        raise HTTPException(
            status_code=404,
            detail="Payment order not found.",
        )

    if payment_order.status == "paid":
        return {"verified": True, "paid": True}

    message = (
        f"{payment_order.razorpay_order_id}|"
        f"{request.razorpay_payment_id}"
    ).encode()

    expected_signature = hmac.new(
        key_secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        request.razorpay_signature,
    ):
        raise HTTPException(
            status_code=400,
            detail="Payment signature verification failed.",
        )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.razorpay.com/v1/payments/"
                + request.razorpay_payment_id,
                auth=get_razorpay_keys(),
            )
            response.raise_for_status()
            payment = response.json()

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Could not confirm payment status. Please retry.",
        )

    if payment.get("order_id") != payment_order.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Payment does not match this order.",
        )

    if int(payment.get("amount", 0)) != payment_order.amount_paise:
        raise HTTPException(
            status_code=400,
            detail="Payment amount does not match this order.",
        )

    payment_status = payment.get("status", "")

    payment_order.payment_id = request.razorpay_payment_id
    payment_order.status = (
        "paid" if payment_status == "captured"
        else payment_status or "pending"
    )
    session.add(payment_order)
    session.commit()

    return {
        "verified": True,
        "paid": payment_status == "captured",
        "status": payment_status,
    }
