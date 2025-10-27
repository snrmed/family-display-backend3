import os, json, hashlib, time
from typing import Dict
import httpx

OW_API = "https://api.openweathermap.org/data/2.5"

def _hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:10]

def get_weather(city: str, units: str, api_key: str, cache_read, cache_write) -> Dict:
    """
    Returns: {"min": int, "max": int, "desc": str, "icon": "01d", "provider":"openweather"}
    Cache for ~60 minutes by city+units.
    """
    city_key = city.strip()
    cache_key = f"cache/weather/{_hash(city_key+'|'+units)}.json"
    # try cache
    j = cache_read(cache_key)
    if j:
        data = json.loads(j)
        # 60 min TTL
        if time.time() - data.get("_ts", 0) < 3600:
            return data["payload"]

    # 1) current weather (has desc & icon, also temp_min/max for many stations)
    params = {"q": city_key, "appid": api_key, "units": units, "lang": "en"}
    with httpx.Client(timeout=15) as cx:
        r = cx.get(f"{OW_API}/weather", params=params)
        r.raise_for_status()
        cur = r.json()

        desc = (cur["weather"][0]["description"] or "").capitalize()
        icon = cur["weather"][0]["icon"]  # "01d"
        main = cur.get("main", {})
        # Fallbacks if temp_min/max missing
        tmin = round(main.get("temp_min", main.get("temp", 0)))
        tmax = round(main.get("temp_max", main.get("temp", 0)))

    payload = {"min": tmin, "max": tmax, "desc": desc, "icon": icon, "provider": "openweather"}
    cache_write(cache_key, json.dumps({"_ts": time.time(), "payload": payload}).encode("utf-8"),
                "application/json", cache="public, max-age=3600")
    return payload
