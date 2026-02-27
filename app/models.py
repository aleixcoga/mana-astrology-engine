from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

HouseSystem = Literal["Placidus", "WholeSign", "Koch", "Equal"]
ZodiacType = Literal["Tropical", "Sidereal"]
AyanamsaType = Literal["None", "Lahiri", "FaganBradley", "Krishnamurti"]
AspectSet = Literal["Major", "Minor"]

class NatalChartRequest(BaseModel):
    birth_date: str = Field(..., description="YYYY-MM-DD")
    birth_time_local: Optional[str] = Field(None, description="HH:MM local time (24h). Required for houses/ASC.")
    time_is_approx: bool = False
    approx_minutes: int = 0
    birth_place: str = Field(..., description='e.g., "Santiago, Chile"')
    lat: Optional[float] = None
    lon: Optional[float] = None
    tzid: Optional[str] = Field(None, description="Optional IANA tz override, e.g., America/Santiago")
    house_system: HouseSystem = "Placidus"
    zodiac: ZodiacType = "Tropical"
    ayanamsa: AyanamsaType = "None"
    aspects: List[AspectSet] = ["Major"]

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None