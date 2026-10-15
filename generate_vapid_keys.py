"""Generate one VAPID key pair for Web Push. Keep the private output secret."""
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
private_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
public_raw = key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
public_key = base64.urlsafe_b64encode(public_raw).decode().rstrip("=")
private_key = base64.b64encode(private_pem).decode()
print("VAPID_PUBLIC_KEY=" + public_key)
print("VAPID_PRIVATE_KEY=base64:" + private_key)
print("VAPID_CLAIMS_EMAIL=mailto:fishspotmalpe@gmail.com")
