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

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("fishspot")


def get_cors_origins():
    raw = os.getenv(
        "CORS_ORIGINS",
        "https://fishspotmalpe.com,https://www.fishspotmalpe.com,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("Fish Spot Malpe API started")
    yield
    logger.info("Fish Spot Malpe API stopped")


app = FastAPI(
    title="
