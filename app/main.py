import os
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

from app.models import NatalChartRequest, ErrorResponse
from app.geocode import geocode_place, GeocodeError
from app.timezone_resolver import tzid_from_latlon, TimezoneResolveError
from app.astrology import calculate_chart

app = FastAPI(title="MANA Astrology Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/natal-chart", responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
def natal_chart(req: NatalChartRequest):
    try:
        if not req.birth_time_local:
            return ErrorResponse(error="missing_time", message="birth_time_local is required for houses/ASC").model_dump()

        lat, lon = req.lat, req.lon
        if lat is None or lon is None:
            lat, lon = geocode_place(req.birth_place)

        tzid = req.tzid or tzid_from_latlon(float(lat), float(lon))

        return calculate_chart(
            birth_date=req.birth_date,
            birth_time_local=req.birth_time_local,
            birth_place=req.birth_place,
            lat=float(lat),
            lon=float(lon),
            tzid=tzid,
            zodiac=req.zodiac,
            house_system=req.house_system,
            ayanamsa=req.ayanamsa,
            aspects_sets=req.aspects,
            time_is_approx=req.time_is_approx,
            approx_minutes=req.approx_minutes,
        )

    except (GeocodeError, TimezoneResolveError, ValueError) as e:
        return ErrorResponse(error="bad_request", message=str(e)).model_dump()
    except Exception as e:
        return ErrorResponse(error="server_error", message=str(e)).model_dump()

ENABLE_TEST_ENDPOINTS = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"

@app.post("/find-asc-boundary")
def find_asc_boundary(
    birth_date: str = Body(..., embed=True),
    birth_place: str = Body(..., embed=True),
    zodiac: str = Body("Tropical", embed=True),
    house_system: str = Body("Placidus", embed=True),
    step_minutes: int = Body(5, embed=True),
):
    if not ENABLE_TEST_ENDPOINTS:
        return ErrorResponse(error="disabled", message="Set ENABLE_TEST_ENDPOINTS=true to enable.").model_dump()

    lat, lon = geocode_place(birth_place)
    tzid = tzid_from_latlon(float(lat), float(lon))
    start = datetime.strptime("00:00", "%H:%M")

    for i in range(0, 1440, max(1, step_minutes)):
        tm = (start + timedelta(minutes=i)).strftime("%H:%M")
        r = calculate_chart(birth_date, tm, birth_place, float(lat), float(lon), tzid, zodiac, house_system, "None", ["Major"], False, 0)
        deg = float(r["angles"]["asc"]["deg"])
        if deg <= 2 or deg >= 28:
            return {"found": True, "mode": "near_boundary", "tzid": tzid, "time_local": tm, "asc": r["angles"]["asc"], "flags": r["flags"], "warnings": r.get("warnings", [])}

    for i in range(0, 1439):
        tm1 = (start + timedelta(minutes=i)).strftime("%H:%M")
        tm2 = (start + timedelta(minutes=i+1)).strftime("%H:%M")
        r1 = calculate_chart(birth_date, tm1, birth_place, float(lat), float(lon), tzid, zodiac, house_system, "None", ["Major"], False, 0)
        r2 = calculate_chart(birth_date, tm2, birth_place, float(lat), float(lon), tzid, zodiac, house_system, "None", ["Major"], False, 0)
        if r1["angles"]["asc"]["sign"] != r2["angles"]["asc"]["sign"]:
            return {"found": True, "mode": "sign_change", "tzid": tzid, "time_local": tm1, "asc": r1["angles"]["asc"], "next_minute_asc": r2["angles"]["asc"], "warnings": list(set(r1.get("warnings", []) + r2.get("warnings", [])))}

    return {"found": False, "tzid": tzid}
