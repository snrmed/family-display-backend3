# backend/main.py
import os
import io
import json
import random
import datetime
import pathlib
from typing import List, Optional

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory, abort
from google.cloud import storage
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────────────────────────────────────
# ENV / GLOBALS
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

DEFAULT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "familydisplay")
DEFAULT_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")
DEFAULT_THEME = "abstract"
PER_THEME_COUNT = int(os.getenv("PER_THEME_COUNT", "8") or 8)
FONT_DIR = os.getenv("FONT_DIR", "./backend/web/designer/fonts")

# UI constants
GLASS_ALPHA = 180
GLASS_RADIUS = 14
TEXT_PADDING_X = 8
TEXT_PADDING_Y = 6
TEXT_SPACING = 4

storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET)

# caches
_font_cache: dict[str, ImageFont.FreeTypeFont] = {}
_icon_cache: dict[str, Image.Image] = {}

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _blob_text(path: str) -> Optional[str]:
    b = bucket.blob(path)
    try:
        if not b.exists():  # type: ignore[attr-defined]
            return None
    except Exception:
        return None
    return b.download_as_text()

def _put_png(path: str, data: bytes, cache_control: str = "public, max-age=86400"):
    b = bucket.blob(path)
    b.cache_control = cache_control
    b.upload_from_string(data, content_type="image/png")

def _load_font(size: int, weight: str = "400") -> ImageFont.FreeTypeFont:
    cache_key = f"{size}:{weight}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    try:
        if FONT_DIR and os.path.isdir(FONT_DIR):
            path = None
            try:
                weight_int = int(weight)
            except (ValueError, TypeError):
                weight_int = 400
            if weight_int >= 700 and os.path.exists(os.path.join(FONT_DIR, "Roboto-Bold.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
            elif weight_int <= 300 and os.path.exists(os.path.join(FONT_DIR, "Roboto-Light.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Light.ttf")
            elif os.path.exists(os.path.join(FONT_DIR, "Roboto-Regular.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
            if path:
                font = ImageFont.truetype(path, size=size)
                _font_cache[cache_key] = font
                return font
        font = ImageFont.truetype("DejaVuSans.ttf", size=size)
        _font_cache[cache_key] = font
        return font
    except Exception:
        font = ImageFont.load_default()
        _font_cache[cache_key] = font
        return font

def _download_and_fit(url: str, size=(800, 480)) -> Image.Image:
    """Download an image and cover-crop to exact size."""
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    tw, th = size
    resample = getattr(Image, "Resampling", Image).LANCZOS
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), resample)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))

def _fit_to_800x480(png_bytes: bytes) -> bytes:
    """Cover-crop any PNG/JPEG bytes to exactly 800×480."""
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    tw, th = 800, 480
    resample = getattr(Image, "Resampling", Image).LANCZOS
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), resample)
    left, top = (nw - tw) // 2, (nh - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out.getvalue()

def _glass(draw: ImageDraw.ImageDraw, x, y, w, h, alpha=GLASS_ALPHA, radius=GLASS_RADIUS):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                           fill=(255, 255, 255, alpha), outline=(185, 215, 211, 255), width=1)

def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)

def _layout_paths(device: str):
    base = f"layouts/{device}"
    return {
        "current": f"{base}/current.json",
        "ver": f"{base}/versions/{int(datetime.datetime.now().timestamp())}.json",
    }

# ──────────────────────────────────────────────────────────────────────────────
# OPENWEATHER ICONS (PNG)
# ──────────────────────────────────────────────────────────────────────────────
OWM_ICON_URL = "https://openweathermap.org/img/wn/{code}@2x.png"

def _get_weather_icon_image(code: str) -> Optional[Image.Image]:
    if not code:
        code = "02d"
    if code in _icon_cache:
        return _icon_cache[code]

    gcs_path = f"icons/openweather/{code}.png"
    blob = bucket.blob(gcs_path)
    try:
        if blob.exists():  # type: ignore[attr-defined]
            data = blob.download_as_bytes()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            _icon_cache[code] = img
            return img
    except Exception:
        pass

    try:
        r = requests.get(OWM_ICON_URL.format(code=code), timeout=10)
        if r.status_code == 200:
            data = r.content
            _put_png(gcs_path, data)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            _icon_cache[code] = img
            return img
    except Exception:
        pass
    return None

def _paste_icon_rgba(base: Image.Image, icon: Image.Image, x: int, y: int, w: int, h: int):
    resample = getattr(Image, "Resampling", Image).LANCZOS
    iw, ih = icon.size
    if iw == 0 or ih == 0:
        return
    scale = min(w / iw, h / ih) * 0.9
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    icon_resized = icon.resize((nw, nh), resample)
    px = x + (w - nw) // 2
    py = y + (h - nh) // 2
    base.alpha_composite(icon_resized, (px, py))

# ──────────────────────────────────────────────────────────────────────────────
# DATA SOURCES
# ──────────────────────────────────────────────────────────────────────────────
def _weather(city="Darwin", country="AU"):
    if not OPENWEATHER_API_KEY:
        return {"city": city, "min": 26, "max": 33, "desc": "Few Clouds", "icon": "⛅", "code": "02d"}
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": f"{city},{country}", "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=8,
        )
        j = r.json()
        main = j.get("main", {})
        w = (j.get("weather") or [{}])[0]
        code = (w.get("icon") or "02d")
        icon_emoji = "☀️" if code.startswith("01") else "⛅" if code.startswith("02") else "☁️" if code.startswith("03") else "🌧️"
        return {
            "city": j.get("name") or city,
            "min": int(round(main.get("temp_min", 26))),
            "max": int(round(main.get("temp_max", 33))),
            "desc": (w.get("description") or "—").title(),
            "icon": icon_emoji,
            "code": code,
        }
    except Exception:
        return {"city": city, "min": 26, "max": 33, "desc": "Few Clouds", "icon": "⛅", "code": "02d"}

def _dad_joke():
    fallbacks = [
        "I'm reading a book on anti-gravity. It's impossible to put down.",
        "Why do pirates not know the alphabet? They always get stuck at 'C'.",
        "I used to play piano by ear… now I use my hands.",
        "Why can't you trust atoms? They make up everything!",
    ]
    try:
        r = requests.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"}, timeout=8)
        if r.status_code == 200:
            return r.json().get("joke") or random.choice(fallbacks)
    except Exception:
        pass
    return random.choice(fallbacks)

# ──────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ──────────────────────────────────────────────────────────────────────────────
def _load_layout(device: str) -> dict:
    paths = _layout_paths(device)
    raw = _blob_text(paths["current"])
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {
        "device": device,
        "mode": DEFAULT_MODE,
        "elements": [
            {"kind": "box",  "x": 16,  "y": 360, "w": 360, "h": 96,  "role": "CARD_WEATHER"},
            {"kind": "box",  "x": 400, "y": 360, "w": 384, "h": 96,  "role": "CARD_JOKE"},
            {"kind": "box",  "x": 620, "y": 16,  "w": 164, "h": 48,  "role": "CARD_GENERIC"},
            {"kind": "icon", "x": 28,  "y": 372, "w": 36,  "h": 36,  "type": "WEATHER_ICON"},
            {"kind": "text", "x": 80,  "y": 372, "w": 260, "h": 46,  "type": "WEATHER_CITY",   "weight": "700"},
            {"kind": "text", "x": 80,  "y": 412, "w": 260, "h": 32,  "type": "WEATHER_MINMAX"},
            {"kind": "text", "x": 80,  "y": 444, "w": 260, "h": 24,  "type": "WEATHER_NOTE"},
            {"kind": "text", "x": 412, "y": 376, "w": 360, "h": 80,  "type": "JOKE"},
            {"kind": "text", "x": 632, "y": 28,  "w": 140, "h": 28,  "type": "DATE",          "weight": "700"}
        ],
    }

# ──────────────────────────────────────────────────────────────────────────────
# RENDER
# ──────────────────────────────────────────────────────────────────────────────
def _render_from_layout(bg_png: bytes, layout: dict) -> bytes:
    bg_png = _fit_to_800x480(bg_png)
    im = Image.open(io.BytesIO(bg_png)).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    weather = _weather()
    joke = _dad_joke()
    date_str = datetime.datetime.now().strftime("%a, %d %b")

    for el in layout.get("elements", []):
        kind = el.get("kind", "box")
        x = int(el.get("x", 0)); y = int(el.get("y", 0))
        w = int(el.get("w", 100)); h = int(el.get("h", 40))
        etype = el.get("type")
        color = el.get("color") or "#000000"

        if kind == "box":
            _glass(draw, x, y, w, h)
            continue

        if kind == "icon" and etype == "WEATHER_ICON":
            code = weather.get("code") or "02d"
            icon_img = _get_weather_icon_image(code)
            if icon_img is not None:
                _paste_icon_rgba(im, icon_img, x, y, w, h)
            continue

        size = max(14, int(h * 0.7))
        weight_raw = el.get("weight", "400")
        weight = "700" if "bold" in str(weight_raw).lower() else (str(weight_raw) if weight_raw else "400")
        font = _load_font(size=size, weight=weight)

        text = el.get("text", "")
        if etype == "WEATHER_CITY":
            text = weather["city"]
        elif etype == "WEATHER_MINMAX":
            text = f"{weather['min']}° / {weather['max']}°"
        elif etype == "WEATHER_NOTE":
            text = weather["desc"]
        elif etype == "DATE":
            text = date_str
        elif etype == "JOKE":
            text = joke

        wrapped = _wrap(draw, text, font, max_w=max(8, w - TEXT_PADDING_X * 2))
        draw.multiline_text((x + TEXT_PADDING_X, y + TEXT_PADDING_Y),
                            wrapped, font=font, fill=color, spacing=TEXT_SPACING)

    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out.getvalue()

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return jsonify({
        "status": "ok",
        "version": "pexels-current-backup-2025-10-27",
        "gcs": True,
        "pexels": bool(PEXELS_API_KEY),
        "openweather": bool(OPENWEATHER_API_KEY),
        "default_device": DEFAULT_DEVICE,
        "default_mode": DEFAULT_MODE
    })

# Designer static
BASE_DIR = pathlib.Path(__file__).resolve().parent
DESIGNER_DIR = BASE_DIR / "web" / "designer"

@app.route("/designer/")
def designer_index():
    return send_from_directory(DESIGNER_DIR, "overlay_designer_v3_full.html")

@app.route("/designer/presets/<path:fname>")
def designer_presets(fname):
    return send_from_directory(DESIGNER_DIR / "presets", fname)

@app.route("/designer/fonts/<path:fname>")
def designer_fonts(fname):
    return send_from_directory(DESIGNER_DIR / "fonts", fname)

# ──────────────────────────────────────────────────────────────────────────────
# ADMIN: PEXELS PREFETCH (CURRENT/BACKUP MODEL)
# ──────────────────────────────────────────────────────────────────────────────
PEXELS_SEARCH = "https://api.pexels.com/v1/search"

@app.post("/admin/prefetch")
def admin_prefetch():
    tok = request.args.get("token") or request.headers.get("X-Admin-Token")
    if not ADMIN_TOKEN or tok != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or ["abstract"]
    if isinstance(themes, str):
        themes = [t.strip() for t in themes.split(",") if t.strip()]
    per_theme = int(body.get("per_theme", body.get("count", PER_THEME_COUNT)))
    overwrite = bool(body.get("overwrite", True))

    if not PEXELS_API_KEY:
        return jsonify({"error": "PEXELS_API_KEY missing"}), 500

    # Backup existing current → backup
    for b in storage_client.list_blobs(GCS_BUCKET, prefix="images/current/"):
        new_name = b.name.replace("images/current/", "images/backup/", 1)
        bucket.copy_blob(b, bucket, new_name)

    headers = {"Authorization": PEXELS_API_KEY}
    saved = []
    for theme in themes:
        params = {"query": theme, "per_page": max(8, per_theme), "orientation": "landscape", "size": "large"}
        r = requests.get(PEXELS_SEARCH, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            continue
        photos = (r.json().get("photos") or [])[:per_theme]
        for i, p in enumerate(photos):
            src = p.get("src", {})
            url = src.get("large2x") or src.get("large") or src.get("original")
            if not url:
                continue
            im = _download_and_fit(url, (800, 480))
            buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
            name = f"images/current/{theme}/v_{i}.png"
            if not overwrite and bucket.blob(name).exists():  # type: ignore[attr-defined]
                continue
            _put_png(name, buf.getvalue())
            saved.append(name)

    return jsonify({"status": "done", "themes": themes, "saved": len(saved)})

# ──────────────────────────────────────────────────────────────────────────────
# LIST + FRAME + RANDOM
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/v1/list")
def v1_list():
    theme = request.args.get("theme")
    prefix = f"images/current/"
    if theme:
        prefix += f"{theme.strip().rstrip('/')}/"
    objs = [b.name for b in storage_client.list_blobs(GCS_BUCKET, prefix=prefix)]
    return jsonify({"theme": theme, "count": len(objs), "objects": objs})

@app.get("/v1/frame")
def v1_frame():
    device = request.args.get("device") or DEFAULT_DEVICE
    theme = request.args.get("theme") or DEFAULT_THEME
    prefix = f"images/current/{theme}/"
    blobs = list(storage_client.list_blobs(GCS_BUCKET, prefix=prefix))
    if not blobs:
        return jsonify({"error": f"no cached images for theme={theme}"}), 404
    bg_png = random.choice(blobs).download_as_bytes()
    layout = _load_layout(device)
    png = _render_from_layout(bg_png, layout)
    return send_file(io.BytesIO(png), mimetype="image/png")

@app.get("/v1/random")
def v1_random():
    device = request.args.get("device") or DEFAULT_DEVICE
    theme = request.args.get("theme")
    if not theme:
        base = f"images/current/"
        themes = sorted({b.name.split("/")[2] for b in storage_client.list_blobs(GCS_BUCKET, prefix=base)
                         if len(b.name.split("/")) > 2})
        theme = random.choice(themes) if themes else DEFAULT_THEME

    blobs = list(storage_client.list_blobs(GCS_BUCKET, prefix=f"images/current/{theme}/"))
    if not blobs:
        return jsonify({"error": f"no cached images for {theme}"}), 404

    layout = _load_layout(device)
    picks = random.sample(blobs, min(4, len(blobs)))
    frames = []
    for b in picks:
        bg = b.download_as_bytes()
        frames.append(_render_from_layout(bg, layout))

    manifest = [b.name for b in picks]
    resp = send_file(io.BytesIO(frames[0]), mimetype="image/png")
    resp.headers["X-Random-Manifest"] = json.dumps(manifest)
    return resp

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
