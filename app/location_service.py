
import os
import math
import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

GOOGLE_AUTOCOMPLETE_URL = (
    "https://places.googleapis.com/v1/places:autocomplete"
)

GOOGLE_ROUTES_URL = (
    "https://routes.googleapis.com/directions/v2:computeRoutes"
)


# --------------------------------------------------
# GOOGLE PLACES AUTOCOMPLETE
# --------------------------------------------------

async def search_places(search_text: str):
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": (
            "suggestions.placePrediction.placeId,"
            "suggestions.placePrediction.text,"
            "suggestions.placePrediction.structuredFormat"
        ),
    }

    payload = {
        "input": search_text,
        "includedRegionCodes": ["in"],
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            GOOGLE_AUTOCOMPLETE_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        print(
            "GOOGLE PLACES ERROR:",
            response.status_code,
            response.text,
            flush=True,
        )
        raise RuntimeError("Google Places API request failed")

    data = response.json()
    suggestions = []

    for item in data.get("suggestions", []):
        prediction = item.get("placePrediction")

        if not prediction:
            continue

        text_data = prediction.get("text", {})

        suggestions.append({
            "place_id": prediction.get("placeId"),
            "description": text_data.get("text", ""),
        })

    return suggestions


# --------------------------------------------------
# GOOGLE MAPS DRIVING DISTANCE
# --------------------------------------------------

async def calculate_driving_distance(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
):
    """
    Calculate actual road distance using Google Routes API.

    Delivery charge:
    ₹10 per kilometre, rounded up to the next rupee.
    """

    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin_lat,
                    "longitude": origin_lng,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination_lat,
                    "longitude": destination_lng,
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                GOOGLE_ROUTES_URL,
                headers=headers,
                json=payload,
            )

        # Log Google's actual error response
        if response.status_code != 200:
            print(
                "GOOGLE ROUTES STATUS:",
                response.status_code,
                flush=True,
            )

            print(
                "GOOGLE ROUTES ERROR DETAILS:",
                response.text,
                flush=True,
            )

            raise RuntimeError(
                f"Google Routes API failed: {response.status_code}"
            )

        data = response.json()

        routes = data.get("routes", [])

        if not routes:
            print(
                "GOOGLE ROUTES RETURNED NO ROUTES:",
                data,
                flush=True,
            )
            raise RuntimeError("No driving route found")

        route = routes[0]

        distance_meters = route.get("distanceMeters")
        duration = route.get("duration")

        if distance_meters is None:
            raise RuntimeError("Driving distance unavailable")

        distance_km = distance_meters / 1000

        # ₹10 per kilometre, rounded up.
        delivery_fee = math.ceil(distance_km * 10)

        result = {
            "distance_meters": distance_meters,
            "distance_km": round(distance_km, 2),
            "duration": duration,
            "delivery_fee": delivery_fee,
        }

        print(
            "GOOGLE ROUTE SUCCESS:",
            result,
            flush=True,
        )

        return result

    except httpx.TimeoutException:
        print("GOOGLE ROUTES TIMEOUT", flush=True)
        raise RuntimeError("Google Routes API timed out")

    except httpx.RequestError as error:
        print(
            "GOOGLE ROUTES CONNECTION ERROR:",
            str(error),
            flush=True,
        )
        raise RuntimeError("Unable to connect to Google Routes API")
