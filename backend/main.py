import os
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.cloud import storage
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kin:D Family Display Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"
ENABLE_EMAIL_USERS = os.getenv("ENABLE_EMAIL_USERS", "false").lower() == "true"
CITY_MODE = os.getenv("CITY_MODE", "default")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin")
DEFAULT_ICON_THEME = os.getenv("WEATHER_ICON_PACK", "happy-skies")
RENDER_WIDTH = int(os.getenv("RENDER_WIDTH", "800"))
RENDER_HEIGHT = int(os.getenv("RENDER_HEIGHT", "480"))
RENDER_PATH = os.getenv("RENDER_PATH", "backend/web/layouts/base.html")

storage_enabled = False
gcs_bucket = None
playwright_browser = None

try:
    storage_client = storage.Client()
    gcs_bucket = storage_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"✓ GCS enabled: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"⚠️  GCS disabled: {e}")

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright
        playwright = None
        playwright_browser = None
        
        @app.on_event("startup")
        async def startup():
            global playwright, playwright_browser
            playwright = await async_playwright().start()
            playwright_browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            logger.info("✓ Playwright browser started")
        
        @app.on_event("shutdown")
        async def shutdown():
            if playwright_browser:
                await playwright_browser.close()
            if playwright:
                await playwright.stop()
            logger.info("✓ Playwright stopped")
    except ImportError:
        logger.warning("⚠️  Playwright not available")
        ENABLE_RENDERING = False

LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I'm reading a book about anti-gravity. It's impossible to put down!",
    "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them.",
    "Why do we tell actors to 'break a leg?' Because every play has a cast.",
    "Helvetica and Times New Roman walk into a bar. 'Get out of here!' shouts the bartender. 'We don't serve your type.'",
    "Yesterday I saw a guy spill all his Scrabble letters on the road. I asked him, 'What's the word on the street?'",
    "What do you call a factory that makes okay products? A satisfactory.",
    "I used to hate facial hair, but then it grew on me.",
]

def make_public_url(path: str) -> str:
    """Build full public URL for assets"""
    if path.startswith("http"):
        return path
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else f"http://localhost:{PORT}"
    return f"{base}/{path.lstrip('/')}"

def gcs_read_json(key: str) -> dict:
    """Read JSON from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = gcs_bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return json.loads(blob.download_as_text(encoding='utf-8'))

def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Write bytes to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = gcs_bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"✓ Wrote {len(data)} bytes to {key}")

async def get_weather(city: str) -> dict:
    """Get weather data"""
    if ENABLE_OPENWEATHER:
        api_key = os.getenv("OPENWEATHER_KEY")
        if api_key:
            try:
                async with httpx.AsyncClient() as client:
                    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
                    r = await client.get(url, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        return {
                            "temp": round(data["main"]["temp"]),
                            "feels_like": round(data["main"]["feels_like"]),
                            "humidity": data["main"]["humidity"],
                            "rain": data.get("rain", {}).get("1h", 0),
                            "wind": round(data["wind"]["speed"]),
                            "icon": data["weather"][0]["icon"],
                            "desc": data["weather"][0]["description"].title()
                        }
            except Exception as e:
                logger.warning(f"OpenWeather failed: {e}")
    
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

async def build_render_data(device: str = "familydisplay") -> dict:
    """Build complete data context for rendering"""
    
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
    
    icon_theme = layout.get("meta", {}).get("iconTheme", DEFAULT_ICON_THEME)
    
    city = DEFAULT_CITY
    if CITY_MODE == "fetch":
        city = layout.get("meta", {}).get("city", DEFAULT_CITY)
    
    weather = await get_weather(city)
    icon_code = weather.get("icon", "01d")
    weather["icon_url"] = make_public_url(f"gcs/assets/weather-icons/{icon_theme}/{icon_code}.svg")
    weather["city"] = city
    
    dad_joke = await get_joke()
    
    bg_url = make_public_url("gcs/pexels/current/abstract_0.jpg")
    
    now = datetime.now()
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
        "svg_base": svg_base,
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
        png_bytes = await page.screenshot(type="png", full_page=False)
        await page.close()
        logger.info(f"✅ Rendered {len(png_bytes)} bytes")
        return png_bytes
    except Exception as e:
        logger.error(f"Render failed: {e}")
        await page.close()
        raise

@app.get("/")
def root():
    return {
        "service": "Kin:D Family Display Backend",
        "status": "running",
        "features": {
            "rendering": ENABLE_RENDERING,
            "pexels": ENABLE_PEXELS,
            "openweather": ENABLE_OPENWEATHER,
            "jokes": ENABLE_JOKES_API,
            "gcs": storage_enabled
        }
    }

@app.get("/v1/render_data")
async def get_render_data(device: str = "familydisplay"):
    """Get render context data"""
    try:
        data = await build_render_data(device)
        return data
    except Exception as e:
        logger.error(f"Render data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/frame")
async def get_frame(device: str = "familydisplay"):
    """Render and return PNG frame"""
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Frame generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/render_now")
async def admin_render_now(device: str = "familydisplay", token: str = None):
    """Force render and save to GCS"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        
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

@app.get("/gcs/{path:path}")
def get_gcs_asset(path: str):
    """Serve assets from GCS bucket"""
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")
    
    blob = gcs_bucket.blob(path)
    if not blob.exists():
        logger.warning(f"❌ Asset not found: {path}")
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    
    data = blob.download_as_bytes()
    
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

def _discover_local_svgs() -> list[str]:
    search_dirs = [
        Path("backend/web/designer/svgs"),
        Path("web/designer/svgs"),
        Path("web/svgs"),
    ]
    for directory in search_dirs:
        if directory.exists():
            svgs = sorted([p.name for p in directory.glob("*.svg")])
            if svgs:
                return svgs
    return []


@app.get("/api/list-svgs")
def list_svgs():
    """List all SVG files available to the designer"""
    svgs: list[str] = []
    base_url = None

    if storage_enabled:
        try:
            blobs = gcs_bucket.list_blobs(prefix="assets/svgs/")
            svgs = [
                blob.name.split("/")[-1]
                for blob in blobs
                if blob.name.endswith(".svg")
            ]
            if svgs:
                base_url = "/gcs/assets/svgs"
                logger.info(f"Found {len(svgs)} SVGs in bucket")
        except Exception as e:
            logger.error(f"Failed to list SVGs from GCS: {e}")

    if not svgs:
        svgs = _discover_local_svgs()
        if svgs:
            base_url = "/designer/svgs"
            logger.info(f"Using {len(svgs)} local SVGs")

    return {"svgs": svgs, "base_url": base_url}


def _discover_local_weather_themes() -> list[str]:
    base_dir = Path("backend/web/designer/weather-icons")
    if not base_dir.exists():
        return []
    return sorted([p.name for p in base_dir.iterdir() if p.is_dir()])


@app.get("/api/list-weather-themes")
def list_weather_themes():
    """List available weather icon themes"""
    themes: list[str] = []
    icon_base = None

    if storage_enabled:
        try:
            blobs = gcs_bucket.list_blobs(prefix="assets/weather-icons/", delimiter="/")
            prefixes: list[str] = []
            for page in blobs.pages:
                prefixes.extend(page.prefixes)
            themes = [
                prefix.rstrip("/").split("/")[-1]
                for prefix in prefixes
            ]
            if themes:
                icon_base = "/gcs/assets/weather-icons"
        except Exception as e:
            logger.error(f"Failed to list weather themes from GCS: {e}")

    if not themes:
        themes = _discover_local_weather_themes()
        if themes:
            icon_base = "/designer/weather-icons"

    if not themes:
        themes = ["happy-skies", "soft-skies", "sunny-day", "blue-sky-pro"]

    if icon_base is None:
        icon_base = "/gcs/assets/weather-icons" if storage_enabled else "/designer/weather-icons"

    return {"themes": themes, "icon_base": icon_base}

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
        gcs_write_bytes(key, json_str.encode('utf-8'), "application/json")
        return {"status": "saved", "path": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/designer/", response_class=HTMLResponse)
def get_designer():
    """Serve designer HTML"""
    paths = [
        "backend/web/designer/overlay_designer_v3_full.html",
        "web/designer/overlay_designer_v3_full.html",
        "overlay_designer_v3_full.html"
    ]
    
    for path in paths:
        if os.path.exists(path):
            logger.info(f"Serving designer from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    
    logger.error("Designer HTML not found in any path")
    return "<h1>Designer not found</h1><p>Checked paths: " + ", ".join(paths) + "</p>"

@app.get("/test/", response_class=HTMLResponse)
def get_test():
    """Serve test page"""
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Test Designer</title>
<style>
body{margin:0;padding:20px;font-family:sans-serif;background:#1a1a1a;color:#fff}
#canvas{position:relative;width:800px;height:480px;background:linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);border:2px solid #333;margin:20px auto}
.el{position:absolute;cursor:move;border:2px solid red}
.el.text{background:rgba(255,255,255,0.9);padding:10px;font-size:20px;color:#000}
button{padding:10px 20px;margin:5px;background:#2d8cf0;color:white;border:none;cursor:pointer;border-radius:4px}
button:hover{background:#1a6ec0}
#status{margin:10px;padding:10px;background:#333;border-radius:4px}
</style></head><body>
<h1>Designer Test</h1>
<div id="status">Ready</div>
<button onclick="testAddText()">Add Text</button>
<button onclick="testAddBox()">Add Box</button>
<button onclick="testFetchData()">Fetch Data</button>
<button onclick="testListSVGs()">List SVGs</button>
<div id="canvas"></div>
<script>
const canvas = document.getElementById('canvas');
const status = document.getElementById('status');
function log(msg) { status.textContent = msg; console.log(msg); }
function testAddText() {
  const el = document.createElement('div');
  el.className = 'el text';
  el.style.left = '100px';
  el.style.top = '100px';
  el.style.width = '200px';
  el.style.height = '40px';
  el.textContent = 'Test Text';
  canvas.appendChild(el);
  log('Added text element - count: ' + canvas.children.length);
}
function testAddBox() {
  const el = document.createElement('div');
  el.className = 'el box';
  el.style.left = '200px';
  el.style.top = '200px';
  el.style.width = '150px';
  el.style.height = '100px';
  el.style.background = 'rgba(255,255,255,0.2)';
  el.style.border = '2px solid blue';
  canvas.appendChild(el);
  log('Added box element - count: ' + canvas.children.length);
}
async function testFetchData() {
  try {
    const response = await fetch('/v1/render_data?device=familydisplay');
    const data = await response.json();
    log('Fetch OK: temp=' + data.weather.temp + ', joke=' + data.dad_joke.substring(0,30));
  } catch (error) {
    log('Fetch ERROR: ' + error.message);
  }
}
async function testListSVGs() {
  try {
    const response = await fetch('/api/list-svgs');
    const data = await response.json();
    log('SVGs: ' + data.svgs.length + ' found - ' + data.svgs.slice(0,3).join(', '));
  } catch (error) {
    log('SVG List ERROR: ' + error.message);
  }
}
log('Test page loaded - canvas ready');
</script></body></html>"""

if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")

if os.path.exists("web/presets"):
    app.mount("/presets", StaticFiles(directory="web/presets", html=True), name="presets")

if os.path.exists("web/svgs"):
    app.mount("/svgs", StaticFiles(directory="web/svgs"), name="svgs")

if os.path.exists("backend/web/designer/presets"):
    app.mount(
        "/designer/presets",
        StaticFiles(directory="backend/web/designer/presets", html=True),
        name="designer-presets",
    )

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
