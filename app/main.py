```python
import os
import re
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import check_database_connection, create_db_and_tables
from app import models  # noqa: F401
from app.product_routes import router as product_router
from app.twilio_service import send_otp, verify_otp
from app.location_service import search_places
from app.payment_routes import router as payment_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fishspot")


def get_cors_origins():
    raw = os.getenv(
        "CORS_ORIGINS",
        "https://fishspotmalpe.com,https://www.fishspotmalpe.com,"
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Fish Spot Malpe API")
    create_db_and_tables()
    logger.info("Database tables initialized")
    yield
    logger.info("Fish Spot Malpe API stopped")


app = FastAPI(
    title="Fish Spot Malpe API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SendOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)


class VerifyOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    otp: str = Field(min_length=4, max_length=8)


def normalize_indian_phone(phone_number: str) -> str:
    value = phone_number.strip().replace(" ", "").replace("-", "")

    if re.fullmatch(r"\d{10}", value):
        return "+91" + value

    if re.fullmatch(r"\+91\d{10}", value):
        return value

    raise HTTPException(
        status_code=422,
        detail="Enter a valid Indian mobile number",
    )


@app.get("/")
def home():
    return {
        "message": "Fish Spot Malpe backend is running",
        "version": app.version,
    }


@app.get("/health")
def health():
    try:
        check_database_connection()
        return {"status": "ok", "database": "ok"}
    except Exception:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )


@app.post("/auth/send-otp")
def send_otp_endpoint(request: SendOtpRequest):
    phone_number = normalize_indian_phone(request.phone_number)

    try:
        status = send_otp(phone_number)
        return {
            "message": "OTP sent successfully",
            "status": status,
        }
    except Exception:
        logger.exception("OTP sending failed")
        raise HTTPException(
            status_code=400,
            detail="Unable to send OTP",
        )


@app.post("/auth/verify-otp")
def verify_otp_endpoint(request: VerifyOtpRequest):
    phone_number = normalize_indian_phone(request.phone_number)

    try:
        status = verify_otp(phone_number, request.otp)
        verified = status == "approved"

        return {
            "message": (
                "OTP verified successfully"
                if verified
                else "Invalid OTP"
            ),
            "verified": verified,
        }
    except Exception:
        logger.exception("OTP verification failed")
        raise HTTPException(
            status_code=400,
            detail="Unable to verify OTP",
        )


@app.get("/location/search")
async def location_search(q: str):
    q = q.strip()

    if len(q) < 3:
        return {"suggestions": []}

    try:
        suggestions = await search_places(q)
        return {"suggestions": suggestions}
    except Exception:
        logger.exception("Location search failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to search locations",
        )


@app.get("/uber/test")
async def uber_test():
    from app.uber_service import get_uber_access_token

    try:
        token = await get_uber_access_token()

        return {
            "success": True,
            "message": "Uber authentication successful",
            "token_received": bool(token),
        }
    except Exception:
        logger.exception("Uber authentication test failed")
        raise HTTPException(
            status_code=502,
            detail="Uber authentication failed; check server logs",
        )


@app.post("/uber/quote")
async def uber_quote(data: dict):
    from app.uber_service import get_uber_delivery_quote

    pickup_address = {
        "street_address": ["98 1st Cross Road"],
        "city": "Bengaluru",
        "state": "Karnataka",
        "zip_code": "560078",
        "country": "IN",
    }

    dropoff_address = data.get("dropoff_address")
    dropoff_latitude = data.get("dropoff_latitude")
    dropoff_longitude = data.get("dropoff_longitude")

    if not isinstance(dropoff_address, dict):
        raise HTTPException(
            status_code=422,
            detail="A valid dropoff_address object is required.",
        )

    if dropoff_latitude is None or dropoff_longitude is None:
        raise HTTPException(
            status_code=422,
            detail="Dropoff latitude and longitude are required.",
        )

    try:
        latitude = float(dropoff_latitude)
        longitude = float(dropoff_longitude)

        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude is out of range")

        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude is out of range")

        quote = await get_uber_delivery_quote(
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            pickup_latitude=12.890616,
            pickup_longitude=77.582438,
            dropoff_latitude=latitude,
            dropoff_longitude=longitude,
        )

        return {
            "success": True,
            "quote": quote,
        }
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="Dropoff coordinates must be valid numbers.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Uber delivery quote failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Uber delivery quote.",
        )


@app.post("/uber/delivery/test")
async def uber_delivery_test():
    from app.uber_service import (
        get_uber_delivery_quote,
        create_uber_delivery,
    )

    pickup_address = {
        "street_address": ["98 1st Cross Road"],
        "city": "Bengaluru",
        "state": "Karnataka",
        "zip_code": "560078",
        "country": "IN",
    }

    dropoff_address = {
        "street_address": ["98 1st Cross Road"],
        "city": "Bengaluru",
        "state": "Karnataka",
        "zip_code": "560078",
        "country": "IN",
    }

    pickup_latitude = 12.890616
    pickup_longitude = 77.582438
    dropoff_latitude = 12.890616
    dropoff_longitude = 77.582438

    try:
        quote = await get_uber_delivery_quote(
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            dropoff_latitude=dropoff_latitude,
            dropoff_longitude=dropoff_longitude,
        )

        quote_id = quote.get("id")

        if not quote_id:
            raise RuntimeError("Uber quote did not return a quote ID.")

        delivery = await create_uber_delivery(
            quote_id=quote_id,
            external_order_id="FISHSPOT-TEST-001",
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            pickup_name="Fish Spot Malpe",
            pickup_phone_number="+919876543210",
            dropoff_name="Test Customer",
            dropoff_phone_number="+919008401064",
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            dropoff_latitude=dropoff_latitude,
            dropoff_longitude=dropoff_longitude,
        )

        return {
            "success": True,
            "quote": quote,
            "delivery": delivery,
        }
    except Exception:
        logger.exception("Uber test delivery failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to create Uber test delivery; check server logs.",
        )


app.include_router(product_router)
app.include_router(payment_router)
```
