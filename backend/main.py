import os
import io
import json
import random
import datetime
import pathlib
from typing import Optional, List

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

storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET)

# ──────────────────────────────────────────────────────────────────────────────
# UTILS
# ──────────────────────────────────────────────────────────────────────────────
def _iso_week() -> str:
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"

def _blob_text(path: str) -> Optional[str]:
    b = bucket.blob(path)
    try:
        if not b.exists():  # type: ignore
            return None
    except Exception:
        return None
    return b.download_as_text()

def _put_png(path: str, data: bytes):
    b = bucket.blob(path)
    b.cache_control = "public, max-age=3600"
    b.upload_from_string(data, content_type="image/png")

# fonts
def _load_font(size: int, weight: str = "400") -> ImageFont.FreeTypeFont:
    try:
        if FONT_DIR and os.path.isdir(FONT_DIR):
            pick = None
            if weight >= "700" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Bold.ttf")):
                pick = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
            elif weight <= "300" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Light.ttf")):
                pick = os.path.join(FONT_DIR, "Roboto-Light.ttf")
            elif os.path.exists(os.path.join(FONT_DIR, "Roboto-Regular.ttf")):
                pick = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
            if pick:
                return ImageFont.truetype(pick, size=size)
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()

# brightness for auto text color
def _is_dark(png_bytes: bytes) -> bool:
    im = Image.open(io.BytesIO(png_bytes)).convert("L").resize((50, 30))
    return sum(im.getdata()) / (50 * 30) < 110

# cover+crop to 800x480
def _download_and_fit(url: str, size=(800, 480)) -> Image.Image:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    tw, th = size
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))

# simple glass card
def _glass(draw: ImageDraw.ImageDraw, x, y, w, h, alpha=180, radius=14):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                           fill=(255, 255, 255, alpha), outline=(185, 215, 211, 255), width=1)

def _layout_paths(device: str):
    base = f"layouts/{device}"
    return {
        "current": f"{base}/current.json",
        "ver": f"{base}/versions/{int(datetime.datetime.now().timestamp())}.json",
    }

# weather + joke
def _weather(city="Darwin", country="AU"):
    if not OPENWEATHER_API_KEY:
        return {"city": city, "min": 26, "max": 33, "desc": "Few Clouds", "icon": "⛅"}
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": f"{city},{country}", "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=8,
        )
        j = r.json()
        main = j.get("main", {})
        w = (j.get("weather") or [{}])[0]
        code = w.get("icon", "02d")
        icon = "☀️" if code.startswith("01") else "⛅" if code.startswith("02") else "☁️" if code.startswith("03") else "🌧️"
        return {
            "city": j.get("name") or city,
            "min": int(round(main.get("temp_min", 26))),
            "max": int(round(main.get("temp_max", 33))),
            "desc": (w.get("description") or "—").title(),
            "icon": icon,
        }
    except Exception:
        return {"city": city, "min": 26, "max": 33, "desc": "Few Clouds", "icon": "⛅"}

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
# LAYOUT LOAD
# ──────────────────────────────────────────────────────────────────────────────
def _load_layout(device: str) -> dict:
    """Load designer JSON if present or return a sensible default."""
    cur = _layout_paths(device)["current"]
    raw = _blob_text(cur)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    # default matches your sticker layout proportions
    return {
        "device": device,
        "mode": DEFAULT_MODE,
        "elements": [
            {"kind": "box",  "x": 16, "y": 360, "w": 360, "h": 96, "role": "CARD_WEATHER"},
            {"kind": "box",  "x": 400, "y": 360, "w": 384, "h": 96, "role": "CARD_JOKE"},
            {"kind": "box",  "x": 590, "y": 18,  "w": 194, "h": 56, "role": "CARD_GENERIC"},
            {"kind": "text", "x": 28, "y": 372, "w": 320, "h": 30, "type": "WEATHER_CITY"},
            {"kind": "text", "x": 28, "y": 405, "w": 320, "h": 24, "type": "WEATHER_MINMAX"},
            {"kind": "icon", "x": 325, "y": 374, "w": 28,  "h": 28, "type": "WEATHER_ICON"},
            {"kind": "text", "x": 412, "y": 380, "w": 360, "h": 60, "type": "JOKE"},
            {"kind": "text", "x": 605, "y": 28,  "w": 160, "h": 28, "type": "DATE"},
        ],
    }

# ──────────────────────────────────────────────────────────────────────────────
# RENDER ENGINE (uses layout)
# ──────────────────────────────────────────────────────────────────────────────
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
    if cur: lines.append(cur)
    return "\n".join(lines)

def _render_from_layout(bg_png: bytes, layout: dict) -> bytes:
    im = Image.open(io.BytesIO(bg_png)).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    dark = _is_dark(bg_png)

    weather = _weather()
    joke = _dad_joke()
    date_str = datetime.datetime.now().strftime("%a, %d %b")

    for el in layout.get("elements", []):
        kind = el.get("kind", "box")
        x = int(el.get("x", 0)); y = int(el.get("y", 0))
        w = int(el.get("w", 100)); h = int(el.get("h", 40))
        etype = el.get("type")
        color = el.get("color") or ("#FFFFFF" if dark else "#000000")

        if kind == "box":
            _glass(draw, x, y, w, h, alpha=180, radius=14)
            continue

        # choose font size from element height
        size = max(14, int(h * 0.7))
        weight = "700" if "bold" in (el.get("weight", "").lower()) else "400"
        font = _load_font(size=size, weight=weight)

        # text source
        text = el.get("text", "")
        if etype == "WEATHER_CITY":
            text = weather["city"]
        elif etype == "WEATHER_MINMAX":
            text = f"{weather['min']}° / {weather['max']}°"
        elif etype == "WEATHER_NOTE":
            text = weather["desc"]
        elif etype == "WEATHER_ICON":
            text = weather["icon"]
        elif etype == "DATE":
            text = date_str
        elif etype == "JOKE":
            text = joke

        # wrap inside element width (padding 8)
        wrapped = _wrap(draw, text, font, max_w=max(8, w - 12))
        draw.multiline_text((x + 8, y + 6), wrapped, font=font, fill=color, spacing=4)

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
        "version": "fix-800x480-fonts-layout-2025-10-26",
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

# Prefetch via Pexels (admin)
PEXELS_SEARCH = "https://api.pexels.com/v1/search"

@app.post("/admin/prefetch")
def admin_prefetch():
    tok = request.args.get("token") or request.headers.get("X-Admin-Token")
    if ADMIN_TOKEN and tok != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or ["nature","geometry","minimal","ocean","architecture","kids","abstract","space"]
    if isinstance(themes, str):
        themes = [t.strip() for t in themes.split(",") if t.strip()]
    per_theme = int(body.get("per_theme", body.get("count", PER_THEME_COUNT)))
    overwrite = bool(body.get("overwrite", False))
    week = body.get("week") or _iso_week()

    if not PEXELS_API_KEY:
        return jsonify({"error": "PEXELS_API_KEY missing"}), 500

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
            name = f"images/{week}/{theme}/v_{i}.png"
            if not overwrite and bucket.blob(name).exists():  # type: ignore
                continue
            _put_png(name, buf.getvalue())
            saved.append(name)

    return jsonify({"status": "done", "week": week, "themes": themes, "saved": len(saved)})

# List cached images
@app.get("/v1/list")
def v1_list():
    week = request.args.get("week") or _iso_week()
    theme = request.args.get("theme")
    prefix = f"images/{week}/"
    if theme:
        prefix += f"{theme.strip().rstrip('/')}/"
    blobs = _list_blobs(prefix, limit=int(request.args.get("limit", "500")))
    return jsonify({"week": week, "theme": theme, "count": len(blobs), "objects": blobs})

def _list_blobs(prefix: str, limit: int = 500) -> List[str]:
    out = []
    for i, b in enumerate(storage_client.list_blobs(GCS_BUCKET, prefix=prefix)):
        if i >= limit: break
        out.append(b.name)
    return out

# Single frame render (uses layout)
@app.get("/v1/frame")
def v1_frame():
    device = request.args.get("device") or DEFAULT_DEVICE
    theme = request.args.get("theme") or DEFAULT_THEME
    week = request.args.get("week") or _iso_week()

    # choose a background from cache
    prefix = f"images/{week}/{theme}/"
    blobs = list(storage_client.list_blobs(GCS_BUCKET, prefix=prefix))
    if not blobs:
        return jsonify({"error": f"no cached images for week={week} theme={theme}"}), 404
    bg_png = random.choice(blobs).download_as_bytes()

    layout = _load_layout(device)
    png = _render_from_layout(bg_png, layout)
    return send_file(io.BytesIO(png), mimetype="image/png")

# Random batch (auto-pick theme if none). Returns first PNG + header manifest
@app.get("/v1/random")
def v1_random():
    device = request.args.get("device") or DEFAULT_DEVICE
    week = request.args.get("week") or _iso_week()
    theme = request.args.get("theme")
    if not theme:
        base = f"images/{week}/"
        themes = sorted({b.name.split("/")[2] for b in storage_client.list_blobs(GCS_BUCKET, prefix=base)
                         if len(b.name.split("/")) > 2})
        theme = random.choice(themes) if themes else DEFAULT_THEME

    blobs = list(storage_client.list_blobs(GCS_BUCKET, prefix=f"images/{week}/{theme}/"))
    if not blobs:
        return jsonify({"error": f"no cached images for {theme}"}), 404

    layout = _load_layout(device)
    picks = random.sample(blobs, min(4, len(blobs)))
    frames = []
    for b in picks:
        bg = b.download_as_bytes()
        frames.append(_render_from_layout(bg, layout))

    manifest = [b.name for b in picks]
    return send_file(io.BytesIO(frames[0]), mimetype="image/png",
                     headers={"X-Random-Manifest": json.dumps(manifest)})

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
