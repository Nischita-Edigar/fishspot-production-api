
import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

UBER_TOKEN_URL = "https://auth.uber.com/oauth/v2/token"
UBER_QUOTE_URL = "https://api.uber.com/v1/customers/{customer_id}/delivery_quotes"
UBER_DELIVERY_URL = "https://api.uber.com/v1/customers/{customer_id}/deliveries"

_cached_token: str | None = None
_token_expires_at: float = 0


def _get_customer_id() -> str:
    customer_id = os.getenv("UBER_CUSTOMER_ID")
    if not customer_id:
        raise RuntimeError("UBER_CUSTOMER_ID is not configured.")
    return customer_id


async def get_uber_access_token() -> str:
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token

    client_id = os.getenv("UBER_CLIENT_ID")
    client_secret = os.getenv("UBER_CLIENT_SECRET")

    if not client_id:
        raise RuntimeError("UBER_CLIENT_ID is not configured.")
    if not client_secret:
        raise RuntimeError("UBER_CLIENT_SECRET is not configured.")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                UBER_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                    "scope": "eats.deliveries",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Uber authentication failed with HTTP %s.",
            exc.response.status_code,
        )
        raise RuntimeError("Uber authentication failed.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Uber authentication request failed.")
        raise RuntimeError("Unable to authenticate with Uber.") from exc

    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("Uber did not return an access token.")

    try:
        expires_in = int(data.get("expires_in", 3600))
    except (ValueError, TypeError):
        expires_in = 3600

    _cached_token = access_token
    _token_expires_at = time.time() + max(expires_in, 0)

    return access_token


def _serialize_address(address: dict[str, Any]) -> str:
    if not isinstance(address, dict):
        raise ValueError("Delivery address must be an object.")

    street_address = address.get("street_address")
    if isinstance(street_address, str):
        street_address = [street_address]

    if not isinstance(street_address, list) or not street_address:
        raise ValueError("Delivery address requires street_address.")

    required_fields = ("city", "state", "zip_code", "country")
    for field in required_fields:
        if not str(address.get(field, "")).strip():
            raise ValueError(f"Delivery address requires {field}.")

    normalized_address = {
        "street_address": [str(line) for line in street_address],
        "city": str(address["city"]),
        "state": str(address["state"]),
        "zip_code": str(address["zip_code"]),
        "country": str(address["country"]).upper(),
    }

    if address.get("unit"):
        normalized_address["street_address"].append(str(address["unit"]))

    return json.dumps(normalized_address, separators=(",", ":"))


async def _post_uber_request(
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = await get_uber_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Uber Direct request failed with HTTP %s.",
            exc.response.status_code,
        )
        raise RuntimeError(
            f"Uber Direct request failed with HTTP {exc.response.status_code}."
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Uber Direct request or response parsing failed.")
        raise RuntimeError("Unable to complete the Uber Direct request.") from exc

    if not isinstance(result, dict):
        raise RuntimeError("Uber Direct returned an invalid response.")

    return result


async def get_uber_delivery_quote(
    pickup_address: dict[str, Any],
    dropoff_address: dict[str, Any],
    pickup_latitude: float,
    pickup_longitude: float,
    dropoff_latitude: float,
    dropoff_longitude: float,
) -> dict[str, Any]:
    customer_id = _get_customer_id()
    url = UBER_QUOTE_URL.format(customer_id=customer_id)

    payload = {
        "pickup_address": _serialize_address(pickup_address),
        "dropoff_address": _serialize_address(dropoff_address),
        "pickup_latitude": float(pickup_latitude),
        "pickup_longitude": float(pickup_longitude),
        "dropoff_latitude": float(dropoff_latitude),
        "dropoff_longitude": float(dropoff_longitude),
    }

    quote = await _post_uber_request(url, payload)

    if not quote.get("id"):
        raise RuntimeError("Uber quote response did not contain a quote ID.")
    if quote.get("fee") is None:
        raise RuntimeError("Uber quote response did not contain a delivery fee.")

    return quote


async def create_uber_delivery(
    quote_id: str,
    external_order_id: str,
    pickup_address: dict[str, Any],
    dropoff_address: dict[str, Any],
    pickup_name: str,
    pickup_phone_number: str,
    dropoff_name: str,
    dropoff_phone_number: str,
    pickup_latitude: float,
    pickup_longitude: float,
    dropoff_latitude: float,
    dropoff_longitude: float,
    manifest_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    customer_id = _get_customer_id()

    if not quote_id:
        raise ValueError("Uber delivery quote ID is required.")
    if not external_order_id:
        raise ValueError("External order ID is required.")
    if not manifest_items:
        raise ValueError("At least one delivery manifest item is required.")

    normalized_items = []

    for item in manifest_items:
        if not isinstance(item, dict):
            raise ValueError("Invalid Uber delivery manifest item.")

        name = str(item.get("name", "")).strip()

        try:
            quantity = int(item.get("quantity", 0))
            price = int(item.get("price", -1))
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid manifest item quantity or price.") from exc

        if not name or quantity < 1 or price < 0:
            raise ValueError("Invalid manifest item name, quantity, or price.")

        normalized_items.append({
            "name": name,
            "quantity": quantity,
            "price": price,
        })

    url = UBER_DELIVERY_URL.format(customer_id=customer_id)

    payload = {
        "quote_id": quote_id,
        "pickup_address": _serialize_address(pickup_address),
        "pickup_name": pickup_name,
        "pickup_phone_number": str(pickup_phone_number),
        "pickup_latitude": float(pickup_latitude),
        "pickup_longitude": float(pickup_longitude),
        "dropoff_address": _serialize_address(dropoff_address),
        "dropoff_name": dropoff_name,
        "dropoff_phone_number": str(dropoff_phone_number),
        "dropoff_latitude": float(dropoff_latitude),
        "dropoff_longitude": float(dropoff_longitude),
        "external_order_id": external_order_id,
        "manifest_items": normalized_items,
    }

    delivery = await _post_uber_request(url, payload)

    delivery_id = (
        delivery.get("id")
        or delivery.get("delivery_id")
        or delivery.get("uuid")
    )

    if not delivery_id:
        raise RuntimeError(
            "Uber delivery response did not contain a delivery ID."
        )

    return delivery
