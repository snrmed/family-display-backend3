import os
import json
import random
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.cloud import storage
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kin:D Family Display Backend v4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# CONFIGURATION
# ============================================================================

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

# UPDATED: Expanded Pexels categories
PEXELS_CATEGORIES = [
    "abstract",
    "geometric",
    "paper-collage",
    "kids-shapes",
    "minimal"
]

LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
]

# Storage
storage_enabled = False
bucket = None
playwright_browser = None

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"✓ GCS enabled: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"GCS disabled: {e}")

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright
        logger.info("✓ Playwright available")
    except ImportError:
        logger.warning("Playwright not installed, rendering disabled")
        ENABLE_RENDERING = False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def make_public_url(path: str) -> str:
    """Create public URL for asset"""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    
    if PUBLIC_BASE_URL:
        base = PUBLIC_BASE_URL.rstrip("/")
        return f"{base}/{path.lstrip('/')}"
    
    return f"/{path.lstrip('/')}"

def resolve_weather_icon_url(theme: str, icon_code: str) -> str:
    """Resolve weather icon URL"""
    if storage_enabled:
        return make_public_url(f"gcs/assets/weather-icons/{theme}/{icon_code}.svg")
    return make_public_url(f"designer/weather-icons/{theme}/{icon_code}.svg")

def gcs_read_json(key: str) -> dict:
    """Read JSON from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return json.loads(blob.download_as_text(encoding='utf-8'))

def gcs_write_json(key: str, data: dict):
    """Write JSON to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    logger.info(f"✓ Wrote JSON to {key}")

def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Write bytes to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"✓ Wrote {len(data)} bytes to {key}")

# ============================================================================
# DEVICE CONFIG
# ============================================================================

def get_device_config(device_id: str) -> dict:
    """Get device configuration"""
    key = f"devices/{device_id}/config.json"
    
    try:
        return gcs_read_json(key)
    except FileNotFoundError:
        # Return default config for Darwin
        logger.info(f"Creating default config for device: {device_id}")
        default_config = {
            "deviceId": device_id,
            "location": {
                "city": "Darwin",
                "timezone": "Australia/Darwin"
            },
            "preferences": {
                "iconTheme": DEFAULT_ICON_THEME
            }
        }
        # Save it
        try:
            gcs_write_json(key, default_config)
        except:
            pass
        return default_config

def save_device_config(device_id: str, config: dict):
    """Save device configuration"""
    key = f"devices/{device_id}/config.json"
    
    # Validate config
    if "location" not in config or "city" not in config["location"]:
        raise ValueError("Config must include location.city")
    
    gcs_write_json(key, config)
    logger.info(f"✓ Saved device config for {device_id}")

# ============================================================================
# DATA PROVIDERS
# ============================================================================

async def generate_extended_description(city: str, lat: float, lon: float, api_key: str, current_data: dict) -> str:
    """Generate extended weather description from forecast - NEW"""
    try:
        async with httpx.AsyncClient() as client:
            # Get forecast
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
            forecast_resp = await client.get(forecast_url, timeout=5)
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()
            
            # Current description
            current_desc = current_data["weather"][0]["description"].title()
            current_temp = round(current_data["main"]["temp"])
            
            # Analyze next 6-9 hours (next 3 forecast entries)
            rain_chance = 0
            max_rain = 0
            temp_trend = []
            
            for i, entry in enumerate(forecast_data["list"][:3]):
                # Rain probability
                if "pop" in entry:
                    rain_chance = max(rain_chance, entry["pop"] * 100)
                
                # Rain amount
                if "rain" in entry:
                    max_rain = max(max_rain, entry["rain"].get("3h", 0))
                
                # Temperature trend
                temp_trend.append(round(entry["main"]["temp"]))
            
            # Build description
            parts = [f"{current_desc}, {current_temp}°C"]
            
            # Add rain forecast
            if rain_chance > 30:
                if max_rain > 5:
                    parts.append(f"{round(rain_chance)}% chance of heavy rain later")
                elif max_rain > 0:
                    parts.append(f"{round(rain_chance)}% chance of rain later")
                else:
                    parts.append(f"{round(rain_chance)}% chance of showers later")
            
            # Add temperature trend
            if len(temp_trend) >= 3:
                future_temp = temp_trend[-1]
                temp_change = future_temp - current_temp
                
                if temp_change >= 4:
                    parts.append(f"warming to {future_temp}°C")
                elif temp_change <= -4:
                    parts.append(f"cooling to {future_temp}°C")
            
            return " with ".join(parts) if len(parts) > 1 else parts[0]
    
    except Exception as e:
        logger.warning(f"Extended description failed: {e}")
        return f"{current_desc}, {current_temp}°C"


async def get_tomorrow_forecast(city: str, lat: float, lon: float, api_key: str, tz_offset: int) -> dict:
    """Get tomorrow's weather forecast - NEW"""
    try:
        async with httpx.AsyncClient() as client:
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
            forecast_resp = await client.get(forecast_url, timeout=5)
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()
            
            # Get tomorrow's date in local timezone
            local_timezone = timezone(timedelta(seconds=tz_offset))
            tomorrow_date = (
                datetime.now(timezone.utc)
                .astimezone(local_timezone)
                + timedelta(days=1)
            ).date()
            
            # Find all entries for tomorrow
            tomorrow_entries = []
            for entry in forecast_data.get("list", []):
                dt_val = entry.get("dt")
                if dt_val:
                    local_dt = datetime.fromtimestamp(dt_val, tz=timezone.utc).astimezone(local_timezone)
                    if local_dt.date() == tomorrow_date:
                        tomorrow_entries.append(entry)
            
            if not tomorrow_entries:
                return None
            
            # Calculate tomorrow's min/max temps
            temps = [round(e["main"]["temp"]) for e in tomorrow_entries]
            
            # Get most common weather condition for tomorrow
            conditions = [e["weather"][0]["description"] for e in tomorrow_entries]
            most_common = max(set(conditions), key=conditions.count)
            
            # Check for rain tomorrow
            rain_chance = max([e.get("pop", 0) * 100 for e in tomorrow_entries])
            
            # Build tomorrow's description
            desc_parts = [f"{most_common.title()}, {min(temps)}°-{max(temps)}°C"]
            if rain_chance > 30:
                desc_parts.append(f"{round(rain_chance)}% chance of rain")
            
            return {
                "temp_min": min(temps),
                "temp_max": max(temps),
                "desc": " with ".join(desc_parts),
                "icon": tomorrow_entries[len(tomorrow_entries)//2]["weather"][0]["icon"]
            }
    
    except Exception as e:
        logger.warning(f"Tomorrow forecast failed: {e}")
        return None


async def get_weather(city: str) -> dict:
    """Get weather data with extended description and tomorrow's forecast - UPDATED"""
    if ENABLE_OPENWEATHER:
        api_key = os.getenv("OPENWEATHER_KEY")
        if api_key:
            try:
                async with httpx.AsyncClient() as client:
                    # Current weather
                    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},AU&appid={api_key}&units=metric"
                    r = await client.get(url, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        weather: dict[str, Any] = {
                            "temp": round(data["main"].get("temp", 0)),
                            "feels_like": round(data["main"].get("feels_like", 0)),
                            "humidity": data.get("main", {}).get("humidity"),
                            "rain": data.get("rain", {}).get("1h", 0),
                            "wind": round(data.get("wind", {}).get("speed", 0)),
                            "icon": data.get("weather", [{}])[0].get("icon", "01d"),
                            "desc": data.get("weather", [{}])[0].get("description", "").title() or "Sunny",
                        }

                        tz_offset = data.get("timezone", 0)
                        weather["timezone_offset"] = tz_offset

                        # Get coordinates
                        coord = data.get("coord", {})
                        lat = coord.get("lat")
                        lon = coord.get("lon")

                        if lat is not None and lon is not None:
                            # Get today's min/max from forecast
                            try:
                                forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
                                forecast_resp = await client.get(forecast_url, timeout=5)
                                forecast_resp.raise_for_status()
                                forecast_data = forecast_resp.json()

                                target_date = (
                                    datetime.now(timezone.utc)
                                    .astimezone(timezone(timedelta(seconds=tz_offset)))
                                    .date()
                                )

                                min_samples: list[float] = []
                                max_samples: list[float] = []
                                local_timezone = timezone(timedelta(seconds=tz_offset))

                                for entry in forecast_data.get("list", []):
                                    dt_val = entry.get("dt")
                                    if dt_val is None:
                                        continue

                                    local_dt = datetime.fromtimestamp(dt_val, tz=timezone.utc).astimezone(local_timezone)
                                    if local_dt.date() != target_date:
                                        continue

                                    main_block = entry.get("main", {})
                                    min_val = main_block.get("temp_min")
                                    max_val = main_block.get("temp_max")

                                    if isinstance(min_val, (int, float)):
                                        min_samples.append(float(min_val))
                                    if isinstance(max_val, (int, float)):
                                        max_samples.append(float(max_val))

                                if min_samples:
                                    weather["temp_min"] = round(min(min_samples))
                                if max_samples:
                                    weather["temp_max"] = round(max(max_samples))
                                    
                            except Exception as exc:
                                logger.warning(f"OpenWeather forecast failed: {exc}")
                                api_min = data.get("main", {}).get("temp_min")
                                api_max = data.get("main", {}).get("temp_max")
                                if isinstance(api_min, (int, float)):
                                    weather["temp_min"] = round(api_min)
                                if isinstance(api_max, (int, float)):
                                    weather["temp_max"] = round(api_max)

                            # NEW: Generate extended description
                            try:
                                extended_desc = await generate_extended_description(
                                    city, lat, lon, api_key, data
                                )
                                weather["desc_extended"] = extended_desc
                            except Exception as e:
                                logger.warning(f"Extended description failed: {e}")
                                weather["desc_extended"] = weather["desc"]
                            
                            # NEW: Get tomorrow's forecast
                            try:
                                tomorrow = await get_tomorrow_forecast(city, lat, lon, api_key, tz_offset)
                                if tomorrow:
                                    weather["tomorrow"] = tomorrow
                            except Exception as e:
                                logger.warning(f"Tomorrow forecast failed: {e}")

                        # Ensure temp_min and temp_max exist
                        if "temp_min" not in weather:
                            weather["temp_min"] = weather["temp"]
                        if "temp_max" not in weather:
                            weather["temp_max"] = weather["temp"]

                        return weather
            except Exception as e:
                logger.warning(f"OpenWeather failed: {e}")

    # Fallback data
    return {
        "temp": 33,
        "feels_like": 33,
        "humidity": 45,
        "rain": 0,
        "wind": 5,
        "icon": "01d",
        "desc": "Sunny",
        "desc_extended": "Sunny with clear skies",
        "temp_min": 30,
        "temp_max": 36,
        "timezone_offset": 0,
    }


async def get_joke() -> str:
    """Get dad joke"""
    if ENABLE_JOKES_API:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://icanhazdadjoke.com/",
                    headers={"Accept": "application/json"},
                    timeout=5
                )
                if r.status_code == 200:
                    return r.json()["joke"]
        except Exception as e:
            logger.warning(f"Joke API failed: {e}")
    
    return random.choice(LOCAL_JOKES)


def choose_pexels_background(category: str = None) -> dict:
    """Choose a random Pexels image from specified category - FIXED"""
    if not storage_enabled:
        return None
    
    try:
        # Default to first category if none specified
        if not category or category not in PEXELS_CATEGORIES:
            category = PEXELS_CATEGORIES[0]
        
        # List all files in the category folder
        prefix = f"pexels/current/{category}_"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        if not blobs:
            logger.warning(f"No Pexels images found for category: {category}")
            return None
        
        # Pick random image from category
        selected_blob = random.choice(blobs)
        url = make_public_url(f"gcs/{selected_blob.name}")
        
        return {
            "category": category,
            "image": selected_blob.name.split("/")[-1],
            "path": selected_blob.name,
            "url": url
        }
    except Exception as e:
        logger.warning(f"Pexels background selection failed: {e}")
        return None


def get_pexels_categories() -> list:
    """Get available Pexels categories"""
    return PEXELS_CATEGORIES

# ============================================================================
# RENDER DATA
# ============================================================================

async def build_render_data(device_id: str = "familydisplay") -> dict:
    """Build complete data context for rendering - uses device config"""
    
    # Load device config FIRST
    device_config = get_device_config(device_id)
    
    city = device_config["location"]["city"]
    tz_name = device_config["location"]["timezone"]
    icon_theme = device_config["preferences"].get("iconTheme", DEFAULT_ICON_THEME)
    
    logger.info(f"Building render data for {device_id}: {city} ({tz_name})")
    
    # Load layout
    layout_key = f"devices/{device_id}/layouts/current.json"
    
    try:
        layout = gcs_read_json(layout_key)
    except:
        logger.warning(f"Layout not found: {layout_key}, using default")
        layout = {
            "name": "default",
            "meta": {},
            "elements": []
        }
    
    # Get weather data using device city
    weather = await get_weather(city)
    icon_code = weather.get("icon", "01d")
    weather["icon_theme"] = icon_theme
    weather["icon_url"] = resolve_weather_icon_url(icon_theme, icon_code)
    weather["city"] = city

    # Calculate local time using device timezone
    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
    except Exception as e:
        logger.warning(f"Invalid timezone {tz_name}: {e}, using UTC")
        now = datetime.now(timezone.utc)
    
    weather["local_datetime"] = now.isoformat()

    # Get joke
    dad_joke = await get_joke()

    # Get Pexels background
    selected_category = layout.get("meta", {}).get("pexelsCategory")
    pexels_info = None

    if ENABLE_PEXELS and storage_enabled:
        pexels_info = choose_pexels_background(selected_category)

    if pexels_info:
        bg_url = pexels_info["url"]
    else:
        bg_url = make_public_url("gcs/pexels/current/abstract_0.jpg")
    
    if ENABLE_PEXELS:
        categories = get_pexels_categories()
        pexels_info = {
            "category": selected_category or (categories[0] if categories else None),
            "image": pexels_info.get("image") if pexels_info else None,
            "path": pexels_info.get("path") if pexels_info else None,
            "url": bg_url,
            "categories": categories,
        }
    
    date_str = now.strftime("%a, %d %b")
    
    if storage_enabled:
        svg_base = make_public_url("gcs/assets/svgs")
    else:
        svg_base = make_public_url("designer/svgs")
    
    return {
        "layout": layout,
        "weather": weather,
        "dad_joke": dad_joke,
        "date": date_str,
        "bg_url": bg_url,
        "pexels": pexels_info,
        "svg_base": svg_base,
        "device": device_config,
        "timestamp": now.isoformat()
    }


async def render_html_to_png(html_path: str, context: Dict[str, Any]) -> bytes:
    """Render base.html to PNG using Playwright"""
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")
    
    page = await playwright_browser.new_page(
        viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}
    )
    
    raw_json = json.dumps(context)
    encoded_data = quote(raw_json, safe="")
    url = f"file://{os.path.abspath(html_path)}?data={encoded_data}"
    
    logger.info(f"🎨 Rendering: {url[:100]}...")
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=10000)
        await page.wait_for_timeout(1500)
        png_bytes = await page.screenshot(type="png", full_page=True)
        return png_bytes
    finally:
        await page.close()

# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Kin:D Family Display Backend v4",
        "version": "4.0",
        "rendering_enabled": ENABLE_RENDERING,
        "storage_enabled": storage_enabled,
        "features": {
            "device_config": True,
            "australian_cities": True,
            "timezone_support": True,
            "extended_weather": True,
            "tomorrow_forecast": True,
            "pexels_randomization": True,
            "text_shadows": True
        }
    }


# Device Config Routes
@app.get("/v1/devices/{device_id}/config")
def api_get_device_config(device_id: str):
    """Get device configuration"""
    try:
        config = get_device_config(device_id)
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"Failed to get device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/devices/{device_id}/config")
async def api_save_device_config(device_id: str, request: Request):
    """Save device configuration"""
    try:
        config = await request.json()
        save_device_config(device_id, config)
        return {"status": "success", "message": f"Device config saved for {device_id}"}
    except Exception as e:
        logger.error(f"Failed to save device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Layout Routes
@app.get("/v1/devices/{device_id}/layouts/current")
def api_get_layout(device_id: str):
    """Get current layout for device"""
    layout_key = f"devices/{device_id}/layouts/current.json"
    try:
        layout = gcs_read_json(layout_key)
        return JSONResponse(content=layout)
    except FileNotFoundError:
        return JSONResponse(content={"name": "default", "meta": {}, "elements": []})
    except Exception as e:
        logger.error(f"Failed to get layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/devices/{device_id}/layouts/current")
async def api_save_layout(device_id: str, request: Request):
    """Save layout for device"""
    try:
        layout = await request.json()
        layout_key = f"devices/{device_id}/layouts/current.json"
        gcs_write_json(layout_key, layout)
        return {"status": "success", "message": f"Layout saved for {device_id}"}
    except Exception as e:
        logger.error(f"Failed to save layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Render Data Route
@app.get("/v1/render_data")
async def get_render_data(device: str = "familydisplay"):
    """Get complete render data for a device"""
    try:
        data = await build_render_data(device)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Failed to build render data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Frame Route
@app.get("/v1/frame")
async def get_frame(device: str = "familydisplay"):
    """Render and return PNG frame"""
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        
        # Save to GCS
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes, "image/png")
        
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Designer Route
@app.get("/designer/", response_class=HTMLResponse)
async def designer():
    """Serve designer HTML"""
    designer_path = Path("backend/web/designer/overlay_designer_v4_clean.html")
    if not designer_path.exists():
        designer_path = Path("web/designer/overlay_designer_v4_clean.html")
    
    if designer_path.exists():
        return HTMLResponse(content=designer_path.read_text())
    raise HTTPException(status_code=404, detail="Designer not found")


# SVG List Route
@app.get("/api/list-svgs")
async def list_svgs():
    """List available SVG files"""
    if not storage_enabled:
        return {"svgs": []}
    
    try:
        blobs = bucket.list_blobs(prefix="assets/svgs/")
        svgs = []
        for blob in blobs:
            if blob.name.endswith('.svg'):
                filename = blob.name.split('/')[-1]
                svgs.append({
                    "name": filename,
                    "path": f"/gcs/{blob.name}",
                    "url": make_public_url(f"gcs/{blob.name}")
                })
        return {"svgs": svgs}
    except Exception as e:
        logger.error(f"Failed to list SVGs: {e}")
        return {"svgs": []}


# Presets List Route
@app.get("/api/list-presets")
async def list_presets():
    """List available preset layouts"""
    presets_dir = Path("backend/web/presets")
    if not presets_dir.exists():
        presets_dir = Path("web/presets")
    
    if presets_dir.exists():
        presets = []
        for file in presets_dir.glob("*.json"):
            presets.append({
                "name": file.stem,
                "path": f"/presets/{file.name}"
            })
        return {"presets": presets}
    return {"presets": []}


# GCS Asset Proxy
@app.get("/gcs/{path:path}")
async def gcs_proxy(path: str):
    """Proxy GCS assets through HTTP"""
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="GCS not enabled")
    
    try:
        blob = bucket.blob(path)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Asset not found")
        
        data = blob.download_as_bytes()
        
        # Determine content type
        if path.endswith('.svg'):
            content_type = 'image/svg+xml'
        elif path.endswith('.json'):
            content_type = 'application/json'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif path.endswith('.png'):
            content_type = 'image/png'
        else:
            content_type = 'application/octet-stream'
        
        return Response(content=data, media_type=content_type)
        
    except Exception as e:
        logger.error(f"GCS proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Admin Routes
@app.get("/admin/render_now")
async def admin_render_now(token: str, device: str = "familydisplay"):
    """Force immediate render"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        
        # Save to GCS
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes, "image/png")
            
            # Also save dated version
            now = datetime.now(timezone.utc)
            dated_key = f"devices/{device}/renders/{now.strftime('%Y-%m-%d_%H-%M-%S')}.png"
            gcs_write_bytes(dated_key, png_bytes, "image/png")
        
        return {"status": "success", "message": f"Rendered {device}", "size": len(png_bytes)}
    except Exception as e:
        logger.error(f"Admin render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Static file mounts
if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")

if os.path.exists("web/presets"):
    app.mount("/presets", StaticFiles(directory="web/presets", html=True), name="presets")

if os.path.exists("backend/web/designer/svgs"):
    app.mount(
        "/designer/svgs",
        StaticFiles(directory="backend/web/designer/svgs"),
        name="designer-svgs",
    )

if os.path.exists("backend/web/designer/weather-icons"):
    app.mount(
        "/designer/weather-icons",
        StaticFiles(directory="backend/web/designer/weather-icons"),
        name="designer-weather-icons",
    )


# Playwright lifecycle
@app.on_event("startup")
async def startup():
    """Initialize Playwright on startup"""
    global playwright_browser
    
    if ENABLE_RENDERING:
        try:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            playwright_browser = await playwright.chromium.launch()
            logger.info("✓ Playwright browser launched")
        except Exception as e:
            logger.error(f"Failed to launch Playwright: {e}")
            playwright_browser = None


@app.on_event("shutdown")
async def shutdown():
    """Cleanup Playwright on shutdown"""
    global playwright_browser
    
    if playwright_browser:
        await playwright_browser.close()
        logger.info("✓ Playwright browser closed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
