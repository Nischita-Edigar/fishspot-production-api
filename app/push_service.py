import json
import base64
import logging
import os
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Session, select

logger = logging.getLogger("fishspot.push")

class AdminPushSubscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    endpoint: str = Field(unique=True, index=True)
    subscription_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

def get_public_key() -> str:
    return os.getenv("VAPID_PUBLIC_KEY", "")

def save_subscription(session: Session, subscription: dict):
    endpoint = subscription.get("endpoint")
    if not endpoint or not isinstance(subscription.get("keys"), dict):
        raise ValueError("Invalid push subscription")
    row = session.exec(select(AdminPushSubscription).where(AdminPushSubscription.endpoint == endpoint)).first()
    if row is None:
        row = AdminPushSubscription(endpoint=endpoint, subscription_json=json.dumps(subscription))
    else:
        row.subscription_json = json.dumps(subscription)
    session.add(row)
    session.commit()

def delete_subscription(session: Session, endpoint: str):
    row = session.exec(select(AdminPushSubscription).where(AdminPushSubscription.endpoint == endpoint)).first()
    if row:
        session.delete(row)
        session.commit()

def send_admin_push(session: Session, payload: dict):
    public_key = os.getenv("VAPID_PUBLIC_KEY", "")
    private_key = os.getenv("VAPID_PRIVATE_KEY", "")
    if private_key.startswith("base64:"):
        try:
            private_key = base64.b64decode(private_key[7:]).decode("utf-8")
        except Exception:
            logger.exception("VAPID_PRIVATE_KEY is not valid base64-encoded PEM")
            return
    email = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@fishspotmalpe.com")
    if not public_key or not private_key:
        logger.warning("Admin push is not configured; set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY")
        return
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.exception("pywebpush dependency is missing")
        return
    rows = session.exec(select(AdminPushSubscription)).all()
    for row in rows:
        try:
            webpush(subscription_info=json.loads(row.subscription_json), data=json.dumps(payload), vapid_private_key=private_key, vapid_claims={"sub": email})
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                session.delete(row)
            logger.warning("Push delivery failed for subscription %s: %s", row.id, exc)
    session.commit()
