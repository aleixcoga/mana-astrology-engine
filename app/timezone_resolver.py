from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()

class TimezoneResolveError(Exception):
    pass

def tzid_from_latlon(lat: float, lon: float) -> str:
    tzid = _tf.timezone_at(lat=lat, lng=lon) or _tf.closest_timezone_at(lat=lat, lng=lon)
    if not tzid:
        raise TimezoneResolveError("Unable to resolve IANA timezone from coordinates")
    return tzid