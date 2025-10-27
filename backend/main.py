import os
import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

# ── Service imports ──────────────────────────────────────────────────────
from services.weather import get_weather
from services.pexels import prefetch_weekly_set, pick_random_key

# ── ENVIRONMENT ─────────────────────────────────────────────────────────
BUCKET = os.getenv("GCS_BUCKET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_demo")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8080")
DEFAULT_DEVICE_ID = os.getenv("DEFAULT_DEVICE_ID", "familydisplay")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin, AU")
DEFAULT_UNITS = os.getenv("DEFAULT_UNITS", "metric")
TIMEZONE = os.getenv("TIMEZONE", "Australia/Adelaide")

# ── INIT FASTAPI APP ────────────────────────────────────────────────────
app = FastAPI(title="Kin:D / Family Display Backend", version="2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GOOGLE CLOUD STORAGE ────────────────────────────────────────────────
storage_enabled = False
try:
    from google.cloud import storage as gcs_storage
    if BUCKET:
        _gcs_client = gcs_storage.Client()
        _gcs_bucket = _gcs_client.bucket(BUCKET)
        storage_enabled = True
except Exception:
    storage_enabled = False
    _gcs_client = None
    _gcs_bucket = None


def gcs_exists(key: str) -> bool:
    if not storage_enabled:
        return False
    return _gcs_bucket.blob(key).exists()


def gcs_read_bytes(key: str) -> bytes:
    return _gcs_bucket.blob(key).download_as_bytes()


def gcs_write_bytes(key: str, data: bytes, content_type: str, cache: str = "public, max-age=60"):
    b = _gcs_bucket.blob(key)
    b.cache_control = cache
    b.upload_from_string(data, content_type=content_type)


def cache_read_bytes(key: str) -> Optional[bytes]:
    try:
        if storage_enabled and gcs_exists(key):
            return gcs_read_bytes(key)
    except Exception:
        pass
    return None


def cache_write_bytes(key: str, data: bytes, content_type: str, cache: str):
    if storage_enabled:
        gcs_write_bytes(key, data, content_type, cache)


# ── STATIC ASSET PROXY ──────────────────────────────────────────────────
@app.get("/assets/{path:path}")
def assets_proxy(path: str):
    key = path
    if not storage_enabled or not gcs_exists(key):
        raise HTTPException(404, "Asset not found")
    data = gcs_read_bytes(key)
    ct = "image/png" if key.endswith(".png") else (
        "image/jpeg" if key.endswith(".jpg") or key.endswith(".jpeg") else "application/octet-stream"
    )
    return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})


# ── /v1/render_data  →  weather + joke + pexels bg ───────────────────────
@app.get("/v1/render_data")
def v1_render_data(device: Optional[str] = Query(None), theme: Optional[str] = Query(None)):
    device = device or DEFAULT_DEVICE_ID
    theme = theme or os.getenv("THEME_DEFAULT", "abstract")
    tz = ZoneInfo(TIMEZONE)
    today = dt.datetime.now(tz).date()

    # WEATHER
    ow_key = os.getenv("OPENWEATHER_API_KEY", "")
    weather = {"min": 27, "max": 34, "desc": "Sunny", "icon": "01d", "provider": "stub"}
    if ow_key:
        try:
            weather = get_weather(
                DEFAULT_CITY,
                DEFAULT_UNITS,
                ow_key,
                cache_read_bytes,
                lambda k, d, ct, cache: cache_write_bytes(k, d, ct, cache),
            )
        except Exception:
            pass

    # BACKGROUND (dual folder randomization)
    enable_pexels = os.getenv("ENABLE_PEXELS", "false").lower() == "true"
    per_theme = int(os.getenv("PER_THEME_COUNT", "8") or "8")
    bg_key = None
    if enable_pexels:
        candidate = pick_random_key(theme, per_theme, rand_ratio=0.1)
        if storage_enabled and gcs_exists(candidate):
            bg_key = candidate
    if not bg_key:
        bg_key = "images/preview/abstract_v0.png"

    # DAD JOKE
    jokes = [
        "I told my wife she should embrace her mistakes — she gave me a hug.",
        "I'm reading a book on anti-gravity. It's impossible to put down.",
        "Why don’t scientists trust atoms? Because they make up everything!",
        "Parallel lines have so much in common. It’s a shame they’ll never meet.",
    ]
    day_index = (int(today.strftime("%j")) + hash(device)) % len(jokes)
    dad_joke = jokes[day_index]

    return JSONResponse(
        {
            "date": today.isoformat(),
            "city": DEFAULT_CITY,
            "timezone": TIMEZONE,
            "weather": weather,
            "dad_joke": dad_joke,
            "pexels_bg_url": f"/assets/{bg_key}",
            "theme": theme,
            "units": DEFAULT_UNITS,
            "device": device,
        }
    )


# ── HTML Layout Preview ─────────────────────────────────────────────────
@app.get("/web/layouts/{name}.html")
def get_layout_html(name: str):
    here = os.path.dirname(__file__)
    path = os.path.join(here, "web", "layouts", f"{name}.html")
    if not os.path.exists(path):
        raise HTTPException(404, f"Layout {name}.html not found")
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ── Screenshot renderer ─────────────────────────────────────────────────
@app.get("/admin/render_now")
def admin_render_now(
    device: Optional[str] = Query(None),
    layout: str = Query("base"),
    token: str = Query(...),
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    device = device or DEFAULT_DEVICE_ID
    layout_url = (
        f"{PUBLIC_BASE_URL}/web/layouts/{layout}.html?mode=render&device={device}&backend={PUBLIC_BASE_URL}"
    )
    png = _take_element_screenshot(layout_url, selector="#canvas", width=800, height=480)

    today = dt.date.today().strftime("%Y-%m-%d")
    latest_key = f"renders/{device}/latest.png"
    dated_key = f"renders/{device}/{today}/v_0.png"

    if storage_enabled:
        gcs_write_bytes(latest_key, png, "image/png", cache="no-cache")
        gcs_write_bytes(dated_key, png, "image/png", cache="public, max-age=31536000")

    return Response(content=png, media_type="image/png")


def _take_element_screenshot(url: str, selector: str, width: int, height: int) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(selector, state="visible", timeout=15_000)
        element = page.query_selector(selector)
        if element is None:
            browser.close()
            raise HTTPException(500, f"Selector not found: {selector}")
        png = element.screenshot(type="png")
        browser.close()
        return png


# ── /v1/frame  → serve latest PNG for device ────────────────────────────
@app.get("/v1/frame")
def v1_frame(device: Optional[str] = Query(None)):
    device = device or DEFAULT_DEVICE_ID
    key = f"renders/{device}/latest.png"
    if storage_enabled and gcs_exists(key):
        data = gcs_read_bytes(key)
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-cache"})
    here = os.path.dirname(__file__)
    local_sample = os.path.join(here, "web", "layouts", "sample.png")
    if os.path.exists(local_sample):
        return FileResponse(local_sample, media_type="image/png")
    raise HTTPException(404, f"No render available for device '{device}'")


# ── Utility: rotate pexels folders ───────────────────────────────────────
def rotate_current_to_cache(theme: str):
    """
    Moves /pexels/current/<theme>/ → /pexels/cache/<theme>/ in GCS.
    Deletes old cache first.
    """
    if not storage_enabled:
        return
    # delete old cache
    cache_prefix = f"pexels/cache/{theme}/"
    for blob in _gcs_client.list_blobs(BUCKET, prefix=cache_prefix):
        blob.delete()
    # copy current → cache
    current_prefix = f"pexels/current/{theme}/"
    for blob in _gcs_client.list_blobs(BUCKET, prefix=current_prefix):
        new_key = blob.name.replace("pexels/current/", "pexels/cache/", 1)
        _gcs_bucket.copy_blob(blob, _gcs_bucket, new_key)
        blob.delete()


# ── Admin prefetch: deep randomized dual-folder Pexels system ────────────
@app.get("/admin/prefetch")
def admin_prefetch(
    token: str = Query(...),
    themes: Optional[str] = Query(None),
    count: Optional[int] = Query(None)
):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid token")
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise HTTPException(400, "PEXELS_API_KEY not configured")

    theme_list = [t.strip() for t in (themes or os.getenv("THEMES", "abstract,geometric,paper-collage,kids-shapes,minimal")).split(",") if t.strip()]
    per_theme = int(count or os.getenv("PER_THEME_COUNT", "8") or "8")

    written = {}
    for theme in theme_list:
        # rotate old -> cache
        rotate_current_to_cache(theme)
        # fetch new randomized set
        keys = prefetch_weekly_set(
            theme,
            api_key,
            per_theme,
            lambda k: gcs_exists(k),
            lambda k, d, ct, cache: gcs_write_bytes(k, d, ct, cache),
        )
        written[theme] = {"downloaded": len(keys), "keys": keys}

    return JSONResponse({"themes": theme_list, "result": written})