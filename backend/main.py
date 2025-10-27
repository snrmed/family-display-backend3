# backend/main.py
import os
import io
import json
import random
import datetime as dt
from typing import Optional, List, Dict

import httpx
from fastapi import FastAPI, Query, HTTPException, Response, Request, Path
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------- ENV / CONFIG ----------
PROJECT_NAME = "Kin:D / Family Display Backend"
DEFAULT_DEVICE_ID = os.getenv("DEFAULT_DEVICE_ID", "familydisplay")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
if not PUBLIC_BASE_URL:
    # Try to infer from Cloud Run injected var (for local dev you can leave blank)
    PUBLIC_BASE_URL = os.getenv("K_SERVICE_URL", "").rstrip("/") or "http://localhost:8000"

TIMEZONE = os.getenv("TIMEZONE", "Australia/Adelaide")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin, AU")
DEFAULT_UNITS = os.getenv("DEFAULT_UNITS", "metric")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
THEMES = os.getenv("THEMES", "abstract,geometric,paper-collage,kids-shapes,minimal")
PER_THEME_COUNT = int(os.getenv("PER_THEME_COUNT", "8"))

GCS_BUCKET = os.getenv("GCS_BUCKET", "")
FONT_DIR = os.getenv("FONT_DIR", "./backend/web/designer/fonts")

# ---------- OPTIONAL GCS ----------
storage_enabled = False
bucket = None
try:
    if GCS_BUCKET:
        from google.cloud import storage as gcs

        gcs_client = gcs.Client()
        bucket = gcs_client.bucket(GCS_BUCKET)
        storage_enabled = True
except Exception:
    storage_enabled = False
    bucket = None

def gcs_write_bytes(key: str, data: bytes, content_type: str, cache: str = "public, max-age=3600"):
    if not storage_enabled:
        return
    blob = bucket.blob(key)
    blob.cache_control = cache
    blob.upload_from_string(data, content_type=content_type)

def gcs_read_bytes(key: str) -> bytes:
    if not storage_enabled:
        raise HTTPException(500, "Storage not configured")
    blob = bucket.blob(key)
    if not blob.exists():
        raise HTTPException(404, f"Asset not found: {key}")
    return blob.download_as_bytes()

def gcs_exists(key: str) -> bool:
    if not storage_enabled:
        return False
    return bucket.blob(key).exists()

def gcs_list(prefix: str) -> List[str]:
    if not storage_enabled:
        return []
    return [b.name for b in bucket.list_blobs(prefix=prefix)]

def gcs_copy(src: str, dst: str):
    if not storage_enabled:
        return
    sb = bucket.blob(src)
    if sb.exists():
        bucket.copy_blob(sb, bucket, dst)

def gcs_delete_prefix(prefix: str):
    if not storage_enabled:
        return
    for b in bucket.list_blobs(prefix=prefix):
        b.delete()

# ---------- PLAYWRIGHT (headless Chromium) ----------
from playwright.sync_api import sync_playwright

def _take_element_screenshot(url: str, selector: str, width: int, height: int) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(selector, state="visible", timeout=15_000)
        element = page.query_selector(selector)
        if not element:
            browser.close()
            raise HTTPException(500, f"Selector not found: {selector}")
        data = element.screenshot(type="png")
        browser.close()
        return data

# ---------- RENDER + STORE LATEST (helper used by admin endpoints) ----------
def _render_and_store_latest(device: str, layout: str = "base") -> bytes:
    layout_url = (
        f"{PUBLIC_BASE_URL}/web/layouts/{layout}.html"
        f"?mode=render&device={device}&backend={PUBLIC_BASE_URL}"
    )
    png = _take_element_screenshot(layout_url, selector="#canvas", width=800, height=480)
    if storage_enabled:
        latest_key = f"renders/{device}/latest.png"
        gcs_write_bytes(latest_key, png, "image/png", cache="no-cache")
    return png

# ---------- FASTAPI ----------
app = FastAPI(title=PROJECT_NAME, version="2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- SIMPLE DATA PROVIDERS (weather / joke) ----------
async def get_weather(city: str, units: str) -> Dict:
    """Very small OpenWeather wrapper with a friendly fallback."""
    api = os.getenv("OPENWEATHER_API_KEY", "")
    if not api:
        # Fallback / stub (keeps layout working)
        return {
            "provider": "stub",
            "city": city,
            "units": units,
            "temp_min": 27,
            "temp_max": 34,
            "condition": "Sunny",
            "icon": "01d",
        }
    params = {"q": city, "appid": api, "units": units}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
        r.raise_for_status()
        j = r.json()
    main = j.get("main", {})
    weather0 = (j.get("weather") or [{}])[0]
    return {
        "provider": "openweather",
        "city": city,
        "units": units,
        "temp_min": int(main.get("temp_min", 0)),
        "temp_max": int(main.get("temp_max", 0)),
        "condition": weather0.get("main", "—"),
        "icon": weather0.get("icon", "01d"),
    }

async def get_joke() -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://icanhazdadjoke.com/", headers={"Accept": "text/plain"})
            if r.status_code == 200 and r.text:
                return r.text.strip()
    except Exception:
        pass
    return "I told my wife she should embrace her mistakes — she gave me a hug."

# ---------- PEXELS UTILS ----------
PEXELS_THEME_QUERIES = {
    "abstract": ["abstract texture", "fluid gradient", "colorful shapes"],
    "geometric": ["geometric pattern", "polygon background", "line pattern"],
    "paper-collage": ["paper collage background", "ripped paper texture"],
    "kids-shapes": ["colorful shapes background", "playful blobs"],
    "minimal": ["minimal gradient background", "soft gradient"],
}

def pexels_pick(theme: str) -> Optional[str]:
    """Return a GCS key to a random image, preferring current over cache."""
    choices = []
    cur = gcs_list(f"pexels/current/{theme}/")
    if cur:
        choices.extend(cur)
    cache = gcs_list(f"pexels/cache/{theme}/")
    if cache:
        # small probability from cache for variety
        choices.extend(cache[: max(1, len(cache)//5)])
    choices = [k for k in choices if k.endswith(".jpg")]
    if not choices:
        return None
    return random.choice(choices)

def rotate_current_to_cache(theme: str):
    # wipe old cache
    gcs_delete_prefix(f"pexels/cache/{theme}/")
    # copy current → cache
    for k in gcs_list(f"pexels/current/{theme}/"):
        if k.endswith(".jpg"):
            dst = k.replace("pexels/current/", "pexels/cache/")
            gcs_copy(k, dst)
    # wipe current for refill
    gcs_delete_prefix(f"pexels/current/{theme}/")

def prefetch_weekly_set(theme: str, api_key: str, per_theme: int,
                        exists_cb, write_cb) -> List[str]:
    """Fetch randomized set from Pexels and store under pexels/current/<theme>/v_#.jpg"""
    if not storage_enabled:
        return []
    q_choices = PEXELS_THEME_QUERIES.get(theme, [theme])
    query = random.choice(q_choices)
    page = random.randint(1, 30)
    headers = {"Authorization": api_key}
    params = {"query": query, "orientation": "landscape", "size": "large", "per_page": 40, "page": page}

    keys: List[str] = []
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get("https://api.pexels.com/v1/search", headers=headers, params=params)
            r.raise_for_status()
            photos = r.json().get("photos", [])
            random.shuffle(photos)
            picked = photos[:per_theme]
            for i, p in enumerate(picked):
                src = (p.get("src") or {}).get("large")
                if not src:
                    continue
                k = f"pexels/current/{theme}/v_{i}.jpg"
                if exists_cb(k):
                    keys.append(k)
                    continue
                img = client.get(src).content
                write_cb(k, img, "image/jpeg", "public, max-age=31536000")
                keys.append(k)
    except Exception:
        # swallow; return what we have
        pass
    return keys

# ---------- ROUTES ----------
@app.get("/assets/{path:path}", summary="Assets Proxy")
def assets_proxy(path: str = Path(...)):
    """Serve any GCS asset by key (read-only). Example: /assets/pexels/current/abstract/v_0.jpg"""
    if not storage_enabled:
        raise HTTPException(404, "Storage not configured")
    data = gcs_read_bytes(path)
    if path.endswith(".png"):
        return Response(content=data, media_type="image/png")
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return Response(content=data, media_type="image/jpeg")
    return Response(content=data, media_type="application/octet-stream")

@app.get("/web/layouts/{name}.html", response_class=HTMLResponse, summary="Get Layout Html")
def get_layout_html(name: str):
    """
    Serves the static HTML for a layout from the repo (backend/web/layouts/{name}.html).
    This HTML is what Chromium renders to produce latest.png.
    """
    fp = os.path.join(os.path.dirname(__file__), "web", "layouts", f"{name}.html")
    if not os.path.exists(fp):
        raise HTTPException(404, f"Layout not found: {name}")
    with open(fp, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/v1/render_data", summary="V1 Render Data")
async def v1_render_data(
    device: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    units: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    debug: Optional[int] = Query(0)
):
    device = device or DEFAULT_DEVICE_ID
    theme = (theme or THEMES.split(",")[0]).strip()
    city = city or DEFAULT_CITY
    units = units or DEFAULT_UNITS

    weather = await get_weather(city, units)
    joke = await get_joke()

    # background selection
    bg_key = None
    if storage_enabled:
        bg_key = pexels_pick(theme)
    bg_url = f"{PUBLIC_BASE_URL}/assets/{bg_key}" if bg_key else None

    payload = {
        "device": device,
        "city": city,
        "units": units,
        "theme": theme,
        "tz": TIMEZONE,
        "now": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bg_key": bg_key,
        "bg_url": bg_url,
        "weather": weather,
        "joke": joke,
    }
    if debug:
        payload["source"] = {"has_storage": storage_enabled}
    return JSONResponse(payload)

@app.api_route("/admin/render_now", methods=["GET", "POST"], summary="Admin Render Now")
def admin_render_now(
    token: str = Query(...),
    device: Optional[str] = Query(None),
    layout: str = Query("base")
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    device = device or DEFAULT_DEVICE_ID
    png = _render_and_store_latest(device=device, layout=layout)
    return Response(content=png, media_type="image/png")

@app.get("/v1/frame", summary="V1 Frame")
def v1_frame(
    device: Optional[str] = Query(None),
):
    device = device or DEFAULT_DEVICE_ID
    key = f"renders/{device}/latest.png"
    if storage_enabled and gcs_exists(key):
        data = gcs_read_bytes(key)
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-cache"})

    # Not present → tell caller how to regenerate (secure flow uses Scheduler or admin)
    headers = {
        "Cache-Control": "no-store",
        "X-Render-Required": "true",
        "X-Render-Endpoint": f"/admin/ensure_latest?device={device}&layout=base",
    }
    raise HTTPException(status_code=404, detail="No latest frame found", headers=headers)

# ---- Admin prefetch: deep randomized dual-folder Pexels system ----
@app.get("/admin/prefetch", summary="Admin Prefetch")
def admin_prefetch(
    token: str = Query(...),
    themes: Optional[str] = Query(None),
    count: Optional[int] = Query(None),
):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid token")
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise HTTPException(400, "PEXELS_API_KEY not configured")

    theme_list = [t.strip() for t in (themes or os.getenv("THEMES", "abstract,geometric,paper-collage,kids-shapes,minimal")).split(",")]
    per_theme = int(count or os.getenv("PER_THEME_COUNT", "8") or "8")

    written = {}
    for theme in theme_list:
        rotate_current_to_cache(theme)
        keys = prefetch_weekly_set(
            theme,
            api_key,
            per_theme,
            lambda k: gcs_exists(k),
            lambda k, d, ct, cache: gcs_write_bytes(k, d, ct, cache),
        )
        written[theme] = {"downloaded": len(keys), "keys": keys}

    return JSONResponse({"themes": theme_list, "result": written})

# --- Endpoint: ensure latest render exists (for Scheduler / secure manual) ---
@app.api_route("/admin/ensure_latest", methods=["POST", "GET"], summary="Admin Ensure Latest")
def admin_ensure_latest(
    request: Request,
    token: str = Query(...),
    device: Optional[str] = Query(None),
    layout: str = Query("base"),
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    device = device or DEFAULT_DEVICE_ID

    key = f"renders/{device}/latest.png"
    if storage_enabled and gcs_exists(key):
        data = gcs_read_bytes(key)
        return Response(content=data, media_type="image/png")

    png = _render_and_store_latest(device=device, layout=layout)
    return Response(content=png, media_type="image/png")
