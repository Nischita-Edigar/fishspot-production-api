import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"


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
        print("Google Places error:", response.status_code, response.text)
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
