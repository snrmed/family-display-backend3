"""
Kin:D Family Display Backend
Fixed version with proper URL resolution for Playwright rendering
"""
import os
import re
import json
import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import quote
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ================================================================
# Environment Variables
# ================================================================
PORT = int(os.getenv("PORT", 8080))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")

# Feature flags
ENABLE_EMAIL_USERS = os.getenv("ENABLE_EMAIL_USERS", "false").lower() == "true"
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"

# City mode
CITY_MODE = os.getenv("CITY_MODE", "default")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin")

# Rendering
RENDER_PATH = os.getenv("RENDER_PATH", "backend/web/layouts/base.html")
RENDER_WIDTH = int(os.getenv("RENDER_WIDTH", "800"))
RENDER_HEIGHT = int(os.getenv("RENDER_HEIGHT", "480"))

# CRITICAL FIX: Public base URL for absolute paths
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Icon theme
DEFAULT_ICON_THEME = os.getenv("WEATHER_ICON_PACK", "happy-skies")

# ================================================================
# Logging
# ================================================================
logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL == "debug" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ================================================================
# Google Cloud Storage
# ================================================================
storage_enabled = False
gcs_bucket = None

try:
    from google.cloud import storage
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"✅ GCS enabled: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"⚠️  GCS disabled: {e}")

# ================================================================
# Helper Functions
# ================================================================

def make_public_url(path: str) -> str:
    """Convert GCS path to full public URL"""
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/{path.lstrip('/')}"
    return f"/{path.lstrip('/')}"

def gcs_read_json(key: str) -> dict:
    """Read JSON from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not configured")
    blob = gcs_bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Not found: {key}")
    data = blob.download_as_bytes()
    return json.loads(data.decode('utf-8'))

def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Write bytes to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not configured")
    blob = gcs_bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"✅ Uploaded: {key}")

# ================================================================
# Playwright Setup
# ================================================================
from playwright.async_api import async_playwright

playwright_app = None
playwright_browser = None

async def init_playwright():
    global playwright_app, playwright_browser
    if ENABLE_RENDERING and playwright_browser is None:
        try:
            playwright_app = await async_playwright().start()
            playwright_browser = await playwright_app.chromium.launch(
                args=["--disable-dev-shm-usage", "--no-sandbox"]
            )
            logger.info("✅ Playwright initialized")
        except Exception as e:
            logger.error(f"❌ Playwright failed: {e}")

async def close_playwright():
    global playwright_app, playwright_browser
    if playwright_browser:
        await playwright_browser.close()
    if playwright_app:
        await playwright_app.stop()

# ================================================================
# FastAPI App
# ================================================================
app = FastAPI(title="Kin:D Family Display Backend", version="2.0.0-fixed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_playwright()

@app.on_event("shutdown")
async def shutdown():
    await close_playwright()

# ================================================================
# Mock Data Providers (simplified for demo)
# ================================================================

LOCAL_JOKES = [
    "Why don't skeletons fight each other? They don't have the guts.",
    "I told my wife she should embrace her mistakes — she gave me a hug.",
    "What do you call a bear with no teeth? A gummy bear.",
]

async def get_weather(city: str) -> dict:
    """Mock weather data"""
    return {
        "temp": 33,
        "feels_like": 33,
        "humidity": 45,
        "rain": 0,
        "wind": 5,
        "icon": "01d",
        "desc": "Sunny"
    }

async def get_joke() -> str:
    """Mock joke"""
    return random.choice(LOCAL_JOKES)

# ================================================================
# Render Data Assembly - FIXED VERSION
# ================================================================

async def build_render_data(device: str = "familydisplay") -> dict:
    """
    Build complete data context for rendering
    CRITICAL FIX: Include svg_base with full PUBLIC_BASE_URL
    """
    
    # 1) Load layout
    if ENABLE_EMAIL_USERS:
        layout_key = f"users/default/devices/{device}/layouts/current.json"
    else:
        layout_key = f"layouts/{device}.json"
    
    try:
        layout = gcs_read_json(layout_key)
    except:
        logger.warning(f"Layout not found: {layout_key}, using default")
        layout = {
            "name": "default",
            "meta": {},
            "elements": []
        }
    
    # 2) Icon theme from layout meta or default
    icon_theme = layout.get("meta", {}).get("iconTheme", DEFAULT_ICON_THEME)
    
    # 3) Get city
    city = DEFAULT_CITY
    if CITY_MODE == "fetch":
        city = layout.get("meta", {}).get("city", DEFAULT_CITY)
    
    # 4) Weather data with FULL URLs
    weather = await get_weather(city)
    icon_code = weather.get("icon", "01d")
    weather["icon_url"] = make_public_url(f"gcs/assets/weather-icons/{icon_theme}/{icon_code}.svg")
    weather["city"] = city
    
    # 5) Other data
    dad_joke = await get_joke()
    
    # 6) Background - mock for now
    bg_url = make_public_url("gcs/pexels/current/abstract_0.jpg")
    
    # 7) Date
    now = datetime.now()
    date_str = now.strftime("%a, %d %b")
    
    # ================================================================
    # CRITICAL FIX: svg_base must be FULL URL
    # ================================================================
    svg_base = make_public_url("gcs/assets/svgs")
    
    return {
        "layout": layout,
        "weather": weather,
        "dad_joke": dad_joke,
        "date": date_str,
        "bg_url": bg_url,
        "svg_base": svg_base,  # ✅ FULL URL for Playwright
        "timestamp": now.isoformat()
    }

# ================================================================
# HTML to PNG Rendering - FIXED VERSION
# ================================================================

async def render_html_to_png(html_path: str, context: Dict[str, Any]) -> bytes:
    """
    Render base.html to PNG using Playwright
    FIXED: Properly encode data and pass base URL
    """
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")
    
    page = await playwright_browser.new_page(
        viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}
    )
    
    # 1) Serialize context to JSON
    raw_json = json.dumps(context)
    
    # 2) URL-encode the data
    encoded_data = quote(raw_json, safe="")
    
    # 3) Build file:// URL with data parameter
    # CRITICAL: base.html will use data.svg_base from JSON, not query param
    url = f"file://{os.path.abspath(html_path)}?data={encoded_data}"
    
    logger.info(f"🎨 Rendering: {url[:100]}...")
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=10000)
        await page.wait_for_timeout(1500)  # Let JS render
        png_bytes = await page.screenshot(type="png", full_page=False)
        await page.close()
        logger.info(f"✅ Rendered {len(png_bytes)} bytes")
        return png_bytes
    except Exception as e:
        logger.error(f"❌ Render failed: {e}")
        await page.close()
        raise

# ================================================================
# API Routes
# ================================================================

@app.get("/")
def root():
    return {
        "service": "Kin:D Family Display Backend",
        "version": "2.0.0-fixed",
        "storage": "enabled" if storage_enabled else "disabled",
        "rendering": "enabled" if ENABLE_RENDERING else "disabled",
        "public_base_url": PUBLIC_BASE_URL or "not_set"
    }

@app.get("/v1/render_data")
async def get_render_data(device: str = "familydisplay"):
    """Get render data JSON"""
    data = await build_render_data(device)
    return JSONResponse(content=data)

@app.get("/v1/frame")
async def render_frame(device: str = "familydisplay"):
    """Render PNG frame"""
    try:
        data = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, data)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Frame render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/render_now")
async def admin_render_now(token: str, device: str = "familydisplay"):
    """Admin: Force render and save to GCS"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    try:
        data = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, data)
        
        # Save to GCS
        if ENABLE_EMAIL_USERS:
            render_key = f"users/default/devices/{device}/renders/latest.png"
        else:
            render_key = f"renders/{device}/latest.png"
        
        gcs_write_bytes(render_key, png_bytes, "image/png")
        
        return {
            "status": "rendered",
            "device": device,
            "size": len(png_bytes),
            "path": render_key
        }
    except Exception as e:
        logger.error(f"Admin render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# GCS Asset Proxy
# ================================================================

@app.get("/gcs/{path:path}")
def get_gcs_asset(path: str):
    """
    Serve assets from GCS bucket
    Examples:
      /gcs/assets/svgs/lemon.svg
      /gcs/assets/weather-icons/happy-skies/01d.svg
      /gcs/pexels/current/abstract_0.jpg
    """
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")
    
    blob = gcs_bucket.blob(path)
    if not blob.exists():
        logger.warning(f"❌ Asset not found: {path}")
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    
    data = blob.download_as_bytes()
    
    # Determine content type
    if path.endswith(".svg"):
        ctype = "image/svg+xml"
    elif path.endswith(".png"):
        ctype = "image/png"
    elif path.endswith(".jpg") or path.endswith(".jpeg"):
        ctype = "image/jpeg"
    elif path.endswith(".json"):
        ctype = "application/json"
    else:
        ctype = "application/octet-stream"
    
    return Response(
        content=data,
        media_type=ctype,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )

# ================================================================
# Layout Management
# ================================================================

@app.get("/layouts/{device}")
def get_layout(device: str, x_admin_token: str = Header(None)):
    """Get layout JSON"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    if ENABLE_EMAIL_USERS:
        key = f"users/default/devices/{device}/layouts/current.json"
    else:
        key = f"layouts/{device}.json"
    
    try:
        return gcs_read_json(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Layout not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/layouts/{device}")
def save_layout(device: str, layout: dict, x_admin_token: str = Header(None)):
    """Save layout JSON"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    if ENABLE_EMAIL_USERS:
        key = f"users/default/devices/{device}/layouts/current.json"
    else:
        key = f"layouts/{device}.json"
    
    try:
        json_str = json.dumps(layout, indent=2)
        gcs_write_bytes(key, json_str.encode(), "application/json")
        return {"status": "saved", "path": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# Designer
# ================================================================

@app.get("/designer/", response_class=HTMLResponse)
def get_designer():
    """Serve designer HTML"""
    path = "web/designer/overlay_designer_v3_full.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Designer not found</h1>"

# ================================================================
# Run
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
