import requests

class GeocodeError(Exception):
    pass

def geocode_place(place: str) -> tuple[float, float]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place, "format": "json", "limit": 1}
    headers = {"User-Agent": "mana-astrology-engine/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    if r.status_code != 200:
        raise GeocodeError(f"Geocoding failed: {r.status_code}")
    data = r.json()
    if not data:
        raise GeocodeError("Place not found")
    return float(data[0]["lat"]), float(data[0]["lon"])