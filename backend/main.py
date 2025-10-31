# ================================================================
# Kin:D / Family Display Backend
# Production Build - Cloud Run / GCS / Playwright / Pexels / APIs
# ================================================================

import os
import io
import json
import random
import logging
import datetime as dt
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, Response

# ================================================================
# Logging / Configuration
# ================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kind-backend")

PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")

# Feature toggles
ENABLE_EMAIL_USERS = os.getenv("ENABLE_EMAIL_USERS", "false").lower() == "true"
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_RENDER_NOW = os.getenv("ENABLE_RENDER_NOW", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"

# City behaviour
CITY_MODE = os.getenv("CITY_MODE", "default").lower()
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin")

# External keys
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")

# Misc
THEMES = [t.strip() for t in os.getenv("THEMES", "abstract,geometric,kids,photo").split(",")]
CACHE_EXPIRY_DAYS = int(os.getenv("CACHE_EXPIRY_DAYS", "7"))
RENDER_PATH = os.getenv("RENDER_PATH", "backend/web/layouts/base.html")
RENDER_WIDTH = int(os.getenv("RENDER_WIDTH", "800"))
RENDER_HEIGHT = int(os.getenv("RENDER_HEIGHT", "480"))

# ================================================================
# Google Cloud Storage
# ================================================================
storage_enabled = False
try:
    from google.cloud import storage
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"GCS storage enabled: bucket={GCS_BUCKET}")
except Exception as e:
    logger.warning(f"GCS disabled: {e}")
    storage_enabled = False
    gcs_client = None
    gcs_bucket = None


def safe_email(email: Optional[str]) -> Optional[str]:
    """Sanitize email for safe GCS pathing"""
    if not email:
        return None
    return email.replace("@", "_at_").replace(".", "_")


def gcs_exists(key: str) -> bool:
    if not storage_enabled:
        return False
    return gcs_bucket.blob(key).exists()


def gcs_read_bytes(key: str) -> bytes:
    if not storage_enabled:
        raise RuntimeError("GCS not configured")
    return gcs_bucket.blob(key).download_as_bytes()


def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    if not storage_enabled:
        raise RuntimeError("GCS not configured")
    blob = gcs_bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"Uploaded: {key} ({len(data)} bytes)")


# ================================================================
# Playwright Renderer
# ================================================================
playwright_browser = None
if ENABLE_RENDERING:
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        playwright_browser = pw.chromium.launch(args=["--no-sandbox"])
        logger.info("Chromium renderer initialised.")
    except Exception as e:
        logger.error(f"Playwright init failed: {e}")
        ENABLE_RENDERING = False


def render_html_to_png(html_path: str, out_bytes: io.BytesIO, context: Dict[str, Any]):
    """Render the base.html with injected JSON data and snapshot as PNG"""
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")
    try:
        page = playwright_browser.new_page(viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT})
        # Inject render data into template through query string
        encoded = json.dumps(context)
        url = f"file://{os.path.abspath(html_path)}?data={encoded}"
        page.goto(url)
        page.wait_for_timeout(2000)
        out_bytes.write(page.screenshot(type="png"))
        page.close()
        logger.info("Render complete via Playwright.")
    except Exception as e:
        logger.error(f"Render failed: {e}")
        raise

# ================================================================
# FastAPI App Init
# ================================================================
app = FastAPI(title="Kin:D Family Display Backend", version="2.0.0")
# ================================================================
# Information Providers (Weather / Joke / Future-ready)
# ================================================================

LOCAL_JOKES = [
    "I told my wife she should embrace her mistakes — she gave me a hug.",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "I’m reading a book about anti-gravity. It’s impossible to put down.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I used to play piano by ear, now I use my hands.",
    "I asked my dog what’s two minus two. He said nothing.",
]

async def get_weather(city: str) -> Dict[str, Any]:
    """Fetch current weather from OpenWeather (metric °C)."""
    if not ENABLE_OPENWEATHER or not OPENWEATHER_KEY:
        logger.debug("Weather provider disabled or key missing.")
        return {"temp": 33, "icon": "01d", "desc": "Sunny"}
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
        if r.status_code == 200:
            j = r.json()
            return {
                "temp": round(j["main"]["temp"]),
                "icon": j["weather"][0]["icon"],
                "desc": j["weather"][0]["description"].title(),
            }
        logger.warning(f"Weather fetch failed {r.status_code}: {r.text[:100]}")
    except Exception as e:
        logger.error(f"Weather error: {e}")
    return {"temp": 33, "icon": "01d", "desc": "Sunny"}

async def get_joke() -> str:
    """Fetch a dad joke from icanhazdadjoke API with fallback."""
    if ENABLE_JOKES_API:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                r = await client.get(
                    "https://icanhazdadjoke.com/",
                    headers={"Accept": "application/json", "User-Agent": "Kin:D Display (https://kind-display.app)"}
                )
            if r.status_code == 200:
                return r.json().get("joke", random.choice(LOCAL_JOKES))
        except Exception as e:
            logger.debug(f"icanhazdadjoke fail: {e}")
    return random.choice(LOCAL_JOKES)

# ---- Future stubs ----
async def get_calendar() -> Dict[str, Any]:
    """Placeholder for future calendar events."""
    return {}

async def get_sports() -> Dict[str, Any]:
    """Placeholder for future sports info."""
    return {}

# Registry of enabled providers
INFO_PROVIDERS = {
    "weather": ENABLE_OPENWEATHER,
    "joke": ENABLE_JOKES_API,
    "calendar": False,
    "sports": False,
}

async def build_render_data(username: Optional[str], device: Optional[str], layout_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate all provider data into one JSON payload."""
    today = dt.date.today().isoformat()

    # determine city
    if CITY_MODE == "fetch" and layout_json and "city" in layout_json:
        city = layout_json.get("city", DEFAULT_CITY)
    else:
        city = DEFAULT_CITY

    data = {"date": today, "city": city, "username": username, "device": device}

    # weather
    if INFO_PROVIDERS["weather"]:
        data["weather"] = await get_weather(city)
    else:
        data["weather"] = {"temp": 33, "icon": "01d", "desc": "Sunny"}

    # joke
    if INFO_PROVIDERS["joke"]:
        data["dad_joke"] = await get_joke()
    else:
        data["dad_joke"] = random.choice(LOCAL_JOKES)

    # extendables
    if INFO_PROVIDERS.get("calendar"):
        data["calendar"] = await get_calendar()
    if INFO_PROVIDERS.get("sports"):
        data["sports"] = await get_sports()

    data["theme"] = random.choice(THEMES)
    return data
    # ================================================================
# Core Routes
# ================================================================

@app.get("/")
def root():
    return {
        "service": "Kin:D Family Display Backend",
        "version": "2.0.0",
        "storage": "GCS" if storage_enabled else "disabled",
        "email_users": ENABLE_EMAIL_USERS,
        "rendering": ENABLE_RENDERING,
        "pexels_enabled": ENABLE_PEXELS,
        "openweather": ENABLE_OPENWEATHER,
        "jokes_api": ENABLE_JOKES_API,
    }

# ---------------------------------------------------------------
# Designer HTML
# ---------------------------------------------------------------
@app.get("/designer/", response_class=HTMLResponse)
def get_designer():
    path = "backend/web/designer/overlay_designer_v3_full.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Designer not found</h1>"

# ---------------------------------------------------------------
# Layout Management (supports optional email hierarchy)
# ---------------------------------------------------------------
@app.get("/layouts/{device_id}")
def get_layout(device_id: str, username: Optional[str] = Query(None)):
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")

    if ENABLE_EMAIL_USERS and username:
        user_key = safe_email(username)
        key = f"users/{user_key}/devices/{device_id}/layouts/current.json"
    else:
        key = f"layouts/{device_id}.json"

    if not gcs_exists(key):
        raise HTTPException(status_code=404, detail="layout not found")

    data = json.loads(gcs_read_bytes(key))
    return JSONResponse(data)

@app.post("/admin/layouts/{device_id}")
async def save_layout(device_id: str, request: Request, username: Optional[str] = Query(None)):
    token = request.headers.get("x-admin-token") or request.query_params.get("token")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")

    payload = await request.json()
    if "elements" not in payload:
        raise HTTPException(status_code=400, detail="layout must contain 'elements'")

    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")

    if ENABLE_EMAIL_USERS and username:
        user_key = safe_email(username)
        key = f"users/{user_key}/devices/{device_id}/layouts/current.json"
    else:
        key = f"layouts/{device_id}.json"

    gcs_write_bytes(key, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), content_type="application/json")
    return {"ok": True, "device": device_id, "username": username or "default"}

# ---------------------------------------------------------------
# Render Data Endpoint
# ---------------------------------------------------------------
@app.get("/v1/render_data")
async def v1_render_data(username: Optional[str] = Query(None), device: Optional[str] = Query(None)):
    layout_json = None
    try:
        if ENABLE_EMAIL_USERS and username:
            key = f"users/{safe_email(username)}/devices/{device}/layouts/current.json"
        else:
            key = f"layouts/{device}.json"
        if gcs_exists(key):
            layout_json = json.loads(gcs_read_bytes(key))
        # if GCS layout not found, use Theme 1 preset as default
        if layout_json is None:
            default_preset_path = "backend/web/designer/presets/Theme 1.json"
            try:
                if os.path.exists(default_preset_path):
                    with open(default_preset_path, "r", encoding="utf-8") as f:
                        layout_json = json.load(f)
                    logger.info("Using default preset: Theme 1.json")
                else:
                    logger.warning("Default preset not found at expected path.")
            except Exception as e:
                logger.error(f"Default preset fallback failed: {e}")
            except Exception as e:
                logger.debug(f"Failed to load layout JSON for render_data: {e}")

    payload = await build_render_data(username, device, layout_json)
    return JSONResponse(payload)

# ---------------------------------------------------------------
# Frame Renderer (Playwright -> PNG)
# ---------------------------------------------------------------
@app.get("/v1/frame")
async def v1_frame(username: Optional[str] = Query(None), device: Optional[str] = Query(None)):
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")

    layout_json = None
    if storage_enabled:
        try:
            if ENABLE_EMAIL_USERS and username:
                key = f"users/{safe_email(username)}/devices/{device}/layouts/current.json"
            else:
                key = f"layouts/{device}.json"
            if gcs_exists(key):
                layout_json = json.loads(gcs_read_bytes(key))
            # if GCS layout not found, use Theme 1 preset as default
        if layout_json is None:
            default_preset_path = "backend/web/designer/presets/Theme 1.json"
            try:
                if os.path.exists(default_preset_path):
                    with open(default_preset_path, "r", encoding="utf-8") as f:
                        layout_json = json.load(f)
                    logger.info("Using default preset: Theme 1.json")
                else:
                    logger.warning("Default preset not found at expected path.")
            except Exception as e:
                logger.error(f"Default preset fallback failed: {e}")
            except Exception as e:
                logger.debug(f"Failed to load layout JSON for render_data: {e}")

        except Exception as e:
            logger.warning(f"Layout load failed for frame: {e}")

    render_data = await build_render_data(username, device, layout_json)
    out = io.BytesIO()
    try:
        render_html_to_png(RENDER_PATH, out, render_data)
        png_bytes = out.getvalue()
        if storage_enabled:
            if ENABLE_EMAIL_USERS and username:
                save_key = f"users/{safe_email(username)}/devices/{device}/renders/latest.png"
            else:
                save_key = f"renders/{device or 'default'}/latest.png"
            gcs_write_bytes(save_key, png_bytes, "image/png")
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Frame render failed: {e}")
        raise HTTPException(status_code=500, detail="render failed")
        # ================================================================
# Admin: Render Now + Pexels Prefetch
# ================================================================

# ---------------------------------------------------------------
# Manual render trigger
# ---------------------------------------------------------------
@app.get("/admin/render_now")
async def admin_render_now(
    token: str,
    username: Optional[str] = Query(None),
    device: Optional[str] = Query(None)
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")
    if not ENABLE_RENDER_NOW:
        raise HTTPException(status_code=403, detail="render_now disabled")
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="rendering disabled")

    logger.info(f"Manual render triggered: user={username}, device={device}")

    layout_json = None
    if storage_enabled:
        try:
            if ENABLE_EMAIL_USERS and username:
                key = f"users/{safe_email(username)}/devices/{device}/layouts/current.json"
            else:
                key = f"layouts/{device}.json"
            if gcs_exists(key):
                layout_json = json.loads(gcs_read_bytes(key))
        except Exception as e:
            logger.warning(f"Layout load failed in render_now: {e}")

    render_data = await build_render_data(username, device, layout_json)
    out = io.BytesIO()
    try:
        render_html_to_png(RENDER_PATH, out, render_data)
        png_bytes = out.getvalue()
        if storage_enabled:
            if ENABLE_EMAIL_USERS and username:
                save_key = f"users/{safe_email(username)}/devices/{device}/renders/{dt.date.today()}.png"
                latest_key = f"users/{safe_email(username)}/devices/{device}/renders/latest.png"
            else:
                save_key = f"renders/{device or 'default'}/{dt.date.today()}.png"
                latest_key = f"renders/{device or 'default'}/latest.png"
            gcs_write_bytes(save_key, png_bytes, "image/png")
            gcs_write_bytes(latest_key, png_bytes, "image/png")
        return {"ok": True, "saved": True, "bytes": len(png_bytes)}
    except Exception as e:
        logger.error(f"Manual render failed: {e}")
        raise HTTPException(status_code=500, detail="manual render failed")

# ---------------------------------------------------------------
# Pexels Prefetch / Cache rollover
# ---------------------------------------------------------------
async def pexels_fetch_images(theme: str, limit: int = 8) -> list:
    """Fetch a batch of images from Pexels API."""
    if not ENABLE_PEXELS or not PEXELS_API_KEY:
        logger.debug("Pexels disabled or key missing.")
        return []
    try:
        url = f"https://api.pexels.com/v1/search?query={theme}&per_page={limit}"
        headers = {"Authorization": PEXELS_API_KEY}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
        if r.status_code == 200:
            j = r.json()
            urls = [p["src"]["large"] for p in j.get("photos", [])]
            return urls
        logger.warning(f"Pexels fetch {theme} -> {r.status_code}")
    except Exception as e:
        logger.error(f"Pexels error: {e}")
    return []

@app.get("/admin/prefetch")
async def admin_prefetch(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")
    if not ENABLE_PEXELS:
        raise HTTPException(status_code=403, detail="pexels disabled")

    today = dt.date.today().isoformat()
    rolled_over = False
    saved = 0

    try:
        # rollover
        if storage_enabled:
            prefix_current = "pexels/current/"
            prefix_cache = f"pexels/cache/{today}/"
            blobs = list(gcs_client.list_blobs(GCS_BUCKET, prefix=prefix_current))
            if blobs:
                rolled_over = True
                for b in blobs:
                    dest = prefix_cache + b.name.split("/", 2)[-1]
                    gcs_bucket.copy_blob(b, gcs_bucket, dest)
                    b.delete()
                logger.info(f"Rolled over {len(blobs)} images to cache/{today}/")
        # fetch new
        for theme in THEMES:
            urls = await pexels_fetch_images(theme)
            for idx, url in enumerate(urls):
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        img = await client.get(url)
                    if img.status_code == 200:
                        key = f"pexels/current/{theme}_{idx}.jpg"
                        gcs_write_bytes(key, img.content, "image/jpeg")
                        saved += 1
                except Exception as e:
                    logger.debug(f"Image fetch fail {url[:40]}: {e}")
        return {"ok": True, "rolled_over": rolled_over, "saved": saved, "themes": THEMES}
    except Exception as e:
        logger.error(f"Prefetch failed: {e}")
        raise HTTPException(status_code=500, detail="prefetch failed")

# ================================================================
# Shutdown hook (close Chromium cleanly)
# ================================================================
@app.on_event("shutdown")
def shutdown_event():
    if ENABLE_RENDERING and playwright_browser:
        try:
            playwright_browser.close()
            logger.info("Chromium renderer closed.")
        except Exception as e:
            logger.warning(f"Playwright close error: {e}")

# ================================================================
# EOF
# ================================================================
logger.info("Kin:D backend loaded successfully.")