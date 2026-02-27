from __future__ import annotations
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional
import swisseph as swe

EPHE_PATH = os.getenv("EPHE_PATH", "/app/ephe")
swe.set_ephe_path(EPHE_PATH)

HOUSE_SYS_MAP = {"Placidus": b"P", "Koch": b"K", "Equal": b"E"}  # WholeSign handled separately
SIGN_NAMES_ES = ["Aries","Tauro","Géminis","Cáncer","Leo","Virgo","Libra","Escorpio","Sagitario","Capricornio","Acuario","Piscis"]

ASPECTS_MAJOR = [("conjunction", 0), ("sextile", 60), ("square", 90), ("trine", 120), ("opposition", 180)]
ASPECTS_MINOR = [("quincunx", 150), ("semisquare", 45), ("sesquisquare", 135), ("quintile", 72)]

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
    "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "TrueNode": swe.TRUE_NODE, "MeanNode": swe.MEAN_NODE, "Chiron": swe.CHIRON, "Lilith": swe.MEAN_APOG,
}

def lon_to_sign(lon: float) -> tuple[str, float]:
    lon_norm = lon % 360.0
    i = int(lon_norm // 30)
    deg = lon_norm - i * 30
    return SIGN_NAMES_ES[i], round(deg, 2)

def _julday_utc(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)

def _set_sidereal(ayanamsa: str):
    if ayanamsa == "Lahiri":
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    elif ayanamsa == "FaganBradley":
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY, 0, 0)
    elif ayanamsa == "Krishnamurti":
        swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0, 0)

def _planet_lon(jd_ut: float, pid: int, zodiac: str, ayanamsa: str) -> tuple[float, bool]:
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if zodiac == "Sidereal":
        _set_sidereal(ayanamsa)
        flags |= swe.FLG_SIDEREAL
    lon, lat, dist, speed_lon = swe.calc_ut(jd_ut, pid, flags)[0]
    return float(lon), bool(speed_lon < 0)

def _aspects(planets: Dict[str, Dict[str, Any]], use_minor: bool) -> List[Dict[str, Any]]:
    asp_list = ASPECTS_MAJOR + (ASPECTS_MINOR if use_minor else [])
    names = list(planets.keys())
    out: List[Dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            a, b = names[i], names[j]
            la, lb = planets[a]["lon"], planets[b]["lon"]
            diff = abs((la - lb + 180) % 360 - 180)
            for asp_name, asp_deg in asp_list:
                orb = abs(diff - asp_deg)
                max_orb = 8 if asp_name in ["conjunction","opposition","square","trine"] else 6
                if orb <= max_orb:
                    out.append({"a": a, "b": b, "type": asp_name, "orb": round(orb, 2)})
                    break
    return out

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
) -> Dict[str, Any]:
    dt_local = datetime.strptime(f"{birth_date} {birth_time_local}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tzid))
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
    offset_minutes = int(dt_local.utcoffset().total_seconds() // 60)
    dst = bool(dt_local.dst() and dt_local.dst().total_seconds() != 0)
    jd_ut = _julday_utc(dt_utc)

    # Houses & angles
    if house_system == "WholeSign":
        cusps, ascmc = swe.houses_ex(jd_ut, swe.FLG_SWIEPH, lat, lon, HOUSE_SYS_MAP["Placidus"])
        asc_lon = float(ascmc[0]); mc_lon = float(ascmc[1])
        asc_sign, _ = lon_to_sign(asc_lon)
        asc_i = SIGN_NAMES_ES.index(asc_sign)
        houses = {}
        for i in range(1, 13):
            sign_i = (asc_i + i - 1) % 12
            cusp_lon = sign_i * 30.0
            s, deg = lon_to_sign(cusp_lon)
            houses[str(i)] = {"sign": s, "deg": 0.0, "lon": float(cusp_lon)}
        angles = {
            "asc": {"sign": lon_to_sign(asc_lon)[0], "deg": lon_to_sign(asc_lon)[1], "lon": asc_lon},
            "mc": {"sign": lon_to_sign(mc_lon)[0], "deg": lon_to_sign(mc_lon)[1], "lon": mc_lon},
        }
    else:
        hsys = HOUSE_SYS_MAP.get(house_system, HOUSE_SYS_MAP["Placidus"])
        cusps, ascmc = swe.houses_ex(jd_ut, swe.FLG_SWIEPH, lat, lon, hsys)
        asc_lon = float(ascmc[0]); mc_lon = float(ascmc[1])
        angles = {
            "asc": {"sign": lon_to_sign(asc_lon)[0], "deg": lon_to_sign(asc_lon)[1], "lon": asc_lon},
            "mc": {"sign": lon_to_sign(mc_lon)[0], "deg": lon_to_sign(mc_lon)[1], "lon": mc_lon},
        }
        houses = {}
        for i in range(1, 13):
            lon_i = float(cusps[i]); s, deg = lon_to_sign(lon_i)
            houses[str(i)] = {"sign": s, "deg": deg, "lon": lon_i}

    warnings: List[str] = []
    ephe_ok = True
    planets: Dict[str, Dict[str, Any]] = {}

    for name, pid in PLANET_IDS.items():
        try:
            lon_p, retro = _planet_lon(jd_ut, pid, zodiac, ayanamsa)
            s, deg = lon_to_sign(lon_p)
            planets[name] = {"sign": s, "deg": deg, "lon": lon_p, "retrograde": retro}
        except Exception as e:
            ephe_ok = False
            warnings.append(f"{name} unavailable: {type(e).__name__}: {str(e)}")

    use_minor = "Minor" in aspects_sets
    aspects = _aspects(planets, use_minor) if planets else []

    asc_deg = float(angles["asc"]["deg"])
    flags = {
        "time_approx": bool(time_is_approx),
        "asc_near_sign_boundary": bool(asc_deg <= 2.0 or asc_deg >= 28.0),
        "house_system_warning": bool(abs(lat) >= 66),
        "ephemeris_files_ok": bool(ephe_ok),
    }

    meta = {
        "place": birth_place, "lat": float(lat), "lon": float(lon),
        "tzid": tzid, "offset_minutes": offset_minutes, "dst": dst,
        "local_datetime": dt_local.isoformat(), "utc_datetime": dt_utc.isoformat(),
        "house_system": house_system, "zodiac": zodiac, "ayanamsa": ayanamsa,
        "ephe_path": EPHE_PATH,
    }

    return {"meta": meta, "angles": angles, "houses": houses, "planets": planets, "aspects": aspects, "flags": flags, "warnings": warnings}