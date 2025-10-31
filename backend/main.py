# ================================================================
# Kin:D / Family Display Backend
# Production Build - Cloud Run / GCS / Playwright (async) / Pexels / Forecast
# ================================================================

import os
import io
import json
import random
import logging
import datetime as dt
from typing import Optional, Dict, Any, List

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

# Feature toggles (env driven)
ENABLE_EMAIL_USERS = os.getenv("ENABLE_EMAIL_USERS", "false").lower() == "true"
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_RENDER_NOW = os.getenv("ENABLE_RENDER_NOW", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"

# City behaviour
CITY_MODE = os.getenv("CITY_MODE", "default").lower()  # "default" or "fetch"
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
    """Sanitize email for safe GCS pathing."""
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
# Playwright (ASYNC) - initialised on startup
# ================================================================
# Important: we must use async_playwright in FastAPI to avoid:
# "It looks like you are using Playwright Sync API inside the asyncio loop."
from playwright.async_api import async_playwright

playwright_app = None
playwright_browser = None

# ================================================================
# FastAPI app
# ================================================================
app = FastAPI(title="Kin:D Family Display Backend", version="2.0.0")

# ================================================================
# Local fallback jokes
# ================================================================
LOCAL_JOKES = [
    "I told my wife she should embrace her mistakes — she gave me a hug.",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "I’m reading a book about anti-gravity. It’s impossible to put down.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I used to play piano by ear, now I use my hands.",
    "I asked my dog what’s two minus two. He said nothing.",
]

# ================================================================
# Startup / Shutdown
# ================================================================
@app.on_event("startup")
async def startup_event():
    global playwright_app, playwright_browser, ENABLE_RENDERING
    if not ENABLE_RENDERING:
        logger.info("Rendering disabled via env, skipping Playwright init.")
        return
    try:
        playwright_app = await async_playwright().start()
        playwright_browser = await playwright_app.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ]
        )
        logger.info("Chromium renderer initialised (async).")
    except Exception as e:
        logger.error(f"Playwright async init failed: {e}")
        # disable so /v1/frame returns 503 instead of exploding
        ENABLE_RENDERING = False


@app.on_event("shutdown")
async def shutdown_event():
    global playwright_app, playwright_browser
    try:
        if playwright_browser:
            await playwright_browser.close()
        if playwright_app:
            await playwright_app.stop()
        logger.info("Playwright renderer closed.")
    except Exception as e:
        logger.warning(f"Playwright close error: {e}")


# ================================================================
# Providers
# ================================================================
async def get_weather(city: str) -> Dict[str, Any]:
    """Fetch current weather from OpenWeather (metric °C). Includes humidity, wind, rain."""
    if not ENABLE_OPENWEATHER or not OPENWEATHER_KEY:
        return {
            "temp": 33,
            "feels_like": 33,
            "humidity": 45,
            "rain": 0,
            "wind": 5,
            "icon": "01d",
            "desc": "Sunny",
        }

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)

        if r.status_code == 200:
            j = r.json()
            rain = 0
            if "rain" in j and "1h" in j["rain"]:
                rain = j["rain"]["1h"]

            return {
                "temp": round(j["main"]["temp"]),
                "feels_like": round(j["main"]["feels_like"]),
                "humidity": j["main"]["humidity"],
                "wind": round(j["wind"]["speed"], 1),
                "rain": rain,
                "icon": j["weather"][0]["icon"],
                "desc": j["weather"][0]["description"].title(),
            }

        logger.warning(f"Weather fetch failed {r.status_code}: {r.text[:100]}")

    except Exception as e:
        logger.error(f"Weather error: {e}")

    # fallback
    return {
        "temp": 33,
        "feels_like": 33,
        "humidity": 45,
        "rain": 0,
        "wind": 5,
        "icon": "01d",
        "desc": "Sunny",
    }


async def get_forecast(city: str, days: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch a simple forecast (next N days) from OpenWeather 5-day/3h endpoint.
    Skips today, returns at most `days` entries.
    """
    if not ENABLE_OPENWEATHER or not OPENWEATHER_KEY:
        return []

    try:
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?q={city}&appid={OPENWEATHER_KEY}&units=metric"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        if r.status_code != 200:
            logger.warning(f"Forecast fetch failed {r.status_code}: {r.text[:120]}")
            return []

        j = r.json()
        raw_list = j.get("list", [])
        if not raw_list:
            return []

        today_str = dt.date.today().isoformat()
        per_day: Dict[str, List[Dict[str, Any]]] = {}

        for item in raw_list:
            dt_txt = item.get("dt_txt")
            if not dt_txt:
                continue
            date_only = dt_txt.split(" ")[0]
            if date_only == today_str:
                # skip today; we already have current weather
                continue

            main = item.get("main", {})
            weather_arr = item.get("weather", [])
            if not weather_arr:
                continue

            w0 = weather_arr[0]
            entry = {
                "temp": main.get("temp"),
                "desc": w0.get("description", "").title(),
                "icon": w0.get("icon"),
            }
            per_day.setdefault(date_only, []).append(entry)

        out: List[Dict[str, Any]] = []
        for day, entries in per_day.items():
            temps = [e["temp"] for e in entries if e.get("temp") is not None]
            if not temps:
                continue
            tmin = round(min(temps))
            tmax = round(max(temps))
            mid = entries[len(entries) // 2]
            out.append(
                {
                    "date": day,
                    "tmin": tmin,
                    "tmax": tmax,
                    "desc": mid.get("desc") or "",
                    "icon": mid.get("icon") or "01d",
                }
            )

        # just return the earliest N days
        out = sorted(out, key=lambda x: x["date"])[:days]
        return out

    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return []


async def get_joke() -> str:
    """Fetch a dad joke from icanhazdadjoke API with fallback."""
    if ENABLE_JOKES_API:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                r = await client.get(
                    "https://icanhazdadjoke.com/",
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Kin:D Display (https://kind-display.app)",
                    },
                )
            if r.status_code == 200:
                return r.json().get("joke", random.choice(LOCAL_JOKES))
        except Exception as e:
            logger.debug(f"icanhazdadjoke fail: {e}")
    return random.choice(LOCAL_JOKES)


async def get_calendar() -> Dict[str, Any]:
    """Placeholder for future calendar events."""
    return {}


async def get_sports() -> Dict[str, Any]:
    """Placeholder for future sports info."""
    return {}


# Enabled providers registry
INFO_PROVIDERS = {
    "weather": ENABLE_OPENWEATHER,
    "joke": ENABLE_JOKES_API,
    "calendar": False,
    "sports": False,
}


# ================================================================
# Helper: load layout from GCS or fallback to local preset
# ================================================================
def load_local_preset() -> Optional[Dict[str, Any]]:
    fallback_path = "backend/web/designer/presets/Theme 1.json"
    if os.path.exists(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Local preset load failed: {e}")
    return None


async def load_layout_for(username: Optional[str], device: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load layout JSON for a device (and username if enabled)."""
    if not device:
        device = "familydisplay"

    if storage_enabled:
        try:
            if ENABLE_EMAIL_USERS and username:
                user_key = safe_email(username)
                key = f"users/{user_key}/devices/{device}/layouts/current.json"
            else:
                key = f"layouts/{device}.json"
            if gcs_exists(key):
                return json.loads(gcs_read_bytes(key))
        except Exception as e:
            logger.warning(f"GCS layout load failed: {e}")

    # fallback to local preset
    preset = load_local_preset()
    if preset:
        logger.info("Using local preset: Theme 1.json")
    return preset


# ================================================================
# Build render payload
# ================================================================
async def build_render_data(
    username: Optional[str],
    device: Optional[str],
    layout_json: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    today = dt.date.today().isoformat()

    # decide city
    if CITY_MODE == "fetch" and layout_json and "city" in layout_json:
        city = layout_json.get("city", DEFAULT_CITY)
    else:
        city = DEFAULT_CITY

    data: Dict[str, Any] = {
        "date": today,
        "city": city,
        "username": username,
        "device": device,
    }

    # weather + forecast
    if INFO_PROVIDERS["weather"]:
        current_weather = await get_weather(city)
        forecast = await get_forecast(city, days=2)
        data["weather"] = current_weather
        data["forecast"] = forecast
    else:
        data["weather"] = {
            "temp": 33,
            "feels_like": 33,
            "humidity": 45,
            "rain": 0,
            "wind": 5,
            "icon": "01d",
            "desc": "Sunny",
        }
        data["forecast"] = []

    # joke
    if INFO_PROVIDERS["joke"]:
        data["dad_joke"] = await get_joke()
    else:
        data["dad_joke"] = random.choice(LOCAL_JOKES)

    # future stubs
    if INFO_PROVIDERS.get("calendar"):
        data["calendar"] = await get_calendar()
    if INFO_PROVIDERS.get("sports"):
        data["sports"] = await get_sports()

    data["theme"] = random.choice(THEMES)
    return data


# ================================================================
# Async renderer
# ================================================================
async def render_html_to_png(html_path: str, context: Dict[str, Any]) -> bytes:
    """Render the base.html with injected JSON data and snapshot as PNG (async)."""
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")

    page = await playwright_browser.new_page(
        viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}
    )

    encoded = json.dumps(context)
    url = f"file://{os.path.abspath(html_path)}?data={encoded}"

    await page.goto(url)
    # allow JS to render / fetch
    await page.wait_for_timeout(1500)
    png_bytes = await page.screenshot(type="png")
    await page.close()
    return png_bytes


# ================================================================
# Routes
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
    path = "web/designer/overlay_designer_v3_full.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Designer not found</h1>"


# ---------------------------------------------------------------
# Layout management
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

    gcs_write_bytes(
        key,
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    return {"ok": True, "device": device_id, "username": username or "default"}


# ---------------------------------------------------------------
# Render data (for Designer Live Preview)
# ---------------------------------------------------------------
@app.get("/v1/render_data")
async def v1_render_data(
    username: Optional[str] = Query(None),
    device: Optional[str] = Query(None),
):
    layout_json = await load_layout_for(username, device or "familydisplay")
    payload = await build_render_data(username, device or "familydisplay", layout_json)
    return JSONResponse(payload)


# ---------------------------------------------------------------
# Frame renderer
# ---------------------------------------------------------------
@app.get("/v1/frame")
async def v1_frame(
    username: Optional[str] = Query(None),
    device: Optional[str] = Query(None),
):
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")

    layout_json = await load_layout_for(username, device or "familydisplay")
    render_data = await build_render_data(username, device or "familydisplay", layout_json)

    try:
        png_bytes = await render_html_to_png(RENDER_PATH, render_data)
    except Exception as e:
        logger.error(f"Frame render failed: {e}")
        raise HTTPException(status_code=500, detail="render failed")

    # save to GCS
    if storage_enabled:
        if ENABLE_EMAIL_USERS and username:
            save_key = f"users/{safe_email(username)}/devices/{device or 'default'}/renders/latest.png"
        else:
            save_key = f"renders/{device or 'default'}/latest.png"
        try:
            gcs_write_bytes(save_key, png_bytes, "image/png")
        except Exception as e:
            logger.warning(f"GCS save of rendered frame failed: {e}")

    return Response(content=png_bytes, media_type="image/png")


# ---------------------------------------------------------------
# Manual render trigger
# ---------------------------------------------------------------
@app.get("/admin/render_now")
async def admin_render_now(
    token: str,
    username: Optional[str] = Query(None),
    device: Optional[str] = Query(None),
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")
    if not ENABLE_RENDER_NOW:
        raise HTTPException(status_code=403, detail="render_now disabled")
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="rendering disabled")

    layout_json = await load_layout_for(username, device or "familydisplay")
    render_data = await build_render_data(username, device or "familydisplay", layout_json)

    try:
        png_bytes = await render_html_to_png(RENDER_PATH, render_data)
    except Exception as e:
        logger.error(f"Manual render failed: {e}")
        raise HTTPException(status_code=500, detail="manual render failed")

    if storage_enabled:
        today = dt.date.today().isoformat()
        if ENABLE_EMAIL_USERS and username:
            base = f"users/{safe_email(username)}/devices/{device or 'default'}/renders/"
        else:
            base = f"renders/{device or 'default'}/"
        gcs_write_bytes(base + f"{today}.png", png_bytes, "image/png")
        gcs_write_bytes(base + "latest.png", png_bytes, "image/png")

    return {"ok": True, "bytes": len(png_bytes)}


# ---------------------------------------------------------------
# Pexels prefetch / cache rollover
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
        # rollover existing current → cache/<today>/
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

        # fetch new for each theme
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
# EOF
# ================================================================
logger.info("Kin:D backend loaded successfully.")