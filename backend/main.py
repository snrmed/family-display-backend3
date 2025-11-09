import os
import json
import random
import logging
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.cloud import storage
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kin:D Family Display Backend v4")

# ──────────────────────────────────────────────────────────────────────────────
# Health / Ready + Base Layout Route
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
def ok():
    return {"ok": True, "service": "family-display-backend"}

BASE_DIR = Path(__file__).resolve().parent
LAYOUTS_DIR = BASE_DIR / "web" / "layouts"

@app.get("/layouts/base.html", response_class=HTMLResponse)
async def serve_base_html(request: Request, data: str = None):
    """Serve base.html with optional data parameter for rendering."""
    base_path = LAYOUTS_DIR / "base.html"
    
    if not base_path.exists():
        raise HTTPException(status_code=404, detail="base.html not found")
    
    # Read and return the HTML file
    with open(base_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content, media_type="text/html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"
DEFAULT_ICON_THEME = os.getenv("WEATHER_ICON_PACK", "happy-skies")
RENDER_WIDTH = int(os.getenv("RENDER_WIDTH", "800"))
RENDER_HEIGHT = int(os.getenv("RENDER_HEIGHT", "480"))
RENDER_PATH = os.getenv("RENDER_PATH", "backend/web/layouts/base.html")

PROJECT_ROOT = BASE_DIR.parent
STATIC_SEARCH_BASES = [Path.cwd(), BASE_DIR, PROJECT_ROOT]
DEFAULT_LAYOUT_KEY = "assets/default.json"

LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
]

# ──────────────────────────────────────────────────────────────────────────────
# GOOGLE CLOUD STORAGE
# ──────────────────────────────────────────────────────────────────────────────

storage_enabled = False
bucket = None
playwright_browser = None

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"✅ GCS connected: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"⚠️ GCS disabled: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def make_public_url(path: str) -> str:
    """Return a proxied/public URL for an object path."""
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    if base:
        return f"{base}/{path.lstrip('/')}"
    return f"/{path.lstrip('/')}"

def resolve_static_dir(*relative_paths: str) -> Path | None:
    """Find the first existing directory from a list of relative paths."""
    for relative_path in relative_paths:
        candidate = Path(relative_path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        for base in STATIC_SEARCH_BASES:
            base_candidate = (base / relative_path).resolve()
            if base_candidate.exists():
                return base_candidate
    return None

def gcs_read_json(key: str) -> dict:
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return json.loads(blob.download_as_text())

def gcs_read_text(key: str) -> str:
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return blob.download_as_text()

def gcs_write_json(key: str, data: dict):
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    logger.info(f"💾 Saved: {key}")

# ============================================================================
# DEVICE LAYOUT LOADING
# ============================================================================

def load_device_layout(device_id: str) -> dict:
    """
    Load the device's layout; fallback to global default if missing.
    """
    # 1) Device layout
    try:
        return gcs_read_json(f"devices/{device_id}/layouts/current.json")
    except Exception:
        pass

    # 2) Global default
    try:
        return gcs_read_json(DEFAULT_LAYOUT_KEY)
    except Exception:
        pass

    # 3) Empty skeleton as last resort
    return {"name": "Default", "elements": []}

def gcs_write_bytes(key: str, data: bytes, content_type: str = "image/png"):
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"💾 Saved: {key}")

# ──────────────────────────────────────────────────────────────────────────────
# DEVICE CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_DEVICE_CONFIG = {
    "location": {
        "name": os.getenv("DEFAULT_CITY", "Darwin"),
        "lat": float(os.getenv("DEFAULT_LAT", "-12.4634")),
        "lon": float(os.getenv("DEFAULT_LON", "130.8456")),
        "timezone": os.getenv("DEFAULT_TZ", "Australia/Darwin")
    },
    "preferences": {"iconTheme": DEFAULT_ICON_THEME},
}

def get_device_config(device_id: str = "familydisplay") -> dict:
    if not storage_enabled:
        return DEFAULT_DEVICE_CONFIG
    try:
        config_key = f"devices/{device_id}/config.json"
        config = gcs_read_json(config_key)
        logger.info(f"✅ Loaded config for {device_id}")
        return config
    except Exception:
        logger.info(f"Using default config for {device_id}")
        return DEFAULT_DEVICE_CONFIG

def save_device_config(device_id: str, config: dict):
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    config_key = f"devices/{device_id}/config.json"
    gcs_write_json(config_key, config)
    logger.info(f"✅ Saved config for {device_id}")

# ──────────────────────────────────────────────────────────────────────────────
# RENDERING & BROWSER
# ──────────────────────────────────────────────────────────────────────────────

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright

        async def init_browser():
            global playwright_browser
            pw = await async_playwright().start()
            playwright_browser = await pw.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            logger.info("🎭 Playwright browser initialized")

        @app.on_event("startup")
        async def startup():
            await init_browser()

        @app.on_event("shutdown")
        async def shutdown():
            if playwright_browser:
                await playwright_browser.close()
    except Exception as e:
        logger.warning(f"⚠️ Playwright disabled: {e}")
        ENABLE_RENDERING = False
        
# ──────────────────────────────────────────────────────────────────────────────
# CONTENT PROVIDERS
# ──────────────────────────────────────────────────────────────────────────────

def resolve_weather_icon_url(theme: str, code: str) -> str:
    """Resolve weather icon URL (proxied)."""
    path = f"assets/weather-icons/{theme}/{code}.svg"
    return make_public_url(f"gcs/{path}")

async def get_weather(lat: float = None, lon: float = None, city: str = None) -> dict:
    """Get weather from OpenWeather using lat/lon (preferred) or city name (fallback)."""
    api_key = os.getenv("OPENWEATHER_KEY")

    if ENABLE_OPENWEATHER and api_key:
        try:
            async with httpx.AsyncClient() as client:
                # Prefer lat/lon if provided
                if lat is not None and lon is not None:
                    # Get current weather using coordinates
                    current_url = "https://api.openweathermap.org/data/2.5/weather"
                    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
                    logger.info(f"Fetching weather for lat={lat}, lon={lon}")
                    
                elif city:
                    # Fallback to city name
                    current_url = "https://api.openweathermap.org/data/2.5/weather"
                    params = {"q": city, "appid": api_key, "units": "metric"}
                    logger.info(f"Fetching weather for city={city}")
                else:
                    raise ValueError("Either lat/lon or city must be provided")
                
                r = await client.get(current_url, params=params, timeout=10)

                if r.status_code == 200:
                    data = r.json()
                    
                    # Extract coordinates (will be accurate even if we used city name)
                    actual_lat = data["coord"]["lat"]
                    actual_lon = data["coord"]["lon"]
                    
                    # Get 5-day/3-hour forecast using coordinates
                    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
                    forecast_params = {"lat": actual_lat, "lon": actual_lon, "appid": api_key, "units": "metric"}
                    fr = await client.get(forecast_url, params=forecast_params, timeout=10)

                    # Calculate today's actual min/max from first 8 entries (24 hours)
                    today_min, today_max = None, None
                    tomorrow_data = None
                    
                    if fr.status_code == 200:
                        forecast = fr.json()
                        if forecast.get("list"):
                            # Today's min/max from first 8 entries
                            today_temps = [entry["main"]["temp"] for entry in forecast["list"][:8]]
                            today_min = round(min(today_temps)) if today_temps else None
                            today_max = round(max(today_temps)) if today_temps else None
                            
                            # Tomorrow's forecast (entries 8-16)
                            if len(forecast["list"]) > 8:
                                tomorrow_temps = [entry["main"]["temp"] for entry in forecast["list"][8:16]]
                                tomorrow_entry = forecast["list"][8]
                                tomorrow_data = {
                                    "temp_min": round(min(tomorrow_temps)) if tomorrow_temps else None,
                                    "temp_max": round(max(tomorrow_temps)) if tomorrow_temps else None,
                                    "desc": tomorrow_entry["weather"][0]["description"].title(),
                                }

                    # Use forecast min/max if available
                    temp_min = today_min if today_min is not None else round(data["main"]["temp_min"])
                    temp_max = today_max if today_max is not None else round(data["main"]["temp_max"])
                    
                    # Build verbose weather description
                    desc = data["weather"][0]["description"]
                    humidity = data["main"]["humidity"]
                    wind_speed = round(data["wind"]["speed"] * 3.6)
                    rain_amount = data.get("rain", {}).get("1h", 0)
                    
                    verbose_desc = f"Expecting {desc} with temperatures ranging from {temp_min}°C to {temp_max}°C. "
                    
                    if rain_amount > 0:
                        verbose_desc += f"Rainfall of {rain_amount}mm expected. "
                    elif "rain" in desc.lower() or "drizzle" in desc.lower():
                        verbose_desc += "Some rain expected throughout the day. "
                    
                    if wind_speed > 30:
                        verbose_desc += f"Windy conditions with gusts up to {wind_speed} km/h. "
                    elif wind_speed > 15:
                        verbose_desc += f"Moderate winds around {wind_speed} km/h. "
                    
                    if humidity > 80:
                        verbose_desc += "High humidity making it feel quite muggy."
                    elif humidity > 60:
                        verbose_desc += "Moderate humidity levels."
                    else:
                        verbose_desc += "Relatively dry conditions."
                    
                    # Build tomorrow's verbose description
                    tomorrow_verbose = None
                    if tomorrow_data:
                        tmr_desc = tomorrow_data["desc"].lower()
                        tmr_min = tomorrow_data["temp_min"]
                        tmr_max = tomorrow_data["temp_max"]
                        
                        tomorrow_verbose = f"Tomorrow expecting {tmr_desc} with temperatures from {tmr_min}°C to {tmr_max}°C. "
                        
                        if "rain" in tmr_desc or "drizzle" in tmr_desc or "shower" in tmr_desc:
                            tomorrow_verbose += "Rain expected. "
                        elif "storm" in tmr_desc or "thunder" in tmr_desc:
                            tomorrow_verbose += "Stormy conditions likely. "
                        elif "cloud" in tmr_desc:
                            tomorrow_verbose += "Cloudy skies. "
                        else:
                            tomorrow_verbose += "Clear conditions. "
                        
                        tomorrow_data["desc_extended"] = tomorrow_verbose

                    # Get location name from response
                    location_name = data.get("name", city or "Unknown")

                    return {
                        "humidity": humidity,
                        "rain": rain_amount,
                        "wind": wind_speed,
                        "icon": data["weather"][0]["icon"],
                        "desc": desc.title(),
                        "desc_extended": verbose_desc,
                        "temp_min": temp_min,
                        "temp_max": temp_max,
                        "timezone_offset": data.get("timezone", 0),
                        "tomorrow": tomorrow_data,
                        "lat": actual_lat,
                        "lon": actual_lon,
                        "location_name": location_name,
                    }
        except Exception as e:
            logger.warning(f"OpenWeather API failed: {e}")

    # Fallback sample data
    return {
        "temp": 32,
        "humidity": 65,
        "rain": 0,
        "wind": 15,
        "icon": "01d",
        "desc": "Sunny",
        "desc_extended": "Expecting sunny conditions with temperatures ranging from 26°C to 36°C. Moderate humidity levels.",
        "temp_min": 26,
        "temp_max": 36,
        "timezone_offset": 0,
        "tomorrow": {
            "temp_min": 25, 
            "temp_max": 35, 
            "desc": "Partly Cloudy",
            "desc_extended": "Tomorrow expecting partly cloudy with temperatures from 25°C to 35°C. Cloudy skies."
        },
        "lat": -12.4634,
        "lon": 130.8456,
        "location_name": "Darwin",
    }
    
    async def get_joke() -> str:
        if ENABLE_JOKES_API:
            try:  # <--- Fixed: Indented inside the 'if'
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        "https://icanhazdadjoke.com/",
                        headers={"Accept": "application/json"},
                        timeout=5,
                    )
                    if r.status_code == 200:
                        return r.json()["joke"]
            except Exception as e:
                logger.warning(f"Joke API failed: {e}")
        
        # Fixed: Indented to be the fallback return for the function
        return random.choice(LOCAL_JOKES)

    def get_pexels_categories() -> list:
    if not storage_enabled:
        return ["abstract", "geometric", "minimal"]
    try:
        blobs = bucket.list_blobs(prefix="pexels/current/")
        categories = set()
        for blob in blobs:
            fn = blob.name.split("/")[-1]
            if "_" in fn:
                categories.add(fn.split("_")[0])
        out = sorted(categories)
        return out or ["abstract", "geometric", "minimal"]
    except Exception as e:
        logger.warning(f"Could not list Pexels categories: {e}")
        return ["abstract", "geometric", "minimal"]

def choose_pexels_background(selected_category: str = None) -> dict | None:
    if not storage_enabled:
        return None
    try:
        prefix = "pexels/current/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        if selected_category:
            blobs = [b for b in blobs if b.name.split("/")[-1].startswith(f"{selected_category}_")]
        if blobs:
            chosen = random.choice(blobs)
            filename = chosen.name.split("/")[-1]
            category = filename.split("_")[0] if "_" in filename else "unknown"
            return {
                "url": make_public_url(f"gcs/{chosen.name}"),
                "category": category,
                "filename": filename,
            }
    except Exception as e:
        logger.warning(f"Could not choose Pexels background: {e}")
    return None

# ──────────────────────────────────────────────────────────────────────────────
# RENDER DATA
# ──────────────────────────────────────────────────────────────────────────────

async def build_render_data(device: str = "familydisplay") -> dict:
    device_config = get_device_config(device)
    
    location = device_config.get("location", {})
    location_name = location.get("name") or location.get("city", "Darwin")
    lat = location.get("lat")
    lon = location.get("lon")
    tz_name = location.get("timezone", "Australia/Darwin")
    icon_theme = device_config.get("preferences", {}).get("iconTheme", DEFAULT_ICON_THEME)

    logger.info(f"Building render data for {device}: {location_name} (lat={lat}, lon={lon})")

    # Load layout (with default fallback)
    layout = load_device_layout(device)

    # Get weather using coordinates (or fallback to name)
    if lat is not None and lon is not None:
        weather = await get_weather(lat=lat, lon=lon)
    else:
        weather = await get_weather(city=f"{location_name},AU")
    icon_code = weather.get("icon", "01d")
    weather["icon_url"] = resolve_weather_icon_url(icon_theme, icon_code)
    weather["city"] = location_name

    # local datetime
    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
    except Exception as e:
        logger.warning(f"Invalid timezone {tz_name}: {e}, using UTC")
        now = datetime.now(timezone.utc)
    weather["local_datetime"] = now.isoformat()

    # content
    dad_joke = await get_joke()

    # background
    selected_category = layout.get("meta", {}).get("pexelsCategory")
    pexels_info = choose_pexels_background(selected_category) if (ENABLE_PEXELS and storage_enabled) else None
    if pexels_info:
        bg_url = pexels_info["url"]
    else:
        bg_url = make_public_url("gcs/pexels/current/abstract_0.jpg")

    # categories list
    categories = get_pexels_categories() if ENABLE_PEXELS else []
    if ENABLE_PEXELS:
        pexels_info = pexels_info or {}
        pexels_info["categories"] = categories

    date_str = now.strftime("%a, %d %b")

    # bases (proxied paths)
    if storage_enabled:
        svg_base = make_public_url("gcs/assets/svgs")
        font_base = make_public_url("gcs/assets/fonts")
        icon_base = make_public_url("gcs/assets/weather-icons")
    else:
        svg_base = make_public_url("designer/svgs")
        font_base = make_public_url("designer/fonts")
        icon_base = make_public_url("designer/weather-icons")

    # dynamic_text map (keys match get_weather())
    w = weather or {}
    tomorrow = (w.get("tomorrow") or {}) if isinstance(w, dict) else {}

    def _fmt_temp(val):
        if val is None:
            return ""
        try:
            return f"{round(float(val))}°C"
        except Exception:
            return f"{val}°C"

    def _fmt_minmax(tmin, tmax):
        if tmin is None and tmax is None:
            return ""
        tmin_s = "" if tmin is None else str(round(float(tmin)))
        tmax_s = "" if tmax is None else str(round(float(tmax)))
        if tmin_s and tmax_s:
            return f"{tmin_s}/{tmax_s}°C"
        return f"{tmin_s or tmax_s}°C"

    def _fmt_speed(val):
        if val is None:
            return ""
        try:
            v = float(val)
            return f"{round(v)} km/h"
        except Exception:
            return f"{val} km/h"

    def _fmt_rain(val):
        if val is None:
            return ""
        try:
            v = float(val)
            s = f"{v:.1f}" if v and abs(v) < 1 else f"{round(v)}"
            return f"{s}mm"
        except Exception:
            return f"{val}mm"

    def _icon_url():
        if w.get("icon_url"):
            return w["icon_url"]
        icon = w.get("icon") or ""
        return f"{icon_base}/{icon}.svg" if icon else ""

    dynamic_text = {
        "CITY": w.get("city") or "",
        "WEATHER_CITY": w.get("city") or "",
        "DATE": date_str,
        "JOKE": dad_joke or "",
        "TEMP": _fmt_temp(w.get("temp")),
        "WEATHER_TEMP": _fmt_temp(w.get("temp")),
        "MINMAX": _fmt_minmax(w.get("temp_min"), w.get("temp_max")),
        "WEATHER_MINMAX": _fmt_minmax(w.get("temp_min"), w.get("temp_max")),
        "WEATHER_DESC": (w.get("desc") or "").title(),
        "WEATHER_DESC_EXTENDED": (w.get("desc_extended") or w.get("desc") or "").strip(),
        "WEATHER_ICON": _icon_url(),
        "HUMIDITY": ("" if w.get("humidity") is None else f"{int(round(float(w.get('humidity'))))}%"),
        "WEATHER_HUMIDITY": ("" if w.get("humidity") is None else f"{int(round(float(w.get('humidity'))))}%"),
        "WIND": _fmt_speed(w.get("wind")),
        "RAIN": _fmt_rain(w.get("rain")),
        "WEATHER_NOTE": (w.get("note") or ""),
        "TOMORROW_DESC": (tomorrow.get("desc") or "").title() if isinstance(tomorrow, dict) else "",
        "TOMORROW_TEMP": _fmt_minmax(tomorrow.get("temp_min"), tomorrow.get("temp_max")) if isinstance(tomorrow, dict) else "",
        "CUSTOM": "",
        "ENABLE_OPENWEATHER": "true" if os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true" else "false",
        "OPENWEATHER_KEY": os.getenv("OPENWEATHER_KEY", ""),
    }

    context = {
        "layout": layout,
        "weather": weather,
        "dad_joke": dad_joke,
        "date": date_str,
        "bg_url": bg_url,
        "pexels": pexels_info,
        "svg_base": svg_base,
        "font_base": font_base,
        "icon_base": icon_base,
        "dynamic_text": dynamic_text,
        "device": device_config,
        "timestamp": now.isoformat(),
    }
    return context

# ──────────────────────────────────────────────────────────────────────────────
# RENDER HTML → PNG
# ──────────────────────────────────────────────────────────────────────────────

async def render_html_to_png(render_path: str, context: dict) -> bytes:
    """Render base.html to PNG using Playwright with data injection."""
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")

    page = await playwright_browser.new_page(
        viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}
    )

    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    
    if not public_base:
        raise RuntimeError("PUBLIC_BASE_URL environment variable not configured")
    
    # Navigate to base.html without data parameter
    url = f"{public_base}/layouts/base.html"
    
    logger.info(f"🎨 Rendering via: {url}")
    logger.info(f"📊 Context data size: {len(json.dumps(context))} bytes")
    logger.info(f"📐 Layout elements: {len(context.get('layout', {}).get('elements', []))}")

    try:
        # Navigate to the page first
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        if not response or response.status != 200:
            logger.error(f"Failed to load page. Status: {response.status if response else 'None'}")
            raise RuntimeError(f"Page load failed with status {response.status if response else 'unknown'}")
        
        # Inject the data directly into the page (avoids URL length limits)
        logger.info("💉 Injecting render data into page...")
        await page.evaluate(f"""
            window.renderData = {json.dumps(context)};
            if (typeof renderLayout === 'function') {{
                renderLayout(window.renderData);
            }}
        """)
        
        # Wait for fonts to load
        await page.evaluate(
            "document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()"
        )
        
        # Wait for rendering to complete
        await page.wait_for_timeout(300)
        
        # Take screenshot
        png_bytes = await page.screenshot(type="png", full_page=True)
        logger.info(f"✓ Screenshot captured: {len(png_bytes)} bytes")
        return png_bytes
        
    except Exception as e:
        logger.error(f"Rendering error: {e}", exc_info=True)
        raise
    finally:
        await page.close()
        
# ──────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ──────────────────────────────────────────────────────────────────────────────

# Device Config
@app.get("/v1/devices/{device_id}/config")
def api_get_device_config(device_id: str):
    try:
        config = get_device_config(device_id)
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"Failed to get device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/devices/{device_id}/config")
async def api_save_device_config(device_id: str, request: Request):
    try:
        config = await request.json()
        save_device_config(device_id, config)
        return {"status": "saved", "device_id": device_id}
    except Exception as e:
        logger.error(f"Failed to save device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Layouts
@app.get("/v1/devices/{device_id}/layouts/current")
def api_get_layout(device_id: str):
    try:
        layout_key = f"devices/{device_id}/layouts/current.json"
        layout = gcs_read_json(layout_key)
        return JSONResponse(content=layout)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Layout not found")
    except Exception as e:
        logger.error(f"Failed to get layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/devices/{device_id}/layouts/current")
async def api_save_layout(device_id: str, request: Request):
    try:
        layout = await request.json()
        layout_key = f"devices/{device_id}/layouts/current.json"
        gcs_write_json(layout_key, layout)
        return {"status": "saved", "device_id": device_id}
    except Exception as e:
        logger.error(f"Failed to save layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Render Data
@app.get("/v1/render_data")
async def api_render_data(device: str = "familydisplay"):
    try:
        data = await build_render_data(device)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Failed to build render data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Frame Render
@app.get("/v1/frame")
async def api_frame(device: str = "familydisplay"):
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    try:
        data = await build_render_data(device)
        render_path = Path(RENDER_PATH)
        if not render_path.exists():
            render_path = BASE_DIR / "web" / "layouts" / "base.html"
        png_bytes = await render_html_to_png(str(render_path), data)

        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes)

        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to render frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Debug Routes
@app.get("/v1/debug/render_data")
async def debug_render_data(device: str = "familydisplay"):
    try:
        data = await build_render_data(device)
        return {
            "success": True,
            "device": device,
            "data_keys": list(data.keys()),
            "layout_name": data.get("layout", {}).get("name"),
            "element_count": len(data.get("layout", {}).get("elements", [])),
            "weather": data.get("weather"),
            "dad_joke": data.get("dad_joke"),
            "date": data.get("date"),
            "bg_url": data.get("bg_url"),
            "svg_base": data.get("svg_base"),
            "font_base": data.get("font_base"),
            "icon_base": data.get("icon_base"),
            "dynamic_text": data.get("dynamic_text"),
        }
    except Exception as e:
        logger.error(f"Debug render data error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

@app.get("/v1/debug/frame_url")
async def debug_frame_url(device: str = "familydisplay"):
    """Debug endpoint to see what URL would be generated for rendering."""
    try:
        data = await build_render_data(device)
        raw_json = json.dumps(data)
        encoded_data = quote(raw_json, safe="")
        public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        url = f"{public_base}/layouts/base.html?data={encoded_data}"
        
        return {
            "success": True,
            "url_length": len(url),
            "data_size": len(raw_json),
            "url_preview": url[:500] + "..." if len(url) > 500 else url,
            "layout_loaded": bool(data.get("layout")),
            "element_count": len(data.get("layout", {}).get("elements", [])),
            "has_weather": bool(data.get("weather")),
            "has_bg_url": bool(data.get("bg_url")),
            "weather_icon_url": data.get("weather", {}).get("icon_url")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/v1/debug/layout")
def debug_layout(device: str = "familydisplay"):
    try:
        layout_key = f"devices/{device}/layouts/current.json"
        layout = gcs_read_json(layout_key)
        return {
            "success": True,
            "device": device,
            "layout_key": layout_key,
            "layout": layout,
            "element_count": len(layout.get("elements", [])),
        }
    except Exception as e:
        logger.error(f"Debug layout error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "layout_key": f"devices/{device}/layouts/current.json",
            "gcs_bucket": GCS_BUCKET,
            "storage_enabled": storage_enabled,
        }

# ──────────────────────────────────────────────────────────────────────────────
# DESIGNER ROUTE (LOADS HTML DIRECTLY FROM GCS)
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/designer/", response_class=HTMLResponse)
async def designer():
    """Serve Designer HTML directly from GCS bucket."""
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="Storage not configured")

    designer_key = "web/designer/overlay_designer_v4_clean.html"
    try:
        html_content = gcs_read_text(designer_key)
        logger.info(f"✅ Designer loaded from {designer_key}")
        return HTMLResponse(content=html_content, media_type="text/html")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Designer not found in bucket",
                "expected_key": designer_key,
                "bucket": GCS_BUCKET,
            },
        )
    except Exception as e:
        logger.error(f"Failed to load designer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# STATIC MOUNTS (optional in-container dev)
# ──────────────────────────────────────────────────────────────────────────────

try:
    presets_dir = resolve_static_dir("web/presets", "backend/web/presets")
    if presets_dir and presets_dir.is_dir():
        app.mount("/presets", StaticFiles(directory=str(presets_dir)), name="presets")
        logger.info(f"✓ Mounted /presets from {presets_dir}")
except Exception as e:
    logger.warning(f"Could not mount /presets: {e}")

try:
    fonts_dir = resolve_static_dir("web/fonts", "backend/web/fonts")
    if fonts_dir and fonts_dir.is_dir():
        app.mount("/fonts", StaticFiles(directory=str(fonts_dir)), name="fonts")
        logger.info(f"✓ Mounted /fonts from {fonts_dir}")
except Exception as e:
    logger.warning(f"Could not mount /fonts: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# GCS ASSET PROXY
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/gcs/{path:path}")
async def gcs_proxy(path: str):
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="GCS not enabled")
    try:
        blob = bucket.blob(path)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Asset not found")
        data = blob.download_as_bytes()

        if path.endswith(".svg"):
            content_type = "image/svg+xml"
        elif path.endswith(".json"):
            content_type = "application/json"
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif path.endswith(".png"):
            content_type = "image/png"
        elif path.endswith(".woff2"):
            content_type = "font/woff2"
        elif path.endswith(".css"):
            content_type = "text/css"
        else:
            content_type = "application/octet-stream"

        return Response(content=data, media_type=content_type)
    except Exception as e:
        logger.error(f"GCS proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/admin/render_now")
async def admin_render_now(token: str = None, device: str = "familydisplay"):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        # Use the same path resolution as /v1/frame
        data = await build_render_data(device)
        render_path = Path(RENDER_PATH)
        if not render_path.exists():
            render_path = BASE_DIR / "web" / "layouts" / "base.html"
        png_bytes = await render_html_to_png(str(render_path), data)
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes)
        return {"status": "rendered", "device": device}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# DEVICE MANAGEMENT ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/v1/devices")
def list_devices():
    """List device IDs found under devices/ in the bucket."""
    if not storage_enabled:
        return {"devices": []}
    seen = set()
    try:
        for blob in bucket.list_blobs(prefix="devices/"):
            parts = blob.name.split("/")
            if len(parts) >= 2 and parts[0] == "devices" and parts[1]:
                seen.add(parts[1])
    except Exception as e:
        logger.warning(f"Could not list devices: {e}")
    return {"devices": sorted(seen)}


@app.post("/v1/devices/{device_id}/layouts/init_from_default")
def init_layout_from_default(device_id: str):
    """
    Copy assets/default.json → devices/<device_id>/layouts/current.json
    (idempotent; overwrites existing file)
    """
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="GCS not enabled")
    try:
        default_layout = gcs_read_json(DEFAULT_LAYOUT_KEY)
        gcs_write_json(f"devices/{device_id}/layouts/current.json", default_layout)
        logger.info(f"✅ Initialized layout for {device_id} from default.json")
        return {"status": "ok", "device": device_id}
    except Exception as e:
        logger.error(f"Failed to initialize layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# API HELPER ROUTES (for designer)
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/list-svgs")
def list_svgs():
    """List available SVG assets for the designer."""
    if not storage_enabled:
        return {"svgs": []}
    try:
        blobs = bucket.list_blobs(prefix="assets/svgs/")
        svgs = []
        for blob in blobs:
            filename = blob.name.split("/")[-1]
            if filename.endswith(".svg"):
                svgs.append({
                    "name": filename,
                    "url": make_public_url(f"gcs/{blob.name}")
                })
        return {"svgs": svgs}
    except Exception as e:
        logger.error(f"Failed to list SVGs: {e}")
        return {"svgs": []}

@app.get("/api/list-pexels-categories")
def list_pexels_categories():
    """List available Pexels categories."""
    categories = get_pexels_categories()
    return {"categories": categories}

@app.get("/api/search-location")
async def search_location(q: str):
    """Search for locations using OpenWeather Geocoding API."""
    api_key = os.getenv("OPENWEATHER_KEY")
    
    if not api_key:
        raise HTTPException(status_code=503, detail="Weather API not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            # OpenWeather Geocoding API
            url = "http://api.openweathermap.org/geo/1.0/direct"
            params = {
                "q": q,
                "limit": 5,  # Return top 5 matches
                "appid": api_key
            }
            
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                results = response.json()
                
                # Format results for frontend
                locations = []
                for loc in results:
                    locations.append({
                        "name": loc.get("name", ""),
                        "state": loc.get("state", ""),
                        "country": loc.get("country", ""),
                        "lat": loc.get("lat"),
                        "lon": loc.get("lon"),
                        "display": f"{loc.get('name', '')}, {loc.get('state', '')}, {loc.get('country', '')}"
                    })
                
                return {"locations": locations}
            else:
                raise HTTPException(status_code=response.status_code, detail="Search failed")
                
    except Exception as e:
        logger.error(f"Location search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/list-presets")
def list_presets_api():
    """List available preset layouts from GCS (assets/layouts/*.json)."""
    if not storage_enabled:
        return {"presets": []}
    try:
        presets = []
        for blob in bucket.list_blobs(prefix="assets/layouts/"):
            name = blob.name.split("/")[-1]
            if not name.endswith(".json"):
                continue
            presets.append(name[:-5])
        return {"presets": sorted(presets)}
    except Exception as e:
        logger.error(f"Failed to list presets from GCS: {e}")
        return {"presets": []}

from fastapi.responses import JSONResponse
from fastapi import HTTPException

@app.get("/presets/{name}.json")
def get_preset_json(name: str):
    """Serve preset JSONs stored in GCS (assets/layouts/<name>.json)."""
    if not storage_enabled:
        raise HTTPException(status_code=404, detail="storage disabled")

    try:
        blob = bucket.blob(f"assets/layouts/{name}.json")
        if not blob.exists():
            raise HTTPException(status_code=404, detail="preset not found")

        text = blob.download_as_text()
        return JSONResponse(content=json.loads(text))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to load preset {name}: {e}")
        raise HTTPException(status_code=500, detail="failed to load preset")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
