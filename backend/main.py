# backend/main.py
import os
import io
import json
import random
import datetime as dt
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

# --------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------
PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
THEMES = os.getenv("THEMES", "abstract,geometric,paper-collage,kids,photo").split(",")
DESIGNER_HTML_PATH = "./backend/web/designer/overlay_designer_v3_full.html"

# --------------------------------------------------------------
# GOOGLE CLOUD STORAGE
# --------------------------------------------------------------
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


# --------------------------------------------------------------
# APP
# --------------------------------------------------------------
app = FastAPI(title="Family Display Backend", version="1.0.0")

# --------------------------------------------------------------
# BASIC ROUTES
# --------------------------------------------------------------
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

# --------------------------------------------------------------
# ASSETS
# --------------------------------------------------------------
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

# --------------------------------------------------------------
# LAYOUT HTMLS (LEGACY)
# --------------------------------------------------------------
@app.get("/web/layouts/{name}.html", response_class=HTMLResponse)
def get_layout_html(name: str):
    local_path = f"./backend/web/layouts/{name}.html"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="layout html not found")

# --------------------------------------------------------------
# RENDER DATA / FRAME (placeholders for your real logic)
# --------------------------------------------------------------
@app.get("/v1/render_data", summary="Render data JSON")
def v1_render_data(theme: Optional[str] = None):
    today = dt.date.today().isoformat()
    chosen_theme = theme or random.choice(THEMES)
    payload = {
        "date": today,
        "city": "Darwin",
        "weather": {"temp": 33, "icon": "01d", "desc": "Sunny"},
        "dad_joke": "I told my wife she should embrace her mistakes — she gave me a hug.",
        "theme": chosen_theme,
    }
    return JSONResponse(payload)

@app.get("/v1/frame", summary="Frame PNG")
def v1_frame(theme: Optional[str] = None):
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9ccddbf\x00\x00\x00\x82\x00\x81"
        b"\x0b\xe7\x14\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return Response(content=png, media_type="image/png")

# --------------------------------------------------------------
# ADMIN PREFETCH (PEXELS)
# --------------------------------------------------------------
@app.get("/admin/prefetch", summary="Prefetch weekly images from Pexels")
def admin_prefetch(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")
    # Placeholder — insert your Pexels prefetch logic here
    return JSONResponse({"ok": True, "fetched": True, "themes": THEMES})

# --------------------------------------------------------------
# DESIGNER ENDPOINTS
# --------------------------------------------------------------
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
    # GCS first
    if storage_enabled:
        gcs_key = f"presets/{name}.json"
        if gcs_exists(gcs_key):
            data = gcs_read_bytes(gcs_key)
            return JSONResponse(json.loads(data))
    # Local fallback
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