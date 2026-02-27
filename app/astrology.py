from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Tuple
import swisseph as swe

ENGINE_VERSION = "v3-stable-robust"

EPHE_PATH = os.getenv("EPHE_PATH", "/app/ephe")
swe.set_ephe_path(EPHE_PATH)

HOUSE_SYS_MAP = {
    "Placidus": b"P",
    "Koch": b"K",
    "Equal": b"E"
}

SIGN_NAMES = [
    "Aries","Tauro","Géminis","Cáncer","Leo","Virgo",
    "Libra","Escorpio","Sagitario","Capricornio","Acuario","Piscis"
]

PLANET_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "TrueNode": swe.TRUE_NODE,
    "MeanNode": swe.MEAN_NODE,
    "Chiron": swe.CHIRON,
    "Lilith": swe.MEAN_APOG,
}

ASPECTS = [
    ("conjunction", 0, 8),
    ("sextile", 60, 6),
    ("square", 90, 8),
    ("trine", 120, 8),
    ("opposition", 180, 8),
]

def lon_to_sign(lon: float) -> Tuple[str, float]:
    lon = lon % 360
    sign_index = int(lon // 30)
    deg = lon - sign_index * 30
    return SIGN_NAMES[sign_index], round(deg, 2)

def julday_utc(dt_utc: datetime) -> float:
    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    )

def safe_calc_ut(jd_ut: float, planet_id: int):
    """
    Robust version compatible with pyswisseph return shape.
    """
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    xx, retflag = swe.calc_ut(jd_ut, planet_id, flags)
    xx = list(xx)
    lon = float(xx[0])
    speed = float(xx[3]) if len(xx) > 3 else 0.0
    retro = speed < 0
    return lon, retro

def normalize_cusps(cusps_raw):
    cusps = list(cusps_raw)

    if len(cusps) == 13:
        return cusps
    elif len(cusps) == 12:
        return [0.0] + cusps
    else:
        raise RuntimeError(f"Unexpected cusps length: {len(cusps)}")

def build_houses(cusps_13):
    houses = {}
    for i in range(1, 13):
        lon = float(cusps_13[i])
        sign, deg = lon_to_sign(lon)
        houses[str(i)] = {
            "sign": sign,
            "deg": deg,
            "lon": lon
        }
    return houses

def calculate_chart(
    birth_date: str,
    birth_time_local: str,
    birth_place: str,
    lat: float,
    lon: float,
    tzid: str,
    zodiac: str,
    house_system: str,
    ayanamsa: str,
    aspects_sets: List[str],
    time_is_approx: bool,
    approx_minutes: int,
):

    dt_local = datetime.strptime(
        f"{birth_date} {birth_time_local}",
        "%Y-%m-%d %H:%M"
    ).replace(tzinfo=ZoneInfo(tzid))

    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
    jd_ut = julday_utc(dt_utc)

    warnings = []
    ephe_ok = True

    # Houses and angles
    try:
        hsys = HOUSE_SYS_MAP.get(house_system, b"P")
        cusps_raw, ascmc = swe.houses_ex(
            jd_ut,
            lat,
            lon,
            hsys,
            swe.FLG_SWIEPH
        )

        cusps_13 = normalize_cusps(cusps_raw)
        houses = build_houses(cusps_13)

        asc_lon = float(ascmc[0])
        mc_lon = float(ascmc[1])

    except Exception as e:
        raise RuntimeError(f"Houses calculation failed: {str(e)}")

    angles = {
        "asc": {
            "sign": lon_to_sign(asc_lon)[0],
            "deg": lon_to_sign(asc_lon)[1],
            "lon": asc_lon
        },
        "mc": {
            "sign": lon_to_sign(mc_lon)[0],
            "deg": lon_to_sign(mc_lon)[1],
            "lon": mc_lon
        }
    }

    # Planets
    planets = {}

    for name, pid in PLANET_IDS.items():
        try:
            lon_p, retro = safe_calc_ut(jd_ut, pid)
            sign, deg = lon_to_sign(lon_p)
            planets[name] = {
                "sign": sign,
                "deg": deg,
                "lon": lon_p,
                "retrograde": retro
            }
        except Exception as e:
            ephe_ok = False
            warnings.append(f"{name} unavailable: {str(e)}")

    # Aspects
    aspects = []
    planet_names = list(planets.keys())

    for i in range(len(planet_names)):
        for j in range(i + 1, len(planet_names)):
            p1 = planet_names[i]
            p2 = planet_names[j]
            lon1 = planets[p1]["lon"]
            lon2 = planets[p2]["lon"]
            diff = abs((lon1 - lon2 + 180) % 360 - 180)

            for asp_name, asp_deg, max_orb in ASPECTS:
                orb = abs(diff - asp_deg)
                if orb <= max_orb:
                    aspects.append({
                        "a": p1,
                        "b": p2,
                        "type": asp_name,
                        "orb": round(orb, 2)
                    })
                    break

    flags = {
        "ephemeris_files_ok": ephe_ok,
        "engine_version": ENGINE_VERSION
    }

    meta = {
        "place": birth_place,
        "lat": lat,
        "lon": lon,
        "tzid": tzid,
        "local_datetime": dt_local.isoformat(),
        "utc_datetime": dt_utc.isoformat(),
        "house_system": house_system,
        "zodiac": zodiac,
        "engine_version": ENGINE_VERSION
    }

    return {
        "meta": meta,
        "angles": angles,
        "houses": houses,
        "planets": planets,
        "aspects": aspects,
        "flags": flags,
        "warnings": warnings
    }
