import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")


def _get_client() -> Client:
    missing = [
        name for name, value in {
            "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
            "TWILIO_VERIFY_SERVICE_SID": TWILIO_VERIFY_SERVICE_SID,
        }.items() if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Twilio configuration: {', '.join(missing)}")
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_otp(phone_number: str):
    client = _get_client()
    verification = client.verify.v2.services(
        TWILIO_VERIFY_SERVICE_SID
    ).verifications.create(
        to=phone_number,
        channel="sms",
    )
    return verification.status


def verify_otp(phone_number: str, otp: str):
    client = _get_client()
    verification_check = client.verify.v2.services(
        TWILIO_VERIFY_SERVICE_SID
    ).verification_checks.create(
        to=phone_number,
        code=otp,
    )
    return verification_check.status
