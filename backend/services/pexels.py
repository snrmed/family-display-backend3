import os, json, hashlib, random, time, datetime as dt
from typing import Optional
import httpx

def weekly_key(today: dt.date) -> str:
    iso = today.isocalendar()
    return f"{today.year}-W{iso.week}"

def pick_curated_key(today: dt.date, theme: str, per_theme_count: int) -> str:
    # deterministic daily pick
    seed = int(today.strftime("%Y%m%d")) ^ hash(theme) & 0xFFFF
    idx = seed % max(1, per_theme_count)
    week = weekly_key(today)
    return f"images/{week}/{theme}/v_{idx}.png"

def ensure_cached_from_pexels(theme: str, api_key: str, today: dt.date, cache_read, cache_write) -> Optional[str]:
    """
    Queries Pexels once per day per theme, downloads one image, stores in GCS:
    cache/pexels/<YYYY-MM-DD>/<theme>/v_0.jpg
    Returns the GCS key or None on failure.
    """
    day = today.isoformat()
    base_key = f"cache/pexels/{day}/{theme}/v_0.jpg"
    if cache_read(base_key):  # already cached
        return base_key

    headers = {"Authorization": api_key}
    query = {
        "abstract":"abstract minimal gradient",
        "geometric":"geometric shapes minimal",
        "paper-collage":"paper collage texture",
        "kids-shapes":"colorful shapes kids",
        "minimal":"minimal texture"
    }.get(theme, theme)

    try:
        with httpx.Client(timeout=20) as cx:
            r = cx.get("https://api.pexels.com/v1/search", headers=headers, params={"query": query, "per_page": 10})
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos: return None
            # pick first landscape-ish
            url = photos[0]["src"].get("landscape") or photos[0]["src"].get("large")
            img = cx.get(url)
            img.raise_for_status()
            cache_write(base_key, img.content, "image/jpeg", cache="public, max-age=31536000")
            return base_key
    except Exception:
        return None
