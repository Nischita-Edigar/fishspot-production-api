async def get_uber_stores(
    latitude: float,
    longitude: float,
) -> dict:
    token = await get_uber_access_token()

    url = "https://api.uber.com/v1/eats/deliveries/stores"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "pickup_at": 0,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            params=params,
            headers=headers,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Uber stores request failed: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()
