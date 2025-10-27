import os, json, random, datetime as dt
from typing import Optional, List
import httpx

# ── Helper: key generator ────────────────────────────────────────────────
def weekly_key(today: dt.date) -> str:
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

# ── Query word mapping ───────────────────────────────────────────────────
_THEME_BASE = {
    "abstract": "abstract art shapes",
    "geometric": "geometric pattern texture",
    "paper-collage": "paper collage aesthetic",
    "kids-shapes": "colorful kids shapes fun",
    "minimal": "minimal background pastel"
}

_STYLE_VARIANTS = ["modern", "vivid", "texture", "flat", "bold", "minimal", "pastel", "retro", "soft", "clean"]

# ── Deep randomized weekly fetch ─────────────────────────────────────────
def prefetch_weekly_set(
    theme: str,
    api_key: str,
    per_theme_count: int,
    exists_fn,                  # (key) -> bool
    write_fn,                   # (key, bytes, content_type, cache) -> None
) -> List[str]:
    """
    Downloads a new randomized batch of Pexels images for /pexels/current/<theme>/.
    Old current batch should be rotated to /pexels/cache/ before this is called.
    Returns a list of new keys written.
    """
    base_query = _THEME_BASE.get(theme, theme)
    style_words = " ".join(random.sample(_STYLE_VARIANTS, k=2))
    query = f"{base_query} {style_words}"
    page = random.randint(1, int(os.getenv("PEXELS_RANDOM_DEPTH", "5")))

    headers = {"Authorization": api_key}
    out_keys: List[str] = []
    try:
        with httpx.Client(timeout=40) as cx:
            r = cx.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "orientation": "landscape", "per_page": per_theme_count * 2, "page": page},
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            random.shuffle(photos)
            photos = photos[: per_theme_count]
            for i, p in enumerate(photos):
                url = p["src"].get("landscape") or p["src"].get("large2x") or p["src"].get("large")
                if not url:
                    continue
                key = f"pexels/current/{theme}/v_{i}.jpg"
                if exists_fn(key):
                    continue
                img = cx.get(url)
                if img.status_code == 200 and img.content:
                    write_fn(key, img.content, "image/jpeg", cache="public, max-age=31536000")
                    out_keys.append(key)
    except Exception as e:
        print("Pexels prefetch error:", e)
    return out_keys

# ── Pick random file from current/cache ──────────────────────────────────
def pick_random_key(theme: str, per_theme_count: int, rand_ratio: float = 0.1) -> str:
    """
    Choose a random variant from pexels/current or pexels/cache.
    rand_ratio = chance of pulling from cache (0–1)
    """
    use_cache = random.random() < rand_ratio
    folder = "cache" if use_cache else "current"
    idx = random.randint(0, per_theme_count - 1)
    return f"pexels/{folder}/{theme}/v_{idx}.jpg"