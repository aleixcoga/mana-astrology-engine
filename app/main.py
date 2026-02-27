import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import NatalChartRequest, ErrorResponse
from app.geocode import geocode_place, GeocodeError
from app.timezone_resolver import tzid_from_latlon, TimezoneResolveError
from app.astrology import calculate_chart

app = FastAPI(
    title="MANA Astrology Engine",
    version="1.1.0"
)

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

@app.post("/natal-chart")
def natal_chart(req: NatalChartRequest):
    try:

        if not req.birth_time_local:
            return ErrorResponse(
                error="missing_time",
                message="birth_time_local is required for houses/ASC"
            ).model_dump()

        # 1️⃣ Geocoding si falta lat/lon
        lat, lon = req.lat, req.lon
        if lat is None or lon is None:
            lat, lon = geocode_place(req.birth_place)

        # 2️⃣ Resolver zona horaria
        tzid = req.tzid or tzid_from_latlon(float(lat), float(lon))

        # 3️⃣ Intentar con el sistema solicitado
        try:
            result = calculate_chart(
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
            return result

        except Exception as primary_error:

            # 4️⃣ Fallback automático a Equal si falla Placidus u otro sistema
            try:
                fallback_result = calculate_chart(
                    birth_date=req.birth_date,
                    birth_time_local=req.birth_time_local,
                    birth_place=req.birth_place,
                    lat=float(lat),
                    lon=float(lon),
                    tzid=tzid,
                    zodiac=req.zodiac,
                    house_system="Equal",
                    ayanamsa=req.ayanamsa,
                    aspects_sets=req.aspects,
                    time_is_approx=req.time_is_approx,
                    approx_minutes=req.approx_minutes,
                )

                fallback_result.setdefault("warnings", [])
                fallback_result["warnings"].append(
                    f"Primary house system '{req.house_system}' failed. Fallback applied: Equal."
                )

                return fallback_result

            except Exception as fallback_error:
                return ErrorResponse(
                    error="server_error",
                    message=f"Primary error: {str(primary_error)} | Fallback error: {str(fallback_error)}"
                ).model_dump()

    except (GeocodeError, TimezoneResolveError, ValueError) as e:
        return ErrorResponse(
            error="bad_request",
            message=str(e)
        ).model_dump()

    except Exception as e:
        return ErrorResponse(
            error="server_error",
            message=str(e)
        ).model_dump()
