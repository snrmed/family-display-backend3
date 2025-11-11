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
RENDER_PATH = os.getenv("RENDER_PATH", "/layouts/base.html")

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

def gcs_write_bytes(key: str, data: bytes, content_type: str = "image/png"):
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
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

async def get_uv_index(lat: float, lon: float) -> dict:
    """
    Get UV index from OpenWeather One Call API.
    Note: This requires One Call API access (may need subscription).
    Returns dict with 'uvi' key or empty dict if unavailable.
    """
    api_key = os.getenv("OPENWEATHER_KEY")
    
    if not api_key:
        return {}
    
    try:
        async with httpx.AsyncClient() as client:
            # Try One Call API 3.0 (current weather + forecast)
            url = "https://api.openweathermap.org/data/3.0/onecall"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "exclude": "minutely,hourly,daily,alerts"  # Only get current
            }
            
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                uvi = data.get("current", {}).get("uvi")
                if uvi is not None:
                    return {"uvi": round(uvi, 1)}
            elif response.status_code == 401:
                # One Call API not available, try legacy UV endpoint
                logger.info("One Call API not available, UV index will be skipped")
                
    except Exception as e:
        logger.debug(f"UV index fetch failed (this is optional): {e}")
    
    return {}

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
                            # Today's detailed forecast from first 8 entries (24 hours)
                            today_entries = forecast["list"][:8]
                            today_temps = [entry["main"]["temp"] for entry in today_entries]
                            today_min = round(min(today_temps)) if today_temps else None
                            today_max = round(max(today_temps)) if today_temps else None
                            
                            # Today's additional data
                            today_humidity = round(sum(e["main"]["humidity"] for e in today_entries) / len(today_entries))
                            today_wind = round(sum(e["wind"]["speed"] for e in today_entries) / len(today_entries) * 3.6)
                            
                            # Today's rain timing
                            today_rain_hours = []
                            for entry in today_entries:
                                if "rain" in entry and entry["rain"].get("3h", 0) > 0:
                                    # Extract hour from dt_txt (e.g., "2025-11-10 15:00:00")
                                    time_str = entry.get("dt_txt", "")
                                    if time_str:
                                        hour = int(time_str.split()[1].split(":")[0])
                                        today_rain_hours.append(hour)
                            
                            # Tomorrow's forecast (entries 8-16)
                            tomorrow_data = None
                            if len(forecast["list"]) > 8:
                                tomorrow_entries = forecast["list"][8:16]
                                tomorrow_temps = [entry["main"]["temp"] for entry in tomorrow_entries]
                                tomorrow_entry = forecast["list"][8]
                                
                                tomorrow_humidity = round(sum(e["main"]["humidity"] for e in tomorrow_entries) / len(tomorrow_entries))
                                tomorrow_wind = round(sum(e["wind"]["speed"] for e in tomorrow_entries) / len(tomorrow_entries) * 3.6)
                                
                                # Tomorrow's rain timing
                                tomorrow_rain_hours = []
                                for entry in tomorrow_entries:
                                    if "rain" in entry and entry["rain"].get("3h", 0) > 0:
                                        time_str = entry.get("dt_txt", "")
                                        if time_str:
                                            hour = int(time_str.split()[1].split(":")[0])
                                            tomorrow_rain_hours.append(hour)
                                
                                tomorrow_data = {
                                    "temp_min": round(min(tomorrow_temps)) if tomorrow_temps else None,
                                    "temp_max": round(max(tomorrow_temps)) if tomorrow_temps else None,
                                    "desc": tomorrow_entry["weather"][0]["description"].title(),
                                    "humidity": tomorrow_humidity,
                                    "wind": tomorrow_wind,
                                    "rain_hours": tomorrow_rain_hours,
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
                    elif "storm" in desc.lower() or "thunder" in desc.lower():
                        verbose_desc += "Stormy conditions possible. "
                    elif "cloud" in desc.lower():
                        verbose_desc += "Cloudy skies throughout. "
                    else:
                        verbose_desc += "Clear conditions expected. "
                    
                    # Tomorrow's extended description
                    if tomorrow_data:
                        tmr_desc = tomorrow_data["desc"].lower()
                        tomorrow_verbose = f"Tomorrow expecting {tomorrow_data['desc']} with temperatures from {tomorrow_data['temp_min']}°C to {tomorrow_data['temp_max']}°C. "
                        
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
                    
                    # Try to get UV index (optional, may not be available on all plans)
                    uv_data = await get_uv_index(actual_lat, actual_lon)
                    uvi = uv_data.get("uvi")

                    return {
                        "humidity": today_humidity if 'today_humidity' in locals() else humidity,
                        "rain": rain_amount,
                        "wind": today_wind if 'today_wind' in locals() else wind_speed,
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
                        "rain_hours": today_rain_hours if 'today_rain_hours' in locals() else [],
                        "uvi": uvi,
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
                    return r.json()["joke"]
        except Exception as e:
            logger.warning(f"Joke API failed: {e}")
    return random.choice(LOCAL_JOKES)

# ──────────────────────────────────────────────────────────────────────────────
# MOOD FORECAST (DeepAI Integration)
# ──────────────────────────────────────────────────────────────────────────────

async def generate_mood_forecast(weather_data: dict, mood: str, day: str, location: str) -> str:
    """
    Generate a mood-based weather forecast using DeepAI API.
    
    Args:
        weather_data: Dict containing temp_min, temp_max, desc, humidity, wind, rain_hours
        mood: One of: "upbeat", "sarcastic", "poetic", "dad_joke", "enthusiastic", "grumpy"
        day: "today" or "tomorrow"
        location: City/suburb name
    
    Returns:
        Generated forecast string (max 30 words)
    """
    api_key = os.getenv("DEEPAI_API_KEY")
    
    # Fallback examples if API unavailable
    fallback_examples = {
        'upbeat_today': "Sunshine and smiles ahead! {}°-{}°C with {} making it perfect for adventures!",
        'upbeat_tomorrow': "Tomorrow's looking fantastic! {}°-{}°C with {} for a great day!",
        'sarcastic_today': "Oh wonderful, another '{}' day. {}°-{}°C if you're wondering.",
        'sarcastic_tomorrow': "Tomorrow: {}°-{}°C. Nature's way of keeping us guessing with {}.",
        'poetic_today': "{} drift like whispered secrets. {}°-{}°C beneath shifting heavens.",
        'poetic_tomorrow': "Tomorrow's canvas painted in {}°-{}°C hues, dancing with {}.",
        'dad_joke_today': "What's {}°C and full of potential? Today! Why? Because it's not degree-pressing with {}!",
        'dad_joke_tomorrow': "Tomorrow's forecast: {}°C with 100% chance of {} somewhere!",
        'enthusiastic_today': "WOW! AMAZING day ahead folks! {}°-{}°C of PURE {} EXCELLENCE!",
        'enthusiastic_tomorrow': "TOMORROW IS GOING TO BE INCREDIBLE! {}°-{}°C of SPECTACULAR {}!",
        'grumpy_today': "Another day. {}°-{}°C with {}. Could be worse. Could be better. Whatever.",
        'grumpy_tomorrow': "Tomorrow's {}°-{}°C. Don't expect miracles with {}. It's just weather."
    }
    
    temp_min = weather_data.get('temp_min', '--')
    temp_max = weather_data.get('temp_max', '--')
    conditions = weather_data.get('desc', 'conditions')
    humidity = weather_data.get('humidity')
    wind = weather_data.get('wind')
    rain_hours = weather_data.get('rain_hours', [])
    uvi = weather_data.get('uvi')
    
    if not api_key:
        logger.info("DEEPAI_API_KEY not set, using fallback examples")
        key = f"{mood}_{day}"
        template = fallback_examples.get(key, "Weather forecast: {}°-{}°C with {}")
        result = template.format(temp_min, temp_max, conditions)
        return result[:100]  # Ensure max length
    
    # Construct detailed prompt for DeepAI
    mood_instructions = {
        "upbeat": "enthusiastic and positive, focusing on the bright side",
        "sarcastic": "witty and dry, with subtle humor about the weather",
        "poetic": "flowery and artistic, using metaphors and imagery",
        "dad_joke": "include a weather-related pun, playful and silly",
        "enthusiastic": "over-the-top excited like a TV weather presenter, use caps",
        "grumpy": "curmudgeonly and mildly complaining about conditions"
    }
    
    day_text = "today" if day == "today" else "tomorrow"
    
    # Build detailed weather context
    weather_context = f"{conditions}, {temp_min}°-{temp_max}°C"
    
    details = []
    if humidity is not None:
        details.append(f"{humidity}% humidity")
    if wind is not None:
        details.append(f"{wind}km/h winds")
    if uvi is not None:
        # UV Index interpretation
        if uvi >= 11:
            uv_desc = "extreme UV"
        elif uvi >= 8:
            uv_desc = "very high UV"
        elif uvi >= 6:
            uv_desc = "high UV"
        elif uvi >= 3:
            uv_desc = "moderate UV"
        else:
            uv_desc = "low UV"
        details.append(f"UV index {uvi} ({uv_desc})")
    
    # Rain timing information
    if rain_hours:
        if len(rain_hours) == 1:
            details.append(f"rain around {rain_hours[0]:02d}:00")
        elif len(rain_hours) == 2:
            details.append(f"rain around {rain_hours[0]:02d}:00 and {rain_hours[1]:02d}:00")
        elif len(rain_hours) > 2:
            # Group into morning/afternoon/evening
            morning = [h for h in rain_hours if 6 <= h < 12]
            afternoon = [h for h in rain_hours if 12 <= h < 18]
            evening = [h for h in rain_hours if 18 <= h < 24]
            
            rain_periods = []
            if morning:
                rain_periods.append("morning")
            if afternoon:
                rain_periods.append("afternoon")
            if evening:
                rain_periods.append("evening")
            
            if rain_periods:
                details.append(f"rain in the {' and '.join(rain_periods)}")
    
    if details:
        weather_context += f" ({', '.join(details)})"
    
    prompt = f"""Generate a weather forecast for {location} for {day_text} in a {mood} tone.

Weather: {weather_context}

Style: {mood_instructions.get(mood, 'casual')}

Maximum 30 words. Single focused statement suitable for e-ink display. Do NOT include greetings or sign-offs. Make it engaging and mention the most interesting weather details."""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.deepai.org/api/text-generator',
                data={'text': prompt},
                headers={'api-key': api_key},
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('output', '').strip()
                
                # Clean up and limit to 30 words
                words = generated_text.split()[:30]
                forecast = ' '.join(words)
                
                # Remove common prefixes/suffixes
                forecast = forecast.replace('Forecast:', '').replace('Weather:', '').strip()
                
                logger.info(f"Generated {mood} {day} forecast: {forecast}")
                return forecast
            else:
                logger.warning(f"DeepAI API returned status {response.status_code}")
                raise Exception(f"API error: {response.status_code}")
                
    except Exception as e:
        logger.error(f"DeepAI forecast generation failed: {e}")
        # Return fallback
        key = f"{mood}_{day}"
        template = fallback_examples.get(key, "Weather forecast: {}°-{}°C with {}")
        result = template.format(temp_min, temp_max, conditions)
        return result[:100]

# ──────────────────────────────────────────────────────────────────────────────
# PEXELS
# ──────────────────────────────────────────────────────────────────────────────

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

    # Format date
    date_str = now.strftime("%A, %B %d, %Y")

    # ─────────────────────────────────────────────────────────────────────
    # MOOD FORECASTS - Process layout elements
    # ─────────────────────────────────────────────────────────────────────
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
                            'rain_hours': weather.get('rain_hours', []),
                            'uvi': weather.get('uvi')
                        }
                    elif day == 'tomorrow' and weather and weather.get('tomorrow'):
                        weather_data = {
                            'temp_min': weather['tomorrow'].get('temp_min'),
                            'temp_max': weather['tomorrow'].get('temp_max'),
                            'desc': weather['tomorrow'].get('desc', 'conditions'),
                            'humidity': weather['tomorrow'].get('humidity'),
                            'wind': weather['tomorrow'].get('wind'),
                            'rain_hours': weather['tomorrow'].get('rain_hours', []),
                            'uvi': None  # UV index typically only for current day
                        }
                    else:
                        weather_data = {
                            'temp_min': 22, 
                            'temp_max': 28, 
                            'desc': 'conditions',
                            'humidity': 65,
                            'wind': 15,
                            'rain_hours': [],
                            'uvi': None
                        }
                    
                    forecast = await generate_mood_forecast(weather_data, mood, day, location_name)
                    mood_forecasts[key] = forecast
                    logger.info(f"Generated {key} forecast: {forecast}")

    # ─────────────────────────────────────────────────────────────────────
    # Build dynamic_text mapping
    # ─────────────────────────────────────────────────────────────────────
    w = weather
    tomorrow = w.get("tomorrow", {})
    
    def _fmt_temp(t):
        return f"{int(round(t))}°C" if t is not None else "--°C"
    
    def _fmt_minmax(tmin, tmax):
        if tmin is not None and tmax is not None:
            return f"{int(round(tmin))}° / {int(round(tmax))}°"
        return "--° / --°"
    
    def _fmt_speed(s):
        return f"{int(round(s))} km/h" if s is not None else "-- km/h"
    
    def _fmt_rain(r):
        return f"{r} mm" if r is not None else "-- mm"
    
    def _icon_url():
        return w.get("icon_url", "")

    dynamic_text = {
        "CITY": location_name,
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
        "TOMORROW_DESC_EXTENDED": (tomorrow.get("desc_extended") or "").strip() if isinstance(tomorrow, dict) else "",
        "TOMORROW_TEMP": _fmt_minmax(tomorrow.get("temp_min"), tomorrow.get("temp_max")) if isinstance(tomorrow, dict) else "",
        "CUSTOM": "",
        "ENABLE_OPENWEATHER": "true" if os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true" else "false",
        "OPENWEATHER_KEY": os.getenv("OPENWEATHER_KEY", ""),
    }

    # Add mood forecasts to dynamic_text
    for key, forecast in mood_forecasts.items():
        dynamic_text[f"FORECAST_{key.upper()}"] = forecast

    svg_base = make_public_url("gcs/assets/svgs")
    font_base = make_public_url("fonts")
    icon_base = make_public_url(f"gcs/assets/weather-icons/{icon_theme}")

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
        "mood_forecasts": mood_forecasts,  # Include for debugging
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
    # Build a proper HTTP URL from the provided render_path
    path = render_path or "/layouts/base.html"

    # If caller passed a full URL, use it as-is
    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        # Treat anything else as a served URL path (not a container file path)
        # Normalize to the known route we expose for base.html
        if path.endswith("base.html"):
            path = "/layouts/base.html"
        if not path.startswith("/"):
            path = "/" + path
        url = f"{public_base}{path}"

    logger.info(f"🎨 Rendering via: {url}")
    logger.info(f"📊 Context data size: {len(json.dumps(context))} bytes")
    logger.info(f"📐 Layout elements: {len(context.get('layout', {}).get('elements', []))}")

    try:
        # Navigate to the page first
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if not response or response.status != 200:
            logger.error(f"Failed to load page. Status: {response.status if response else 'No response'}")
            raise RuntimeError(f"Page load failed with status {response.status if response else 'unknown'}")

        # Inject the context data
        await page.evaluate(
            """(data) => { window.renderData = data; }""",
            context
        )

        # Wait a bit for rendering
        await page.wait_for_timeout(1000)

        # Take screenshot
        png_bytes = await page.screenshot(type="png")

        logger.info("✅ Render complete")
        return png_bytes

    except Exception as e:
        logger.error(f"Rendering error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        await page.close()

# ──────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ──────────────────────────────────────────────────────────────────────────────

# Device Config
@app.get("/v1/devices/{device_id}/config")
async def api_get_device_config(device_id: str):
    try:
        config = get_device_config(device_id)
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/devices/{device_id}/config")
async def api_save_device_config(device_id: str, request: Request):
    try:
        config = await request.json()
        save_device_config(device_id, config)
        return {"status": "saved", "device_id": device_id}
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Device Layout
@app.get("/v1/devices/{device_id}/layouts/current")
async def api_get_layout(device_id: str):
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
        render_path = os.getenv("RENDER_PATH", "/layouts/base.html")
        png_bytes = await render_html_to_png(render_path, data)
        
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes)
        
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Frame render error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/admin/render_now")
async def admin_render_now(token: str = None, device: str = "familydisplay"):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        data = await build_render_data(device)
        render_path = os.getenv("RENDER_PATH", "/layouts/base.html")
        png_bytes = await render_html_to_png(render_path, data)
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
            url = "http://api.openweathermap.org/geo/1.0/direct"
            params = {"q": q, "limit": 5, "appid": api_key}
            
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                results = response.json()
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
    """List available preset layouts."""
    if not storage_enabled:
        return {"presets": []}
    try:
        blobs = bucket.list_blobs(prefix="assets/layouts/")
        presets = []
        for blob in blobs:
            filename = blob.name.split("/")[-1]
            if filename.endswith(".json") and filename != "default.json":
                presets.append(filename.replace(".json", ""))
        return {"presets": presets}
    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        return {"presets": []}

# ──────────────────────────────────────────────────────────────────────────────
# DESIGNER ROUTE
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/designer/")
async def serve_designer():
    """Serve the designer HTML from GCS."""
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
# STATIC MOUNTS
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GCS proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
