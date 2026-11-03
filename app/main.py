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
from app import push_service  # noqa: F401
from app.product_routes import router as product_router
from app.twilio_service import send_otp, verify_otp
from app.location_service import search_places, calculate_driving_distance
from app.payment_routes import router as payment_router
from app.admin_routes import router as admin_router
from app.stock_routes import router as stock_router

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


class DeliveryDistanceRequest(BaseModel):
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)


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


@app.post("/delivery/distance")
async def delivery_distance(request: DeliveryDistanceRequest):
    # Fish Spot Malpe pickup coordinates.
    # Verify these coordinates point to the exact shop entrance before launch.
    shop_latitude = 12.890616
    shop_longitude = 77.582438

    try:
        result = await calculate_driving_distance(
            origin_lat=shop_latitude,
            origin_lng=shop_longitude,
            destination_lat=request.destination_latitude,
            destination_lng=request.destination_longitude,
        )

        return {
            "success": True,
            "distance_km": result["distance_km"],
            "distance_meters": result["distance_meters"],
            "duration": result["duration"],
            "delivery_fee": result["delivery_fee"],
        }
    except Exception:
        logger.exception("Driving distance calculation failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to calculate driving distance",
        )


app.include_router(product_router)
app.include_router(payment_router)
app.include_router(admin_router)
app.include_router(stock_router)
