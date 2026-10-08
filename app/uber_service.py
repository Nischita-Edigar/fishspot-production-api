import os
import time

import httpx


UBER_TOKEN_URL = "https://sandbox-login.uber.com/oauth/v2/token"
UBER_STORES_URL = "https://test-api.uber.com/v1/eats/deliveries/stores"


_cached_token: str | None = None
_token_expires_at: float = 0


async def get_uber_access_token() -> str:
    global _cached_token
    global _token_expires_at

    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token

    client_id = os.getenv("UBER_CLIENT_ID")
    client_secret = os.getenv("UBER_CLIENT_SECRET")

    if not client_id:
        raise RuntimeError(
            "UBER_CLIENT_ID is not configured."
        )

    if not client_secret:
        raise RuntimeError(
            "UBER_CLIENT_SECRET is not configured."
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:
        response = await client.post(
            UBER_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
                "scope": "eats.deliveries",
            },
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Uber authentication failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

    data = response.json()

    access_token = data.get("access_token")
    expires_in = int(
        data.get("expires_in", 0)
    )

    if not access_token:
        raise RuntimeError(
            "Uber did not return an access token."
        )

    _cached_token = access_token
    _token_expires_at = (
        time.time() + expires_in
    )

    return access_token


async def get_uber_stores(
    latitude: float,
    longitude: float,
) -> dict:
    token = await get_uber_access_token()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "pickup_at": 0,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:
        response = await client.get(
            UBER_STORES_URL,
            params=params,
            headers=headers,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Uber stores request failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

    return response.json()
