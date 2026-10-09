
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, Session, SQLModel, select

from app.database import get_session
from app.models import Product
from app.uber_service import (
    create_uber_delivery,
    get_uber_delivery_quote,
)

router = APIRouter(prefix="/payments", tags=["Payments"])

PACKING_FEE_PAISE = 500

PICKUP_ADDRESS = {
    "street_address": ["98 1st Cross Road"],
    "city": "Bengaluru",
    "state": "Karnataka",
    "zip_code": "560078",
    "country": "IN",
}

PICKUP_LATITUDE = 12.890616
PICKUP_LONGITUDE = 77.582438


class PaymentOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    razorpay_order_id: str = Field(unique=True, index=True)
    amount_paise: int
    status: str = "created"
    items_json: str
    address_json: str
    delivery_quote_id: str
    customer_name: str | None = Field(default=None, max_length=120)
    customer_phone: str | None = Field(default=None, max_length=20)
    payment_id: str | None = None
    delivery_id: str | None = Field(default=None, index=True)
    tracking_url: str | None = None
    delivery_status: str = "not_created"
    dropoff_latitude: float | None = None
    dropoff_longitude: float | None = None
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
    customer_name: str = PydanticField(min_length=1, max_length=120)
    customer_phone: str = PydanticField(min_length=10, max_length=20)


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def get_razorpay_keys() -> tuple[str, str]:
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

    customer_name = request.customer_name.strip()
    customer_phone = re.sub(r"\D", "", request.customer_phone)[-10:]

    if not customer_name:
        raise HTTPException(
            status_code=400,
            detail="Customer name is required.",
        )

    if not re.fullmatch(r"[6-9]\d{9}", customer_phone):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid 10-digit Indian mobile number.",
        )

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

    zip_code = str(
        request.dropoff_address.get("zip_code", "")
    ).strip()

    if not zip_code:
        raise HTTPException(
            status_code=400,
            detail="Delivery pincode is required.",
        )

    if not zip_code.startswith("560"):
        raise HTTPException(
            status_code=400,
            detail="Delivery is currently available only in Bangalore.",
        )

    try:
        quote = await get_uber_delivery_quote(
            pickup_address=PICKUP_ADDRESS,
            dropoff_address=request.dropoff_address,
            pickup_latitude=PICKUP_LATITUDE,
            pickup_longitude=PICKUP_LONGITUDE,
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
                    "notes": {
                        "source": "Fish Spot Malpe",
                        "customer_name": customer_name,
                        "customer_phone": customer_phone,
                    },
                },
            )
            response.raise_for_status()
            razorpay_order = response.json()

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not create a payment order. Please try again.",
        )

    payment_order = PaymentOrder(
        razorpay_order_id=razorpay_order["id"],
        amount_paise=total_paise,
        status="created",
        items_json=json.dumps(order_items),
        address_json=json.dumps(request.dropoff_address),
        delivery_quote_id=str(quote_id),
        customer_name=customer_name,
        customer_phone=customer_phone,
        dropoff_latitude=request.dropoff_latitude,
        dropoff_longitude=request.dropoff_longitude,
    )

    try:
        session.add(payment_order)
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "The payment order could not be saved. "
                "Please contact support before retrying payment."
            ),
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
                auth=(os.getenv("RAZORPAY_KEY_ID"), key_secret),
            )
            response.raise_for_status()
            payment = response.json()

    except httpx.HTTPError:
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

    if (
        payment_order.payment_id
        and payment_order.payment_id != request.razorpay_payment_id
    ):
        raise HTTPException(
            status_code=400,
            detail="This order is already linked to another payment.",
        )

    payment_status = payment.get("status", "")

    if payment_status != "captured":
        payment_order.status = payment_status or "pending"
        session.add(payment_order)
        session.commit()

        return {
            "verified": True,
            "paid": False,
            "status": payment_status or "pending",
            "delivery_status": payment_order.delivery_status,
            "tracking_url": payment_order.tracking_url,
        }

    payment_order.payment_id = request.razorpay_payment_id
    payment_order.status = "paid"
    session.add(payment_order)
    session.commit()
    session.refresh(payment_order)

    # Only start delivery creation for orders that have not started it.
    # A stuck "creating" status must be reconciled before retrying.
    if payment_order.delivery_status == "not_created":
        payment_order.delivery_status = "creating"
        session.add(payment_order)
        session.commit()

        try:
            if (
                payment_order.dropoff_latitude is None
                or payment_order.dropoff_longitude is None
            ):
                raise RuntimeError(
                    "Saved delivery coordinates are missing."
                )

            pickup_phone = os.getenv("UBER_PICKUP_PHONE")
            if not pickup_phone:
                raise RuntimeError(
                    "UBER_PICKUP_PHONE is not configured."
                )

            items = json.loads(payment_order.items_json)
            address = json.loads(payment_order.address_json)

            manifest_items = [
                {
                    "name": item["name"],
                    "quantity": item["quantity"],
                    "price": item["unit_price_paise"],
                }
                for item in items
            ]

            delivery = await create_uber_delivery(
                quote_id=payment_order.delivery_quote_id,
                external_order_id=payment_order.razorpay_order_id,
                pickup_address=PICKUP_ADDRESS,
                dropoff_address=address,
                pickup_name=os.getenv(
                    "UBER_PICKUP_NAME", "Fish Spot Malpe"
                ),
                pickup_phone_number=pickup_phone,
                dropoff_name=payment_order.customer_name or "Customer",
                dropoff_phone_number=(
                    "+91" + (payment_order.customer_phone or "")
                ),
                pickup_latitude=PICKUP_LATITUDE,
                pickup_longitude=PICKUP_LONGITUDE,
                dropoff_latitude=payment_order.dropoff_latitude,
                dropoff_longitude=payment_order.dropoff_longitude,
                manifest_items=manifest_items,
            )

            delivery_id = (
                delivery.get("id")
                or delivery.get("delivery_id")
                or delivery.get("uuid")
            )
            tracking_url = (
                delivery.get("tracking_url")
                or delivery.get("order_tracking_url")
            )

            if not delivery_id:
                raise RuntimeError(
                    "Uber response did not contain a delivery ID."
                )

            payment_order.delivery_id = str(delivery_id)
            payment_order.tracking_url = tracking_url
            payment_order.delivery_status = str(
                delivery.get("status")
                or delivery.get("state")
                or "created"
            ).lower()

        except Exception:
            # Payment remains paid. Do not automatically resubmit an
            # ambiguous delivery request because Uber may have accepted it.
            payment_order.delivery_status = "creation_failed"

        session.add(payment_order)
        session.commit()
        session.refresh(payment_order)

    return {
        "verified": True,
        "paid": True,
        "status": "captured",
        "delivery_id": payment_order.delivery_id,
        "tracking_url": payment_order.tracking_url,
        "delivery_status": payment_order.delivery_status,
    }
