from fastapi import Query
import os
import json
import random
import logging
import traceback
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.cloud import storage
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kin:D Family Display Backend v4")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Health / Ready + Base Layout Route
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CONFIGURATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
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

TODO_PRESETS = {
    "kids_morning": {
        "name": "Kids Morning Routine",
        "items": [
            {"emoji": "ðŸ›ï¸", "time": "7:00am", "task": "Make bed", "days": ["weekdays"]},
            {"emoji": "ðŸª¥", "time": "7:15am", "task": "Brush teeth", "days": ["all"]},
            {"emoji": "ðŸ¥£", "time": "7:30am", "task": "Eat breakfast", "days": ["all"]},
            {"emoji": "ðŸŽ’", "time": "8:00am", "task": "Pack school bag", "days": ["weekdays"]}
        ]
    },
    "kids_afternoon": {
        "name": "After School Tasks",
        "items": [
            {"emoji": "ðŸ‘•", "time": "3:30pm", "task": "Change clothes", "days": ["weekdays"]},
            {"emoji": "ðŸ“š", "time": "4:00pm", "task": "Homework time", "days": ["weekdays"]},
            {"emoji": "ðŸ§¹", "time": "5:00pm", "task": "Tidy room", "days": ["all"]},
            {"emoji": "ðŸ±", "time": "5:30pm", "task": "Feed pets", "days": ["all"]}
        ]
    },
    "kids_chores": {
        "name": "Weekly Chores",
        "items": [
            {"emoji": "ðŸ—‘ï¸", "time": "6:00pm", "task": "Take out bins", "days": ["mon", "thu"]},
            {"emoji": "ðŸ§º", "time": "", "task": "Put laundry away", "days": ["wed", "sat"]},
            {"emoji": "ðŸ§½", "time": "", "task": "Wipe table after dinner", "days": ["all"]},
            {"emoji": "ðŸŒ±", "time": "", "task": "Water plants", "days": ["sun"]}
        ]
    },
    "family_weekly": {
        "name": "Family Reminders",
        "items": [
            {"emoji": "ðŸ“š", "time": "", "task": "Library books due", "days": ["mon"]},
            {"emoji": "ðŸ—‘ï¸", "time": "6:00pm", "task": "Bin night", "days": ["wed"]},
            {"emoji": "ðŸŽ¹", "time": "4:00pm", "task": "Piano lesson", "days": ["fri"]},
            {"emoji": "âš½", "time": "9:00am", "task": "Soccer game", "days": ["sat"]}
        ]
    },
    "homework": {
        "name": "Homework Checklist",
        "items": [
            {"emoji": "ðŸ“–", "time": "", "task": "Reading", "days": ["weekdays"]},
            {"emoji": "âœï¸", "time": "", "task": "Math worksheet", "days": ["weekdays"]},
            {"emoji": "ðŸ”¤", "time": "", "task": "Spelling practice", "days": ["weekdays"]},
            {"emoji": "ðŸŽ¨", "time": "", "task": "Art project", "days": ["weekends"]}
        ]
    }
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GOOGLE CLOUD STORAGE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

storage_enabled = False
bucket = None
playwright_browser = None

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"âœ… GCS connected: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"âš ï¸ GCS disabled: {e}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UTILITIES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    logger.info(f"ðŸ’¾ Saved: {key}")

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
    logger.info(f"ðŸ’¾ Saved: {key}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DEVICE CONFIGURATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        logger.info(f"âœ… Loaded config for {device_id}")
        return config
    except Exception:
        logger.info(f"Using default config for {device_id}")
        return DEFAULT_DEVICE_CONFIG

def save_device_config(device_id: str, config: dict):
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    config_key = f"devices/{device_id}/config.json"
    gcs_write_json(config_key, config)
    logger.info(f"âœ… Saved config for {device_id}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RENDERING & BROWSER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright

        async def init_browser():
            global playwright_browser
            pw = await async_playwright().start()
            playwright_browser = await pw.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            logger.info("ðŸŽ­ Playwright browser initialized")

        @app.on_event("startup")
        async def startup():
            await init_browser()

        @app.on_event("shutdown")
        async def shutdown():
            if playwright_browser:
                await playwright_browser.close()
    except Exception as e:
        logger.warning(f"âš ï¸ Playwright disabled: {e}")
        ENABLE_RENDERING = False
        
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CONTENT PROVIDERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                    rain_periods = []  # Track when rain is expected
                    
                    if fr.status_code == 200:
                        forecast = fr.json()
                        if forecast.get("list"):
                            # Today's min/max from first 8 entries
                            today_temps = [entry["main"]["temp"] for entry in forecast["list"][:8]]
                            today_min = round(min(today_temps)) if today_temps else None
                            today_max = round(max(today_temps)) if today_temps else None
                            
                            # Check for rain in today's forecast
                            for i, entry in enumerate(forecast["list"][:8]):
                                if entry.get("rain") or any(w["main"].lower() in ["rain", "drizzle"] for w in entry["weather"]):
                                    # Convert forecast time to readable format
                                    dt = datetime.fromtimestamp(entry["dt"])
                                    hour = dt.strftime("%I%p").lstrip("0").lower()
                                    rain_periods.append(hour)
                            
                            # Tomorrow's forecast (entries 8-16)
                            if len(forecast["list"]) > 8:
                                tomorrow_temps = [entry["main"]["temp"] for entry in forecast["list"][8:16]]
                                tomorrow_entry = forecast["list"][8]
                                
                                # Check for rain in tomorrow's forecast
                                tomorrow_rain_periods = []
                                for entry in forecast["list"][8:16]:
                                    if entry.get("rain") or any(w["main"].lower() in ["rain", "drizzle"] for w in entry["weather"]):
                                        dt = datetime.fromtimestamp(entry["dt"])
                                        hour = dt.strftime("%I%p").lstrip("0").lower()
                                        tomorrow_rain_periods.append(hour)
                                
                                tomorrow_data = {
                                    "temp_min": round(min(tomorrow_temps)) if tomorrow_temps else None,
                                    "temp_max": round(max(tomorrow_temps)) if tomorrow_temps else None,
                                    "desc": tomorrow_entry["weather"][0]["description"].title(),
                                    "rain_periods": tomorrow_rain_periods[:3]  # First 3 periods
                                }

                    # Use forecast min/max if available
                    temp_min = today_min if today_min is not None else round(data["main"]["temp_min"])
                    temp_max = today_max if today_max is not None else round(data["main"]["temp_max"])
                    
                    # Build verbose weather description
                    desc = data["weather"][0]["description"]
                    humidity = data["main"]["humidity"]
                    wind_speed = round(data["wind"]["speed"] * 3.6)
                    rain_amount = data.get("rain", {}).get("1h", 0)
                    feels_like = round(data["main"]["feels_like"])
                    pressure = data["main"].get("pressure", 0)
                    clouds = data.get("clouds", {}).get("all", 0)
                    
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
                        "rain_periods": rain_periods[:3],  # First 3 rain periods
                        "wind": wind_speed,
                        "icon": data["weather"][0]["icon"],
                        "desc": desc.title(),
                        "desc_extended": verbose_desc,
                        "temp_min": temp_min,
                        "temp_max": temp_max,
                        "feels_like": feels_like,
                        "pressure": pressure,
                        "clouds": clouds,
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
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://icanhazdadjoke.com/",
                    headers={"Accept": "application/json"},
                    timeout=5,
                )
                if r.status_code == 200:
                    data = r.json()
                    joke = data.get("joke", "").strip()
                    if joke:
                        return joke
        except Exception as e:
            logger.warning(f"Joke API failed: {e}")
    return random.choice(LOCAL_JOKES)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MOOD FORECAST (DeepAI Integration)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Add this section after the get_joke() function in main.py

async def generate_mood_forecast(weather_data: dict, mood: str, day: str, location: str) -> str:
    """
    Generate a mood-based weather forecast using Groq (fastest free AI API).
    
    Args:
        weather_data: Dict containing temp_min, temp_max, desc, humidity, wind, feels_like, clouds, rain_periods
        mood: One of: "upbeat", "sarcastic", "poetic", "dad_joke", "enthusiastic", "grumpy"
        day: "today" or "tomorrow"
        location: City/suburb name
    
    Returns:
        Generated forecast string (max 40 words)
    """
    api_key = os.getenv("GROQ_API_KEY")
    
    # Fallback examples if API unavailable
    fallback_examples = {
        'upbeat_today': "Sunshine ahead! {}°-{}°C with {} making it perfect!",
        'upbeat_tomorrow': "Tomorrow looks great! {}°-{}°C with {}!",
        'sarcastic_today': "Oh wonderful, another '{}' day. {}°-{}°C.",
        'sarcastic_tomorrow': "Tomorrow: {}°-{}°C. Nature keeping us guessing with {}.",
        'poetic_today': "{} drift like secrets. {}°-{}°C beneath shifting heavens.",
        'poetic_tomorrow': "Tomorrow painted in {}°-{}°C hues, dancing with {}.",
        'dad_joke_today': "What's {}°C and full of potential? Today! Not degree-pressing with {}!",
        'dad_joke_tomorrow': "Tomorrow: {}°C with 100% chance of {} somewhere!",
        'enthusiastic_today': "WOW! AMAZING day! {}°-{}°C of PURE {} EXCELLENCE!",
        'enthusiastic_tomorrow': "TOMORROW WILL BE INCREDIBLE! {}°-{}°C of SPECTACULAR {}!",
        'grumpy_today': "Another day. {}°-{}°C with {}. Whatever.",
        'grumpy_tomorrow': "Tomorrow's {}°-{}°C. Don't expect miracles with {}."
    }
    
    temp_min = weather_data.get('temp_min', '--')
    temp_max = weather_data.get('temp_max', '--')
    conditions = weather_data.get('desc', 'conditions')
    
    if not api_key:
        logger.info("GROQ_API_KEY not set, using fallback")
        key = f"{mood}_{day}"
        template = fallback_examples.get(key, "{}°-{}°C with {}")
        return template.format(temp_min, temp_max, conditions)[:120]
    
    # Construct richer context for Groq
    mood_instructions = {
        "upbeat": "enthusiastic and positive",
        "sarcastic": "witty and dry with subtle humor",
        "poetic": "flowery and artistic with metaphors",
        "dad_joke": "include a weather pun, playful",
        "enthusiastic": "over-the-top excited, use caps",
        "grumpy": "curmudgeonly and mildly complaining"
    }
    
    day_text = "today" if day == "today" else "tomorrow"
    
    # Build rich weather context
    humidity = weather_data.get('humidity', '')
    wind = weather_data.get('wind', '')
    feels_like = weather_data.get('feels_like', '')
    clouds = weather_data.get('clouds', '')
    rain_periods = weather_data.get('rain_periods', [])
    
    weather_context = f"{conditions}, {temp_min}°-{temp_max}°C"
    if feels_like and feels_like != temp_max:
        weather_context += f" (feels like {feels_like}°C)"
    if humidity:
        weather_context += f", {humidity}% humidity"
    if wind and wind > 15:
        weather_context += f", {wind}km/h winds"
    if clouds and clouds > 70:
        weather_context += f", {clouds}% cloudy"
    if rain_periods:
        weather_context += f", rain expected around {', '.join(rain_periods[:2])}"
    weather_context += f" in {location}"
    
    prompt = f"""Write ONE SHORT weather forecast for {day_text} in a {mood_instructions.get(mood, 'casual')} style.

Weather details: {weather_context}

Requirements:
- MAXIMUM 40 words
- Single sentence only
- No greetings or preamble
- Be {mood_instructions.get(mood, 'casual')}
- Just the forecast sentence"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"🚀 Calling Groq for {mood} {day} forecast")
            
            # Groq API endpoint (OpenAI compatible)
            url = "https://api.groq.com/openai/v1/chat/completions"
            
            payload = {
                "model": "llama-3.3-70b-versatile",  # Fast and smart
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.9,
                "max_tokens": 80,
                "top_p": 0.95
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = await client.post(url, json=payload, headers=headers)
            
            logger.info(f"Groq response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract text from Groq response (OpenAI format)
                choices = result.get('choices', [])
                if choices:
                    message = choices[0].get('message', {})
                    generated_text = message.get('content', '').strip()
                    
                    # Clean and limit to 40 words
                    words = generated_text.split()[:40]
                    forecast = ' '.join(words)
                    forecast = forecast.replace('Forecast:', '').replace('Weather:', '').strip()
                    forecast = forecast.rstrip('.')  # Remove trailing period if present
                    
                    logger.info(f"✅ Generated {mood} {day} forecast: {forecast}")
                    return forecast[:200]
                
            logger.warning(f"Groq API returned status {response.status_code}")
            
    except Exception as e:
        logger.warning(f"Groq API failed: {e}")
            
    except Exception as e:
        logger.warning(f"Could not choose background from storage: {e}")
    
    return None



def get_spectra_e6_color_bias(theme: str, query: str) -> str:
    """
    Bias Unsplash queries toward Spectra-E6 friendly colors.

    Returns one of: "red", "yellow", "orange", "black_and_white"

    Rules:
    - abstract/kids/geo/paper_collage themes → red/yellow/orange
    - soft_minimal → orange or black_and_white
    - All other themes → random choice from all 4 colors
    """
    # Warm color themes (abstract, kids, geometric, paper collage)
    warm_themes = ["playful_illustrations", "retro_vibrant", "textured_artistic"]
    warm_queries = ["abstract", "geometric", "paper", "collage", "kids", "illustration", "doodle", "cartoon"]

    # Soft minimal themes
    soft_themes = ["modern_minimal", "nature_abstraction"]
    soft_queries = ["minimal", "soft", "gradient", "zen", "pastel"]

    # Check if theme matches warm categories
    if theme in warm_themes or any(q in query.lower() for q in warm_queries):
        return random.choice(["red", "yellow", "orange"])

    # Check if theme/query matches soft minimal
    elif theme in soft_themes or any(q in query.lower() for q in soft_queries):
        return random.choice(["orange", "black_and_white"])

    # Default: random choice from all options
    else:
        return random.choice(["red", "yellow", "orange", "black_and_white"])


async def download_unsplash_theme_set(theme: str = "modern_minimal", images_per_theme: int = 9) -> int:
    """
    Download a set of images for a theme from Unsplash and store in GCS.
    This is called by a scheduler/admin endpoint, not during regular renders.

    Returns: Number of images successfully downloaded
    """
    api_key = os.getenv("UNSPLASH_ACCESS_KEY")

    if not api_key or not storage_enabled:
        logger.error("Cannot download: UNSPLASH_ACCESS_KEY or GCS not configured")
        return 0

    # Theme subcategories
    theme_subcategories = {
        "modern_minimal": [
            "minimal gradient", "abstract gradient", "pastel gradient",
            "geometric minimal", "modern abstract", "color field",
            "soft gradient background", "minimal shapes", "abstract waves"
        ],
        "playful_illustrations": [
            "cute illustration", "kawaii pattern", "doodle pattern",
            "cartoon pattern", "colorful shapes", "paper craft",
            "kids illustration", "playful abstract", "flat illustration"
        ],
        "nature_abstraction": [
            "abstract nature", "watercolor abstract", "organic shapes",
            "botanical abstract", "marble texture", "ink water abstract",
            "pastel nature", "abstract landscape", "zen minimalist"
        ],
        "retro_vibrant": [
            "retro abstract", "70s pattern", "memphis design",
            "pop art abstract", "vintage geometric", "retro gradient",
            "bauhaus design", "mid century pattern", "graphic design poster"
        ],
        "textured_artistic": [
            "abstract painting", "acrylic abstract", "collage art",
            "artistic texture", "expressionist abstract", "contemporary art",
            "mixed media art", "abstract expressionism", "modern painting"
        ]
    }

    subcategories = theme_subcategories.get(theme, theme_subcategories["modern_minimal"])
    downloaded_count = 0
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i, query in enumerate(subcategories[:images_per_theme]):
            try:
                # Get Spectra-E6 color bias for this theme and query
                color_bias = get_spectra_e6_color_bias(theme, query)

                # Get random image from Unsplash with color bias
                response = await client.get(
                    "https://api.unsplash.com/photos/random",
                    params={
                        "query": query,
                        "orientation": "landscape",
                        "color": color_bias,
                        "client_id": api_key
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Use Unsplash's custom size API for optimal 800x480 display
                    # Request 800x480 with crop to fill (ensures perfect fit)
                    base_url = data["urls"]["raw"]
                    custom_url = f"{base_url}&w=800&h=480&fit=crop&crop=entropy"
                    
                    photo_id = data["id"]
                    
                    # Download image at custom size
                    img_response = await client.get(custom_url)
                    if img_response.status_code == 200:
                        # Save to GCS: backgrounds/{theme}/{index}_{photo_id}.jpg
                        blob_name = f"backgrounds/{theme}/{i}_{photo_id}.jpg"
                        blob = bucket.blob(blob_name)
                        blob.upload_from_string(
                            img_response.content,
                            content_type="image/jpeg"
                        )
                        
                        downloaded_count += 1
                        logger.info(f"  ✅ {i+1}/{images_per_theme}: {query} → {blob_name} (800x480)")
                    
                    # Respect rate limits (50/hour = ~72 seconds for 50)
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"  ❌ Failed to download {query}: {e}")
    
    logger.info(f"🎉 Downloaded {downloaded_count}/{images_per_theme} images for {theme}")
    return downloaded_count


def choose_background_from_storage(selected_theme: str = None) -> dict | None:
    """
    Choose a random background from pre-downloaded images in GCS.
    This is fast and doesn't call external APIs.
    """
    if not storage_enabled:
        return None
    
    try:
        # Default to modern_minimal if no theme specified
        if not selected_theme:
            selected_theme = "modern_minimal"
        
        # List all images for this theme
        prefix = f"backgrounds/{selected_theme}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Filter for image files
        blobs = [b for b in blobs if b.name.endswith(('.jpg', '.jpeg', '.png'))]
        
        if blobs:
            # Randomly select one
            chosen = random.choice(blobs)
            filename = chosen.name.split("/")[-1]
            
            logger.info(f"📸 Selected background: {selected_theme}/{filename}")
            
            return {
                "url": make_public_url(f"gcs/{chosen.name}"),
                "theme": selected_theme,
                "filename": filename
            }
        else:
            logger.warning(f"No images found for theme: {selected_theme}")
            
    except Exception as e:
        logger.warning(f"Could not choose background from storage: {e}")
    
    return None


def get_unsplash_themes() -> list:
    """Return list of available Unsplash themes for the designer"""
    return [
        {
            "id": "modern_minimal",
            "name": "Modern Minimal",
            "description": "Clean gradients and geometric shapes",
            "mood": "Professional, calm, modern"
        },
        {
            "id": "playful_illustrations",
            "name": "Playful Illustrations", 
            "description": "Fun, colorful, family-friendly",
            "mood": "Cheerful, playful, engaging"
        },
        {
            "id": "nature_abstraction",
            "name": "Nature Abstraction",
            "description": "Organic patterns and soft colors",
            "mood": "Zen, peaceful, calming"
        },
        {
            "id": "retro_vibrant",
            "name": "Retro Vibrant",
            "description": "Bold colors and vintage patterns",
            "mood": "Energetic, fun, nostalgic"
        },
        {
            "id": "textured_artistic",
            "name": "Textured Artistic",
            "description": "Gallery-worthy abstract art",
            "mood": "Sophisticated, creative"
        }
    ]

def filter_items_by_day(items: list, current_day: str) -> list:
    """Filter todo items based on current day of week"""
    filtered = []
    
    for item in items:
        days = item.get('days', ['all'])
        
        # Handle special keywords
        if 'all' in days:
            filtered.append(item)
        elif 'weekdays' in days and current_day in ['mon', 'tue', 'wed', 'thu', 'fri']:
            filtered.append(item)
        elif 'weekends' in days and current_day in ['sat', 'sun']:
            filtered.append(item)
        elif current_day in days:
            filtered.append(item)
    
    return filtered


def render_todo_element(elem: dict, context: dict) -> str:
    """Render todo list with multiple layout options and day filtering"""
    import html as html_lib
    from datetime import datetime
    
    layout = elem.get('layout', 'kids')
    title = elem.get('title', 'TODAY\'S MISSIONS ðŸŽ¯')
    all_items = elem.get('items', [])
    show_time = elem.get('showTime', True)
    show_emoji = elem.get('showEmoji', True)
    
    # Get current day of week
    try:
        now = datetime.fromisoformat(context.get('timestamp', datetime.now().isoformat()))
        current_day = now.strftime('%a').lower()[:3]  # 'mon', 'tue', etc.
    except:
        current_day = 'mon'
    
    # Filter items for current day
    items = filter_items_by_day(all_items, current_day)
    
    # If no items for today, show empty state
    if not items:
        return f'<div class="todo-list todo-empty" style="text-align:center; padding:20px; opacity:0.6;">' \
               f'<div style="font-size:3em;">âœ“</div>' \
               f'<div style="font-size:1.2em; margin-top:10px;">No tasks today!</div>' \
               f'</div>'
    
    # Text styling
    font_size = elem.get('fontSize', 16)
    font_family = elem.get('fontFamily', 'Inter')
    font_weight = elem.get('fontWeight', '400')
    color = elem.get('color', '#000000')
    
    # Text effects
    shadow_type = elem.get('textShadowType', 'none')
    shadow_color = elem.get('textShadowColor', '#000000')
    shadow_intensity = elem.get('textShadowIntensity', 1.0)
    
    # Build text shadow CSS
    text_shadow = ''
    if shadow_type == 'shadow':
        blur = int(shadow_intensity * 4)
        text_shadow = f'text-shadow: 2px 2px {blur}px {shadow_color};'
    elif shadow_type == 'glow':
        blur = int(shadow_intensity * 4)
        text_shadow = f'text-shadow: 0 0 {blur}px {shadow_color}, 0 0 {blur*2}px {shadow_color};'
    
    base_style = f'''
        font-size: {font_size}px;
        font-family: "{font_family}", sans-serif;
        font-weight: {font_weight};
        color: {color};
        {text_shadow}
    '''
    
    if layout == 'kids':
        return render_todo_kids_style(title, items, show_time, show_emoji, base_style, html_lib)
    elif layout == 'compact_horizontal':
        return render_todo_compact_horizontal(title, items, show_time, show_emoji, base_style, html_lib)
    elif layout == 'compact_vertical':
        return render_todo_compact_vertical(title, items, show_time, show_emoji, base_style, html_lib)
    elif layout == 'single_line':
        return render_todo_single_line(title, items, show_time, show_emoji, base_style, html_lib)
    
    return '<div>Todo element</div>'


def render_todo_kids_style(title, items, show_time, show_emoji, style, html_lib):
    """Kids style - large emojis, vertical layout"""
    html = f'<div class="todo-list todo-kids" style="{style}">'
    html += f'<div class="todo-title">{html_lib.escape(title)}</div>'
    
    for item in items:
        emoji = item.get('emoji', 'â­') if show_emoji else ''
        task = item.get('task', '')
        time_str = item.get('time', '')
        
        html += '<div class="todo-item">'
        if emoji:
            html += f'<div class="todo-emoji">{emoji}</div>'
        html += f'<div class="todo-task">{html_lib.escape(task).upper()}</div>'
        
        if show_time and time_str:
            html += f'<div class="todo-time">â° {html_lib.escape(time_str)}</div>'
        
        html += '</div>'
    
    html += '</div>'
    return html


def render_todo_compact_horizontal(title, items, show_time, show_emoji, style, html_lib):
    """Compact horizontal layout - 3 lines"""
    html = f'<div class="todo-list todo-compact-h" style="{style}">'
    html += f'<div class="todo-title">{html_lib.escape(title)}</div>'
    
    # Split items into rows (3 items per row)
    rows = [items[i:i+3] for i in range(0, len(items), 3)]
    
    for row in rows:
        html += '<div class="todo-row">'
        for i, item in enumerate(row):
            emoji = item.get('emoji', 'â­') if show_emoji else ''
            task = item.get('task', '')
            time_str = item.get('time', '')
            
            # Add separator between items
            if i > 0:
                html += ' â€¢ '
            
            html += f'{emoji} {html_lib.escape(task)}'
            if show_time and time_str:
                html += f' <span class="time">{html_lib.escape(time_str)}</span>'
        html += '</div>'
    
    html += '</div>'
    return html


def render_todo_compact_vertical(title, items, show_time, show_emoji, style, html_lib):
    """Compact vertical layout - 3 lines"""
    html = f'<div class="todo-list todo-compact-v" style="{style}">'
    html += f'<div class="todo-title">{html_lib.escape(title)}</div>'
    
    # Split items into columns
    cols = [items[i:i+2] for i in range(0, len(items), 2)]
    
    for col in cols:
        html += '<div class="todo-row">'
        for i, item in enumerate(col):
            emoji = item.get('emoji', 'â­') if show_emoji else ''
            task = item.get('task', '')
            time_str = item.get('time', '')
            
            if i > 0:
                html += ' â€¢ '
            
            if show_time and time_str:
                html += f'{html_lib.escape(time_str)} '
            html += f'{emoji} {html_lib.escape(task)}'
        html += '</div>'
    
    html += '</div>'
    return html


def render_todo_single_line(title, items, show_time, show_emoji, style, html_lib):
    """Ultra compact single line"""
    html = f'<div class="todo-list todo-single" style="{style}">'
    html += f'<span class="todo-title">{html_lib.escape(title)}</span> '
    
    for i, item in enumerate(items):
        emoji = item.get('emoji', 'â­') if show_emoji else ''
        task = item.get('task', '')[:10]  # Truncate long tasks
        time_str = item.get('time', '')
        
        if i > 0:
            html += ' â€¢ '
        
        html += f'{emoji} {html_lib.escape(task)}'
        if show_time and time_str:
            html += f' {html_lib.escape(time_str)}'
    
    html += '</div>'
    return html


@app.get("/api/todo-presets")
def get_todo_presets():
    """Return available todo presets for designer"""
    return {"presets": TODO_PRESETS}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RENDER DATA
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # Generate mood forecasts by scanning layout elements
    mood_forecasts = {}
    if layout and layout.get('elements'):
        for element in layout['elements']:
            if element.get('type') == 'FORECAST_MOOD':
                mood = element.get('forecastMood', 'upbeat')
                day = element.get('forecastDay', 'today')
                key = f"{mood}_{day}"
                
                # Only generate once per unique mood/day combination
                if key not in mood_forecasts:
                    if day == 'today' and weather:
                        weather_data = {
                            'temp_min': weather.get('temp_min'),
                            'temp_max': weather.get('temp_max'),
                            'desc': weather.get('desc', 'conditions'),
                            'humidity': weather.get('humidity'),
                            'wind': weather.get('wind'),
                            'feels_like': weather.get('feels_like'),
                            'clouds': weather.get('clouds'),
                            'rain_periods': weather.get('rain_periods', [])
                        }
                    elif day == 'tomorrow' and weather and weather.get('tomorrow'):
                        weather_data = {
                            'temp_min': weather['tomorrow'].get('temp_min'),
                            'temp_max': weather['tomorrow'].get('temp_max'),
                            'desc': weather['tomorrow'].get('desc', 'conditions'),
                            'humidity': weather['tomorrow'].get('humidity'),
                            'wind': weather['tomorrow'].get('wind'),
                            'rain_periods': weather['tomorrow'].get('rain_periods', [])
                        }
                    else:
                        # Fallback weather data
                        weather_data = {
                            'temp_min': 22, 
                            'temp_max': 28, 
                            'desc': 'conditions',
                            'humidity': 65,
                            'wind': 15
                        }
                    
                    forecast = await generate_mood_forecast(weather_data, mood, day, location_name)
                    mood_forecasts[key] = forecast
                    logger.info(f"Generated {key} forecast: {forecast}")

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

    # background - use pre-downloaded images from GCS storage
    selected_theme = layout.get("meta", {}).get("unsplashTheme", "modern_minimal")
    
    # Get background from storage (fast, no API calls)
    bg_info = choose_background_from_storage(selected_theme) if storage_enabled else None
    
    # Fallback to a default image if nothing in storage
    if bg_info:
        bg_url = bg_info["url"]
    else:
        logger.warning(f"No backgrounds found for theme: {selected_theme}, using fallback")
        bg_url = make_public_url("gcs/backgrounds/default.jpg")

    # themes list for designer
    unsplash_themes = get_unsplash_themes()

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
        "DAD_JOKE": dad_joke or "",
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
        "TOMORROW_DESC_EXTENDED": (tomorrow.get("desc_extended") or tomorrow.get("desc") or "").strip() if isinstance(tomorrow, dict) else "",
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
        "unsplash_themes": unsplash_themes,
        "svg_base": svg_base,
        "font_base": font_base,
        "icon_base": icon_base,
        "dynamic_text": dynamic_text,
        "device": device_config,
        "timestamp": now.isoformat(),
        "mood_forecasts": mood_forecasts,
        "todo_presets": TODO_PRESETS,
    }
    return context
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RENDER HTML â†’ PNG
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    
    logger.info(f"ðŸŽ¨ Rendering via: {url}")
    logger.info(f"ðŸ“Š Context data size: {len(json.dumps(context))} bytes")
    logger.info(f"ðŸ“ Layout elements: {len(context.get('layout', {}).get('elements', []))}")

    try:
        # Inject context data BEFORE page navigation using add_init_script
        # Use __RENDER_DATA__ to match what base.html expects
        context_json = json.dumps(context)
        logger.info(f"ðŸ“¦ Preparing injection, size: {len(context_json)} bytes")
        
        await page.add_init_script(f"""
            window.__RENDER_DATA__ = {context_json};
            window.renderData = {context_json};  // Also set old name for backwards compat
            console.log('âœ… __RENDER_DATA__ injected via init script');
            console.log('Elements in data:', (window.__RENDER_DATA__.layout?.elements || []).length);
        """)
        
        logger.info("ðŸ“ Init script added, now navigating to page")

        # Navigate to the page (data now exists before page loads)
        response = await page.goto(url, wait_until="networkidle", timeout=30000)
        
        if not response or response.status != 200:
            logger.error(f"Failed to load page. Status: {response.status if response else 'No response'}")
            raise RuntimeError(f"Page load failed with status {response.status if response else 'unknown'}")

        # Wait longer for SVGs and fonts to load
        await page.wait_for_timeout(2000)
        
        # Debug: Check how many elements rendered
        element_count = await page.evaluate("""
            () => document.querySelectorAll('#canvas .el').length
        """)
        logger.info(f"ðŸ“¸ Rendered elements on page: {element_count}")

        # Take screenshot
        png_bytes = await page.screenshot(type="png")

        logger.info("âœ… Render complete")
        return png_bytes

    except Exception as e:
        logger.error(f"Rendering error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        await page.close()

# ────────────────────────────────────────────────────────────────────────────
# RAW7 7-COLOUR PALETTE (FOR SPECTRA E6 PANELS)
# ────────────────────────────────────────────────────────────────────────────

# RAW7 palette for Spectra E6 e-paper displays
RAW7_PALETTE = [
    (255, 255, 255),  # 0: white
    (0, 0, 0),        # 1: black
    (220, 0, 0),      # 2: red
    (255, 216, 0),    # 3: yellow
    (0, 0, 200),      # 4: blue
    (0, 160, 0),      # 5: green
    (255, 128, 0),    # 6: orange
]


def quantize_rgb_to_raw7_index(rgb: tuple) -> int:
    """
    Quantize an RGB tuple to the closest RAW7 palette index (0-6).

    Args:
        rgb: Tuple of (r, g, b) values (0-255)

    Returns:
        Index (0-6) of the closest color in RAW7_PALETTE
    """
    r, g, b = rgb
    min_distance = float('inf')
    best_index = 0

    for idx, (pr, pg, pb) in enumerate(RAW7_PALETTE):
        # Euclidean distance in RGB space
        distance = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if distance < min_distance:
            min_distance = distance
            best_index = idx

    return best_index


def png_bytes_to_raw7(image_bytes: bytes, width: int, height: int) -> bytes:
    """
    Convert PNG image bytes to RAW7 format with Floyd-Steinberg dithering.

    Process:
    1. Load PNG from bytes
    2. Resize to (width, height)
    3. Apply Floyd-Steinberg dithering in RGB space
    4. Quantize every pixel to RAW7 palette index
    5. Pack output using RAW7 format (2 pixels per byte)

    Args:
        image_bytes: PNG image as bytes
        width: Target width
        height: Target height

    Returns:
        RAW7 encoded bytes (width * height / 2 bytes)
    """
    from PIL import Image
    import io

    # Load PNG from bytes
    img = Image.open(io.BytesIO(image_bytes))

    # Resize to target dimensions
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    # Convert to RGB if not already
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Convert to numpy array for easier manipulation
    import numpy as np
    pixels = np.array(img, dtype=np.float32)  # Use float for error diffusion

    # Floyd-Steinberg dithering
    for y in range(height):
        for x in range(width):
            old_pixel = pixels[y, x]

            # Quantize to nearest RAW7 color
            new_index = quantize_rgb_to_raw7_index(tuple(old_pixel.astype(int)))
            new_pixel = np.array(RAW7_PALETTE[new_index], dtype=np.float32)

            # Set the quantized pixel
            pixels[y, x] = new_pixel

            # Calculate quantization error
            quant_error = old_pixel - new_pixel

            # Distribute error to neighboring pixels (Floyd-Steinberg coefficients)
            if x + 1 < width:
                pixels[y, x + 1] += quant_error * 7 / 16
            if y + 1 < height:
                if x > 0:
                    pixels[y + 1, x - 1] += quant_error * 3 / 16
                pixels[y + 1, x] += quant_error * 5 / 16
                if x + 1 < width:
                    pixels[y + 1, x + 1] += quant_error * 1 / 16

    # Convert dithered pixels to RAW7 indices
    indices = []
    for y in range(height):
        for x in range(width):
            pixel = pixels[y, x].clip(0, 255).astype(int)
            index = quantize_rgb_to_raw7_index(tuple(pixel))
            indices.append(index)

    # Pack indices into RAW7 format (2 pixels per byte, high nibble first)
    raw7_bytes = bytearray()
    for i in range(0, len(indices), 2):
        high_nibble = indices[i] & 0x0F
        low_nibble = indices[i + 1] & 0x0F if i + 1 < len(indices) else 0
        byte = (high_nibble << 4) | low_nibble
        raw7_bytes.append(byte)

    return bytes(raw7_bytes)

# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# API ROUTES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        
        if storage_enabled:
            gcs_write_json(f"devices/{device}/render_data.json", data)
        
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
        # Save render_data.json beside config.json
        if storage_enabled:
            gcs_write_json(f"devices/{device}/render_data.json", data)
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

# RAW7 Render (for Spectra E6 e-paper displays)
@app.get("/v1/raw7")
async def api_raw7(device: str = "familydisplay"):
    """
    Render frame in RAW7 format for Spectra E6 e-paper displays.

    Process:
    1. Build render data using existing build_render_data()
    2. Render HTML to PNG using existing render_html_to_png()
    3. Convert PNG to RAW7 using png_bytes_to_raw7()
    4. Return RAW7 bytes as application/octet-stream
    5. Save to GCS at devices/{device}/renders/latest.raw7 (if enabled)
    """
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    try:
        # Step 1: Build render data
        data = await build_render_data(device)

        # Save render_data.json
        if storage_enabled:
            gcs_write_json(f"devices/{device}/render_data.json", data)

        # Step 2: Render HTML to PNG
        render_path = Path(RENDER_PATH)
        if not render_path.exists():
            render_path = BASE_DIR / "web" / "layouts" / "base.html"
        png_bytes = await render_html_to_png(str(render_path), data)

        # Step 3: Convert PNG to RAW7
        raw7_bytes = png_bytes_to_raw7(png_bytes, RENDER_WIDTH, RENDER_HEIGHT)

        # Step 4: Save to GCS (if enabled)
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.raw7"
            gcs_write_bytes(render_key, raw7_bytes, content_type="application/octet-stream")
            logger.info(f"💾 Saved RAW7 render: {render_key} ({len(raw7_bytes)} bytes)")

        # Step 5: Return RAW7 bytes
        logger.info(f"✅ RAW7 render complete: {len(raw7_bytes)} bytes ({RENDER_WIDTH}x{RENDER_HEIGHT})")
        return Response(content=raw7_bytes, media_type="application/octet-stream")

    except Exception as e:
        logger.error(f"Failed to render RAW7 frame: {e}")
        logger.error(traceback.format_exc())
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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DESIGNER ROUTE (LOADS HTML DIRECTLY FROM GCS)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/designer/", response_class=HTMLResponse)
async def designer():
    """Serve Designer HTML directly from GCS bucket."""
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="Storage not configured")

    designer_key = "web/designer/overlay_designer_v4_clean.html"
    try:
        html_content = gcs_read_text(designer_key)
        logger.info(f"âœ… Designer loaded from {designer_key}")
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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STATIC MOUNTS (optional in-container dev)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

try:
    presets_dir = resolve_static_dir("web/presets", "backend/web/presets")
    if presets_dir and presets_dir.is_dir():
        app.mount("/presets", StaticFiles(directory=str(presets_dir)), name="presets")
        logger.info(f"âœ“ Mounted /presets from {presets_dir}")
except Exception as e:
    logger.warning(f"Could not mount /presets: {e}")

try:
    fonts_dir = resolve_static_dir("web/fonts", "backend/web/fonts")
    if fonts_dir and fonts_dir.is_dir():
        app.mount("/fonts", StaticFiles(directory=str(fonts_dir)), name="fonts")
        logger.info(f"âœ“ Mounted /fonts from {fonts_dir}")
except Exception as e:
    logger.warning(f"Could not mount /fonts: {e}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GCS ASSET PROXY
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ADMIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DEVICE MANAGEMENT ROUTES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    Copy assets/default.json â†’ devices/<device_id>/layouts/current.json
    (idempotent; overwrites existing file)
    """
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="GCS not enabled")
    try:
        default_layout = gcs_read_json(DEFAULT_LAYOUT_KEY)
        gcs_write_json(f"devices/{device_id}/layouts/current.json", default_layout)
        logger.info(f"âœ… Initialized layout for {device_id} from default.json")
        return {"status": "ok", "device": device_id}
    except Exception as e:
        logger.error(f"Failed to initialize layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# API HELPER ROUTES (for designer)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

@app.get("/api/list-unsplash-themes")
def list_unsplash_themes():
    """List available Unsplash theme sets."""
    themes = get_unsplash_themes()
    return {"themes": themes}

@app.post("/admin/download-theme-backgrounds")
async def admin_download_backgrounds(token: str = None, theme: str = "modern_minimal", count: int = 9):
    """
    Admin endpoint to download backgrounds for a theme from Unsplash to GCS.
    Usage: POST /admin/download-theme-backgrounds?token=XXX&theme=modern_minimal&count=9
    """
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        downloaded = await download_unsplash_theme_set(theme, count)
        return {
            "status": "success",
            "theme": theme,
            "downloaded": downloaded,
            "total": count
        }
    except Exception as e:
        logger.error(f"Failed to download backgrounds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/download-all-themes")
async def admin_download_all_themes(token: str = None, count: int = 9):
    """
    Admin endpoint to download backgrounds for ALL themes.
    Usage: POST /admin/download-all-themes?token=XXX&count=9
    """
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    themes = ["modern_minimal", "playful_illustrations", "nature_abstraction", "retro_vibrant", "textured_artistic"]
    results = {}
    
    for theme in themes:
        try:
            downloaded = await download_unsplash_theme_set(theme, count)
            results[theme] = {"downloaded": downloaded, "total": count}
            logger.info(f"âœ… Completed theme: {theme}")
        except Exception as e:
            results[theme] = {"error": str(e)}
            logger.error(f"âŒ Failed theme: {theme} - {e}")
    
    return {
        "status": "completed",
        "results": results
    }

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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


@app.post("/v1/frame_bg_reroll")
async def frame_bg_reroll(
    device: str = Query("familydisplay"),
    theme: str | None = Query(None)
):
    """
    Uses cached render_data.json for the device,
    swaps only the background, renders a new PNG.
    No external API calls.
    """
    key = f"devices/{device}/render_data.json"
    render_data = gcs_read_json(key)
    if not render_data:
        # Fallback: build once to seed cache (this will call external APIs only this first time)
        try:
            render_data = await build_render_data(device=device)
            if storage_enabled:
                gcs_write_json(key, render_data)
        except Exception:
            raise HTTPException(status_code=404, detail="No cached render_data found for this device")

    selected_theme = theme or (render_data.get("layout", {}).get("meta", {}) or {}).get("unsplashTheme") or "modern_minimal"

    bg = choose_background_from_storage(selected_theme)
    if not bg:
        raise HTTPException(status_code=404, detail="No backgrounds available for selected theme")

    render_data["bg_url"] = bg["url"]

    render_path = Path(RENDER_PATH)
    if not render_path.exists():
        render_path = BASE_DIR / "web" / "layouts" / "base.html"

    png_bytes = await render_html_to_png(str(render_path), render_data)

    if storage_enabled:
        gcs_write_bytes(f"devices/{device}/renders/latest.png", png_bytes)
        gcs_write_json(key, render_data)

    return Response(content=png_bytes, media_type="image/png")

@app.get("/v1/frame_bg_reroll_browser")
async def frame_bg_reroll_browser(
    device: str = Query("familydisplay"),
    theme: str | None = Query(None)
):
    """Browser-friendly background reroll.
    Performs the same logic as /v1/frame_bg_reroll and then redirects
    to the updated PNG with a cache-buster so you see the new image immediately.
    """
    await frame_bg_reroll(device=device, theme=theme)
    ts = int(datetime.now(timezone.utc).timestamp())
    png_url = f"/gcs/devices/{device}/renders/latest.png?t={ts}"
    return RedirectResponse(png_url)



@app.get("/v1/render_data_save")
async def render_data_save(device: str = Query("familydisplay")):
    """
    Build full render_data and also save to devices/<device>/render_data.json.
    Use this if you want to seed/refresh the cached JSON explicitly.
    """
    render_data = await build_render_data(device=device)
    if storage_enabled:
        gcs_write_json(f"devices/{device}/render_data.json", render_data)
    return render_data

