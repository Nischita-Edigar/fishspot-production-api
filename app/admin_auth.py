import base64
import os
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Header, HTTPException

# Must remain identical to the signing secret used by admin login.
ADMIN_TOKEN_SECRET = os.getenv("ADMIN_TOKEN_SECRET", "").encode("utf-8")

if len(ADMIN_TOKEN_SECRET) < 32:
    raise RuntimeError("ADMIN_TOKEN_SECRET must contain at least 32 characters.")

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def require_admin(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin login required")
    token = authorization[7:].strip()
    try:
        payload_part, signature = token.split(".", 1)
        expected = _b64(
            hmac.new(ADMIN_TOKEN_SECRET, payload_part.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(
            base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4))
        )
        if payload.get("role") != "admin" or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Expired token")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Admin session expired. Please log in again.",
        )
    return True
