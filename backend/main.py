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

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATIC_SEARCH_BASES = [Path.cwd(), BASE_DIR, PROJECT_ROOT]

LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
]

# ============================================================================
# GOOGLE CLOUD STORAGE
# ============================================================================

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

# ============================================================================
# UTILITIES
# ============================================================================

def make_public_url(path: str) -> str:
    """Generate public URL for assets"""
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/{path}"
    return f"/{path}"


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
    """Read JSON from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return json.loads(blob.download_as_text())


def gcs_read_text(key: str) -> str:
    """Read text file from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return blob.download_as_text()


def gcs_write_json(key: str, data: dict):
    """Write JSON to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    logger.info(f"💾 Saved: {key}")


def gcs_write_bytes(key: str, data: bytes, content_type: str = "image/png"):
    """Write bytes to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"💾 Saved: {key}")


# ============================================================================
# DEVICE CONFIGURATION
# ============================================================================

DEFAULT_DEVICE_CONFIG = {
    "location": {
        "city": "Darwin",
        "timezone": "Australia/Darwin"
    },
    "preferences": {
        "iconTheme": "happy-skies"
    }
}

def get_device_config(device_id: str = "familydisplay") -> dict:
    """Load device configuration"""
    if not storage_enabled:
        return DEFAULT_DEVICE_CONFIG
    
    try:
        config_key = f"devices/{device_id}/config.json"
        config = gcs_read_json(config_key)
        logger.info(f"✅ Loaded config for {device_id}")
        return config
    except:
        logger.info(f"Using default config for {device_id}")
        return DEFAULT_DEVICE_CONFIG


def save_device_config(device_id: str, config: dict):
    """Save device configuration"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    
    config_key = f"devices/{device_id}/config.json"
    gcs_write_json(config_key, config)
    logger.info(f"✅ Saved config for {device_id}")


# ============================================================================
# RENDERING & BROWSER
# ============================================================================

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright
        
        async def init_browser():
            global playwright_browser
            pw = await async_playwright().start()
            playwright_browser = await pw.chromium.launch(
                args=['--no-sandbox', '--disable-dev-shm-usage']
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


# ============================================================================
# CONTENT PROVIDERS
# ============================================================================

def resolve_weather_icon_url(theme: str, code: str) -> str:
    """Resolve weather icon URL"""
    path = f"assets/weather-icons/{theme}/{code}.svg"
    return make_public_url(f"gcs/{path}")


async def get_weather(city: str) -> dict:
    """Get weather data from OpenWeather API"""
    api_key = os.getenv("OPENWEATHER_KEY")
    
    if ENABLE_OPENWEATHER and api_key:
        try:
            async with httpx.AsyncClient() as client:
                # Get current weather
                current_url = f"https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": city,
                    "appid": api_key,
                    "units": "metric"
                }
                r = await client.get(current_url, params=params, timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    
                    # Get forecast for tomorrow
                    lat = data["coord"]["lat"]
                    lon = data["coord"]["lon"]
                    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
                    forecast_params = {
                        "lat": lat,
                        "lon": lon,
                        "appid": api_key,
                        "units": "metric"
                    }
                    forecast_r = await client.get(forecast_url, params=forecast_params, timeout=10)
                    
                    tomorrow_data = None
                    if forecast_r.status_code == 200:
                        forecast = forecast_r.json()
                        if forecast.get("list"):
                            # Get tomorrow's forecast (24 hours ahead)
                            tomorrow_entry = forecast["list"][8] if len(forecast["list"]) > 8 else forecast["list"][-1]
                            tomorrow_data = {
                                "temp_min": round(tomorrow_entry["main"]["temp_min"]),
                                "temp_max": round(tomorrow_entry["main"]["temp_max"]),
                                "desc": tomorrow_entry["weather"][0]["description"].title()
                            }
                    
                    return {
                        "temp": round(data["main"]["temp"]),
                        "humidity": data["main"]["humidity"],
                        "rain": data.get("rain", {}).get("1h", 0),
                        "wind": round(data["wind"]["speed"] * 3.6),
                        "icon": data["weather"][0]["icon"],
                        "desc": data["weather"][0]["description"].title(),
                        "desc_extended": data["weather"][0]["description"],
                        "temp_min": round(data["main"]["temp_min"]),
                        "temp_max": round(data["main"]["temp_max"]),
                        "timezone_offset": data.get("timezone", 0),
                        "tomorrow": tomorrow_data
                    }
        except Exception as e:
            logger.warning(f"OpenWeather API failed: {e}")
    
    return {
        "temp": 32,
        "humidity": 65,
        "rain": 0,
        "wind": 15,
        "icon": "01d",
        "desc": "Sunny",
        "desc_extended": "Sunny with clear skies",
        "temp_min": 30,
        "temp_max": 36,
        "timezone_offset": 0,
        "tomorrow": {
            "temp_min": 29,
            "temp_max": 35,
            "desc": "Partly Cloudy"
        }
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


def get_pexels_categories() -> list:
    """Get available Pexels categories from GCS bucket"""
    if not storage_enabled:
        return ["abstract", "geometric", "minimal"]
    
    try:
        # List all folders in pexels/current/
        blobs = bucket.list_blobs(prefix="pexels/current/", delimiter="/")
        
        # Extract unique category names from file prefixes
        categories = set()
        for blob in blobs:
            # File format: pexels/current/category_number.jpg
            filename = blob.name.split("/")[-1]
            if "_" in filename:
                category = filename.split("_")[0]
                categories.add(category)
        
        sorted_categories = sorted(list(categories))
        logger.info(f"📂 Found {len(sorted_categories)} Pexels categories: {sorted_categories}")
        return sorted_categories if sorted_categories else ["abstract", "geometric", "minimal"]
    except Exception as e:
        logger.warning(f"Could not list Pexels categories: {e}")
        return ["abstract", "geometric", "minimal"]


def choose_pexels_background(selected_category: str = None) -> dict:
    """Choose a random Pexels background from the selected category"""
    if not storage_enabled:
        return None
    
    try:
        prefix = "pexels/current/"
        
        # If a specific category is selected, filter by it
        if selected_category:
            blobs = list(bucket.list_blobs(prefix=prefix))
            category_blobs = [
                blob for blob in blobs 
                if blob.name.split("/")[-1].startswith(f"{selected_category}_")
            ]
        else:
            category_blobs = list(bucket.list_blobs(prefix=prefix))
        
        if category_blobs:
            chosen = random.choice(category_blobs)
            filename = chosen.name.split("/")[-1]
            category = filename.split("_")[0] if "_" in filename else "unknown"
            
            return {
                "url": make_public_url(f"gcs/{chosen.name}"),
                "category": category,
                "filename": filename
            }
    except Exception as e:
        logger.warning(f"Could not choose Pexels background: {e}")
    
    return None


async def build_render_data(device: str = "familydisplay") -> dict:
    """Build complete render data for a device"""
    try:
        device_config = get_device_config(device)
        city = device_config.get("location", {}).get("city", "Darwin")
        tz_name = device_config.get("location", {}).get("timezone", "Australia/Darwin")
        icon_theme = device_config.get("preferences", {}).get("iconTheme", DEFAULT_ICON_THEME)
        
        logger.info(f"Building render data for {device}: {city} ({tz_name})")
        
        # Load layout
        layout_key = f"devices/{device}/layouts/current.json"
        try:
            layout = gcs_read_json(layout_key)
        except:
            layout = {"name": "Default", "elements": []}
        
        # Get weather
        weather = await get_weather(f"{city},AU")
        
        # Add weather icon URL
        icon_code = weather.get("icon", "01d")
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
        
        # Get all available categories for frontend
        categories = get_pexels_categories() if ENABLE_PEXELS else []
        
        if ENABLE_PEXELS:
            pexels_info = pexels_info or {}
            pexels_info["categories"] = categories
        
        date_str = now.strftime("%a, %d %b")
        
        if storage_enabled:
            svg_base = make_public_url("gcs/assets/svgs")
        else:
            svg_base = make_public_url("designer/svgs")
        
        # Font base for loading fonts in base.html
        font_base = make_public_url("fonts")
        
        return {
            "layout": layout,
            "weather": weather,
            "dad_joke": dad_joke,
            "date": date_str,
            "bg_url": bg_url,
            "pexels": pexels_info,
            "svg_base": svg_base,
            "font_base": font_base,
            "device": device_config,
            "timestamp": now.isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to build render data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            "pexels_randomization": True,
            "dynamic_categories": True
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
        return {"status": "saved", "device_id": device_id}
    except Exception as e:
        logger.error(f"Failed to save device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Layout Routes
@app.get("/v1/devices/{device_id}/layouts/current")
def api_get_layout(device_id: str):
    """Get current layout for device"""
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
    """Save layout for device"""
    try:
        layout = await request.json()
        layout_key = f"devices/{device_id}/layouts/current.json"
        gcs_write_json(layout_key, layout)
        return {"status": "saved", "device_id": device_id}
    except Exception as e:
        logger.error(f"Failed to save layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Render Data Route
@app.get("/v1/render_data")
async def api_render_data(device: str = "familydisplay"):
    """Get complete render data"""
    try:
        data = await build_render_data(device)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Failed to build render data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Frame Render Route
@app.get("/v1/frame")
async def api_frame(device: str = "familydisplay"):
    """Render PNG frame"""
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        data = await build_render_data(device)
        
        render_path = Path(RENDER_PATH)
        if not render_path.exists():
            render_path = Path("web/layouts/base.html")
        
        png_bytes = await render_html_to_png(str(render_path), data)
        
        # Save to GCS
        if storage_enabled:
            render_key = f"devices/{device}/renders/latest.png"
            gcs_write_bytes(render_key, png_bytes)
        
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to render frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Designer Route
@app.get("/designer/", response_class=HTMLResponse)
async def designer():
    """Serve designer HTML from GCS"""
    if not storage_enabled:
        raise HTTPException(status_code=503, detail="Storage not configured")
    
    try:
        designer_key = "web/designer/overlay_designer_v4_clean.html"
        html_content = gcs_read_text(designer_key)
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Designer not found in bucket")
    except Exception as e:
        logger.error(f"Failed to load designer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    presets_dir = resolve_static_dir("web/presets", "backend/web/presets")

    if presets_dir and presets_dir.exists():
        presets = []
        for file in presets_dir.glob("*.json"):
            presets.append(file.stem)
        return {"presets": presets}
    return {"presets": []}


# Pexels Categories Route
@app.get("/api/list-pexels-categories")
async def list_pexels_categories():
    """List available Pexels categories"""
    try:
        categories = get_pexels_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Failed to list Pexels categories: {e}")
        return {"categories": ["abstract", "geometric", "minimal"]}


# Static Files - FIXED for container working directory
try:
    presets_dir = resolve_static_dir("web/presets", "backend/web/presets")
    if presets_dir and presets_dir.is_dir():
        app.mount("/presets", StaticFiles(directory=str(presets_dir)), name="presets")
        logger.info(f"✓ Mounted /presets from {presets_dir}")
    else:
        logger.info("/presets directory not found; skipping mount")
except Exception as e:
    logger.warning(f"Could not mount /presets: {e}")

try:
    fonts_dir = resolve_static_dir("web/fonts", "backend/web/fonts")
    if fonts_dir and fonts_dir.is_dir():
        app.mount("/fonts", StaticFiles(directory=str(fonts_dir)), name="fonts")
        logger.info(f"✓ Mounted /fonts from {fonts_dir}")
    else:
        logger.info("/fonts directory not found; skipping mount")
except Exception as e:
    logger.warning(f"Could not mount /fonts: {e}")


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
async def admin_render_now(token: str = None, device: str = "familydisplay"):
    """Force render now"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        await api_frame(device)
        return {"status": "rendered", "device": device}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
