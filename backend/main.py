# backend/main.py
import os
import json
import random
import datetime as dt
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

# ============================================================
# CONFIG
# ============================================================
PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
# you can override in Cloud Run: "abstract,geometric,paper-collage,kids,photo"
THEMES = os.getenv("THEMES", "abstract,geometric,kids,photo").split(",")
DESIGNER_HTML_PATH = "./backend/web/designer/overlay_designer_v3_full.html"

# Pexels sources (simple)
PEXELS_BASE_URL = "https://api.pexels.com/v1/search"
PEXELS_PER_THEME = int(os.getenv("PEXELS_PER_THEME", "6"))  # per run
PEXELS_IMAGE_WIDTH = 800
PEXELS_IMAGE_HEIGHT = 480

# ============================================================
# GCS
# ============================================================
storage_enabled = False
gcs_client = None
gcs_bucket = None
try:
    if GCS_BUCKET:
        from google.cloud import storage  # type: ignore
        gcs_client = storage.Client()
        gcs_bucket = gcs_client.bucket(GCS_BUCKET)
        storage_enabled = True
except Exception as e:
    print("⚠️ GCS disabled:", e)
    storage_enabled = False


def gcs_exists(key: str) -> bool:
    if not storage_enabled:
        return False
    return gcs_bucket.blob(key).exists()


def gcs_read_bytes(key: str) -> bytes:
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    return gcs_bucket.blob(key).download_as_bytes()


def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = gcs_bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)


def gcs_list(prefix: str) -> List[str]:
    if not storage_enabled:
        return []
    return [b.name for b in gcs_client.list_blobs(GCS_BUCKET, prefix=prefix)]


# ============================================================
# JOKES (fallback-first)
# ============================================================
LOCAL_JOKES = [
    "I told my wife she should embrace her mistakes — she gave me a hug.",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "I’m reading a book about anti-gravity. It’s impossible to put down.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I used to play piano by ear, now I use my hands.",
    "I asked my dog what’s two minus two. He said nothing.",
]

def get_random_joke() -> str:
    # 1) try GCS jokes if present
    if storage_enabled:
        gcs_key = "content/jokes.json"
        if gcs_exists(gcs_key):
            try:
                data = json.loads(gcs_read_bytes(gcs_key))
                if isinstance(data, list) and data:
                    return random.choice(data)
            except Exception:
                pass
    # 2) fallback to local list
    return random.choice(LOCAL_JOKES)


# ============================================================
# PEXELS HELPERS
# ============================================================
def rollover_pexels_cache():
    """
    Move everything from pexels/current/ → pexels/cache/<YYYY-MM-DD>/
    so that if today's fetch fails we still have a previous set.
    """
    if not storage_enabled:
        return
    today = dt.date.today().isoformat()
    src_prefix = "pexels/current/"
    dst_prefix = f"pexels/cache/{today}/"

    blobs = gcs_client.list_blobs(GCS_BUCKET, prefix=src_prefix)
    count = 0
    for blob in blobs:
        rel = blob.name[len(src_prefix):]  # e.g. "abstract_001.jpg"
        new_blob = gcs_bucket.blob(dst_prefix + rel)
        new_blob.rewrite(blob)  # copy
        count += 1
    print(f"[pexels] rollover {src_prefix} → {dst_prefix} ({count} files)")


def fetch_pexels_images() -> int:
    """
    Simple Pexels fetcher: for each theme, query and store top N images
    in pexels/current/<theme>/...
    If PEXELS_API_KEY missing, we just return 0.
    """
    if not storage_enabled:
        print("[pexels] storage not enabled, skipping fetch")
        return 0
    if not PEXELS_API_KEY:
        print("[pexels] no API key, skipping fetch")
        return 0

    import requests  # allowed here since it's runtime code

    total_saved = 0
    for theme in THEMES:
        params = {
            "query": theme,
            "per_page": PEXELS_PER_THEME,
            "orientation": "landscape"
        }
        headers = {
            "Authorization": PEXELS_API_KEY
        }
        resp = requests.get(PEXELS_BASE_URL, params=params, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"[pexels] failed for {theme}: {resp.status_code}")
            continue
        data = resp.json()
        photos = data.get("photos", [])
        for idx, p in enumerate(photos):
            src = p.get("src", {})
            url = src.get("landscape") or src.get("original")
            if not url:
                continue
            img_resp = requests.get(url, timeout=20)
            if img_resp.status_code != 200:
                continue
            # key: pexels/current/<theme>/<idx>.jpg
            key = f"pexels/current/{theme}/{idx}.jpg"
            gcs_write_bytes(key, img_resp.content, content_type="image/jpeg")
            total_saved += 1
    print(f"[pexels] saved {total_saved} images")
    return total_saved


def pick_image_from_bucket() -> Optional[bytes]:
    """
    Image fallback chain:
    1. pexels/current/
    2. pexels/cache/<latest-date>/
    3. images/current/
    4. images/backup/
    Returns raw bytes or None.
    """
    if not storage_enabled:
        return None

    # 1) pexels/current/
    current_keys = gcs_list("pexels/current/")
    current_jpgs = [k for k in current_keys if k.lower().endswith((".jpg", ".jpeg", ".png"))]
    if current_jpgs:
        key = random.choice(current_jpgs)
        return gcs_read_bytes(key)

    # 2) pexels/cache/<latest>/
    cache_keys = gcs_list("pexels/cache/")
    # find latest date folder
    dates = sorted(
        {k.split("/")[2] for k in cache_keys if k.count("/") >= 2},
        reverse=True
    )
    for date_prefix in dates:
        date_keys = gcs_list(f"pexels/cache/{date_prefix}/")
        date_jpgs = [k for k in date_keys if k.lower().endswith((".jpg", ".jpeg", ".png"))]
        if date_jpgs:
            key = random.choice(date_jpgs)
            return gcs_read_bytes(key)

    # 3) images/current/
    img_current = gcs_list("images/current/")
    img_current = [k for k in img_current if k.lower().endswith((".jpg", ".jpeg", ".png"))]
    if img_current:
        key = random.choice(img_current)
        return gcs_read_bytes(key)

    # 4) images/backup/
    img_backup = gcs_list("images/backup/")
    img_backup = [k for k in img_backup if k.lower().endswith((".jpg", ".jpeg", ".png"))]
    if img_backup:
        key = random.choice(img_backup)
        return gcs_read_bytes(key)

    return None


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(title="Family Display Backend", version="1.0.0")

# ============================================================
# ROOT
# ============================================================
@app.get("/")
def root():
    return {
        "name": "family-display-backend",
        "version": "1.0.0",
        "designer": "/designer/",
        "presets": "/presets/<name>.json",
        "layouts": "/layouts/<device>",
        "frame": "/v1/frame",
        "render_data": "/v1/render_data",
    }


# ============================================================
# STATIC ASSETS (old paths still work)
# ============================================================
@app.get("/assets/{path:path}", summary="Static asset proxy")
def assets_proxy(path: str):
    local_path = f"./backend/web/{path}"
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            data = f.read()
        if path.endswith(".svg"):
            return Response(data, media_type="image/svg+xml")
        if path.endswith(".png"):
            return Response(data, media_type="image/png")
        if path.endswith(".jpg") or path.endswith(".jpeg"):
            return Response(data, media_type="image/jpeg")
        return Response(data)
    if storage_enabled:
        key = f"assets/{path}"
        if gcs_exists(key):
            data = gcs_read_bytes(key)
            return Response(data)
    raise HTTPException(status_code=404, detail="asset not found")


# ============================================================
# FONTS (local → GCS)
# ============================================================
@app.get("/fonts/{subpath:path}")
def get_font(subpath: str):
    local_path = f"./backend/web/fonts/{subpath}"
    if os.path.exists(local_path):
        if local_path.endswith(".css"):
            with open(local_path, "r", encoding="utf-8") as f:
                return Response(f.read(), media_type="text/css")
        else:
            with open(local_path, "rb") as f:
                return Response(f.read(), media_type="font/ttf")
    if storage_enabled:
        gcs_key = f"fonts/{subpath}"
        if gcs_exists(gcs_key):
            data = gcs_read_bytes(gcs_key)
            mt = "text/css" if subpath.endswith(".css") else "font/ttf"
            return Response(data, media_type=mt)
    raise HTTPException(status_code=404, detail="font not found")


# ============================================================
# LEGACY HTML LAYOUTS
# ============================================================
@app.get("/web/layouts/{name}.html", response_class=HTMLResponse)
def get_layout_html(name: str):
    local_path = f"./backend/web/layouts/{name}.html"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="layout html not found")


# ============================================================
# RENDER DATA (used by HTML/SVG renderer)
# ============================================================
@app.get("/v1/render_data", summary="Render data JSON")
def v1_render_data(theme: Optional[str] = None):
    today = dt.date.today().isoformat()
    chosen_theme = theme or random.choice(THEMES)
    payload = {
        "date": today,
        "city": "Darwin",
        "weather": {"temp": 33, "icon": "01d", "desc": "Sunny"},
        "dad_joke": get_random_joke(),
        "theme": chosen_theme,
    }
    return JSONResponse(payload)


# ============================================================
# FRAME (with image fallback chain)
# ============================================================
@app.get("/v1/frame", summary="Frame PNG")
def v1_frame(theme: Optional[str] = None):
    # 1) try to get an image from bucket (pexels → images → backup)
    img = pick_image_from_bucket()
    if img:
        return Response(content=img, media_type="image/jpeg")
    # 2) last resort tiny PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9ccddbf\x00\x00\x00\x82\x00\x81"
        b"\x0b\xe7\x14\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return Response(content=png, media_type="image/png")


# ============================================================
# ADMIN: PREFETCH (SCHEDULER CALLS THIS)
# ============================================================
@app.get("/admin/prefetch", summary="Prefetch weekly images from Pexels")
def admin_prefetch(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")

    # 1) rollover old current → cache/<date>/
    rollover_pexels_cache()

    # 2) fetch fresh images (if Pexels is configured)
    saved = fetch_pexels_images()

    return JSONResponse({
        "ok": True,
        "rolled_over": True,
        "saved": saved,
        "themes": THEMES,
    })


# ============================================================
# DESIGNER ENDPOINTS
# ============================================================
@app.get("/designer/", response_class=HTMLResponse)
def get_designer():
    if os.path.exists(DESIGNER_HTML_PATH):
        with open(DESIGNER_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Designer not found</h1>"


@app.get("/layouts/{device_id}")
def get_layout(device_id: str):
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")
    key = f"layouts/{device_id}/current.json"
    if not gcs_exists(key):
        raise HTTPException(status_code=404, detail=f"layout for device '{device_id}' not found")
    data = gcs_read_bytes(key)
    return JSONResponse(json.loads(data))


@app.post("/admin/layouts/{device_id}")
async def save_layout(device_id: str, request: Request):
    token = request.headers.get("x-admin-token") or request.query_params.get("token")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")
    payload = await request.json()
    if "elements" not in payload:
        raise HTTPException(status_code=400, detail="layout must contain 'elements'")
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")
    key = f"layouts/{device_id}/current.json"
    gcs_write_bytes(
        key,
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    return {"ok": True, "device": device_id}


@app.get("/presets/{name}.json")
def get_preset(name: str):
    # 1) GCS override
    if storage_enabled:
        gcs_key = f"presets/{name}.json"
        if gcs_exists(gcs_key):
            data = gcs_read_bytes(gcs_key)
            return JSONResponse(json.loads(data))
    # 2) local baked-in
    local_path = f"./backend/web/designer/presets/{name}.json"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    raise HTTPException(status_code=404, detail=f"preset '{name}' not found")


@app.get("/svgs/{name}")
def get_svg(name: str):
    local_path = f"./backend/web/designer/svgs/{name}"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="image/svg+xml")
    if storage_enabled:
        gcs_key = f"svgs/{name}"
        if gcs_exists(gcs_key):
            data = gcs_read_bytes(gcs_key)
            return HTMLResponse(data, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail=f"svg '{name}' not found")
