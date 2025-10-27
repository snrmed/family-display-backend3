import os
import datetime
from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

# ---- ENV ----
BUCKET = os.getenv("GCS_BUCKET", "")                # e.g. family-display-packs
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_demo")  # change in prod
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8080")  # Cloud Run URL once deployed

# ---- App ----
app = FastAPI(title="Family Display - HTML Renderer", version="1.0")

# CORS (Designer preview may call this service from a different host)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---- Storage: GCS if configured, else local-only ----
storage_enabled = False
try:
    from google.cloud import storage as gcs_storage  # type: ignore
    if BUCKET:
        _gcs_client = gcs_storage.Client()
        _gcs_bucket = _gcs_client.bucket(BUCKET)
        storage_enabled = True
except Exception:
    storage_enabled = False
    _gcs_client = None
    _gcs_bucket = None

def gcs_exists(key: str) -> bool:
    if not storage_enabled: return False
    b = _gcs_bucket.blob(key)
    return b.exists()

def gcs_read_bytes(key: str) -> bytes:
    b = _gcs_bucket.blob(key)
    return b.download_as_bytes()

def gcs_write_bytes(key: str, data: bytes, content_type: str, cache: str = "public, max-age=60"):
    b = _gcs_bucket.blob(key)
    b.cache_control = cache
    b.upload_from_string(data, content_type=content_type)

# ---- Data API (stub for Stage 1) ----
@app.get("/v1/render_data")
def v1_render_data(device: str, theme: str = "abstract"):
    """Return the dynamic data your HTML uses. Wire real weather/pexels later."""
    today = datetime.date.today().isoformat()
    return JSONResponse({
        "date": today,
        "city": "Darwin, AU",
        "weather": {"min": 27, "max": 34, "desc": "Sunny", "icon": "01d"},
        "dad_joke": "I told my wife she should embrace her mistakes — she gave me a hug.",
        # Point to your cached background if you have it; else a dev placeholder path
        "pexels_bg_url": "/images/preview/abstract_v0.png"
    })

# ---- Serve a local layout (Stage-1 example) ----
@app.get("/web/layouts/{name}.html")
def get_layout_html(name: str):
    here = os.path.dirname(__file__)
    path = os.path.join(here, "web", "layouts", f"{name}.html")
    if not os.path.exists(path):
        raise HTTPException(404, f"Layout {name}.html not found")
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# ---- Render Now: open layout URL in headless Chromium and screenshot #canvas ----
@app.get("/admin/render_now")
def admin_render_now(
    device: str = Query(..., description="Device ID"),
    layout: str = Query("base", description="Layout name (file in web/layouts/)"),
    token: str = Query(..., description="Admin token")
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    layout_url = (
        f"{PUBLIC_BASE_URL}/web/layouts/{layout}.html"
        f"?mode=render&device={device}&backend={PUBLIC_BASE_URL}"
    )
    png = _take_element_screenshot(layout_url, selector="#canvas", width=800, height=480)

    # Save to GCS if configured
    today = datetime.date.today().strftime("%Y-%m-%d")
    latest_key = f"renders/{device}/latest.png"
    dated_key  = f"renders/{device}/{today}/v_0.png"

    if storage_enabled:
        gcs_write_bytes(latest_key, png, "image/png", cache="no-cache")
        gcs_write_bytes(dated_key,  png, "image/png", cache="public, max-age=31536000")

    # Also return the PNG for immediate verification
    return Response(content=png, media_type="image/png")

def _take_element_screenshot(url: str, selector: str, width: int, height: int) -> bytes:
    """Launch headless Chromium, load URL, screenshot specific element."""
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1
        )
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(selector, state="visible", timeout=15_000)
        element = page.query_selector(selector)
        if element is None:
            browser.close()
            raise HTTPException(500, f"Selector not found: {selector}")
        png = element.screenshot(type="png")
        browser.close()
        return png

# ---- Device endpoint: returns latest PNG ----
@app.get("/v1/frame")
def v1_frame(device: str):
    key = f"renders/{device}/latest.png"
    if storage_enabled and gcs_exists(key):
        data = gcs_read_bytes(key)
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-cache"})

    # Local dev fallback: serve a sample if present
    here = os.path.dirname(__file__)
    local_sample = os.path.join(here, "web", "layouts", "sample.png")
    if os.path.exists(local_sample):
        return FileResponse(local_sample, media_type="image/png")
    raise HTTPException(404, "No render available")
