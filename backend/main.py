# backend/main.py - COMPLETE FIXED VERSION for E-ink Display

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

# FIXED: Correct path resolution
BASE_DIR = pathlib.Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "web" / "designer" / "fonts"

# UI Constants - OPTIMIZED FOR E-INK (Waveshare 6-color Spectra)
GLASS_ALPHA = 100  # Much more transparent (was 180) - better for e-ink
GLASS_RADIUS = 14
TEXT_PADDING_X = 8
TEXT_PADDING_Y = 6
TEXT_SPACING = 4

storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET)

# Font cache for performance
_font_cache = {}

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _iso_week() -> str:
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"

def _blob_text(path: str) -> Optional[str]:
    b = bucket.blob(path)
    try:
        if not b.exists():
            return None
    except Exception:
        return None
    return b.download_as_text()

def _put_png(path: str, data: bytes):
    b = bucket.blob(path)
    b.cache_control = "public, max-age=3600"
    b.upload_from_string(data, content_type="image/png")

def _load_font(size: int, weight: str = "400") -> ImageFont.FreeTypeFont:
    """Load Roboto from FONT_DIR with FIXED path handling."""
    cache_key = f"{size}_{weight}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    try:
        # Parse weight
        try:
            weight_int = int(weight)
        except (ValueError, TypeError):
            weight_int = 400
        
        # FIXED: Check if FONT_DIR exists and construct proper paths
        if FONT_DIR.exists() and FONT_DIR.is_dir():
            font_path = None
            
            # Select appropriate font file based on weight
            if weight_int >= 700:
                bold_path = FONT_DIR / "Roboto-Bold.ttf"
                if bold_path.exists():
                    font_path = str(bold_path)
            elif weight_int <= 300:
                light_path = FONT_DIR / "Roboto-Light.ttf"
                if light_path.exists():
                    font_path = str(light_path)
            
            # Fallback to Regular if specific weight not found
            if not font_path:
                regular_path = FONT_DIR / "Roboto-Regular.ttf"
                if regular_path.exists():
                    font_path = str(regular_path)
            
            # Load the font if we found a valid path
            if font_path:
                font = ImageFont.truetype(font_path, size=size)
                _font_cache[cache_key] = font
                print(f"✓ Loaded Roboto: {pathlib.Path(font_path).name} at size {size}")
                return font
        
        # Fallback to DejaVu Sans
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=size)
        _font_cache[cache_key] = font
        print(f"⚠ Using fallback DejaVu font at size {size}")
        return font
    except Exception as e:
        # Last resort: default bitmap font
        print(f"⚠ Font loading failed ({e}), using default bitmap font")
        font = ImageFont.load_default()
        _font_cache[cache_key] = font
        return font

def _download_and_fit(url: str, size=(800, 480)) -> Image.Image:
    """Download an image and cover-crop to exact size."""
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    tw, th = size
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))

def _fit_to_800x480(png_bytes: bytes) -> bytes:
    """Cover-crop any PNG/JPEG bytes to exactly 800×480."""
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    tw, th = 800, 480
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out.getvalue()

def _glass(draw: ImageDraw.ImageDraw, x, y, w, h, alpha=GLASS_ALPHA, radius=GLASS_RADIUS):
    """Draw frosted glass box - optimized for e-ink with higher transparency."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                          fill=(255, 255, 255, alpha), 
                          outline=(185, 215, 211, 255), 
                          width=1)

def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    """Wrap text to fit within max_w pixels."""
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
# DATA SOURCES
# ──────────────────────────────────────────────────────────────────────────────

def _weather(city="Darwin", country="AU"):
    """Fetch weather with FIXED emoji icons optimized for e-ink display."""
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
        code = (w.get("icon") or "02d")
        
        # Simpler emoji set that renders better on e-ink displays
        if code.startswith("01"):
            icon = "☀"  # Clear sky
        elif code.startswith("02"):
            icon = "⛅"  # Partly cloudy
        elif code.startswith("03") or code.startswith("04"):
            icon = "☁"  # Cloudy
        elif code.startswith("09") or code.startswith("10"):
            icon = "🌧"  # Rain
        elif code.startswith("11"):
            icon = "⛈"  # Thunderstorm
        elif code.startswith("13"):
            icon = "❄"  # Snow
        else:
            icon = "🌫"  # Mist/Fog
        
        return {
            "city": j.get("name") or city,
            "min": int(round(main.get("temp_min", 26))),
            "max": int(round(main.get("temp_max", 33))),
            "desc": (w.get("description") or "—").title(),
            "icon": icon,
        }
    except Exception as e:
        print(f"⚠ Weather fetch error: {e}")
        return {"city": city, "min": 26, "max": 33, "desc": "Few Clouds", "icon": "⛅"}

def _dad_joke():
    """Fetch dad joke with fallbacks."""
    fallbacks = [
        "I'm reading a book on anti-gravity. It's impossible to put down.",
        "Why do pirates not know the alphabet? They always get stuck at 'C'.",
        "I used to play piano by ear… now I use my hands.",
        "Why can't you trust atoms? They make up everything!",
    ]
    try:
        r = requests.get("https://icanhazdadjoke.com/", 
                        headers={"Accept": "application/json"}, 
                        timeout=8)
        if r.status_code == 200:
            return r.json().get("joke") or random.choice(fallbacks)
    except Exception:
        pass
    return random.choice(fallbacks)

# ──────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ──────────────────────────────────────────────────────────────────────────────

def _load_layout(device: str) -> dict:
    """Use saved Designer layout or fallback to a sensible default."""
    paths = _layout_paths(device)
    raw = _blob_text(paths["current"])
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    
    # Default = Sticker Parade proportions (optimized for e-ink)
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
    """Render overlay with FIXED font loading and icon rendering for e-ink."""
    # Ensure background is exactly 800×480
    bg_png = _fit_to_800x480(bg_png)
    
    im = Image.open(io.BytesIO(bg_png)).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    
    weather = _weather()
    joke = _dad_joke()
    date_str = datetime.datetime.now().strftime("%a, %d %b")
    
    for el in layout.get("elements", []):
        kind = el.get("kind", "box")
        x = int(el.get("x", 0))
        y = int(el.get("y", 0))
        w = int(el.get("w", 100))
        h = int(el.get("h", 40))
        etype = el.get("type")
        color = el.get("color") or "#000000"
        
        if kind == "box":
            _glass(draw, x, y, w, h, alpha=GLASS_ALPHA, radius=GLASS_RADIUS)
            continue
        
        # Calculate font size
        size = max(14, int(h * 0.7))
        
        # Parse weight properly
        weight_raw = el.get("weight", "400")
        if "bold" in str(weight_raw).lower():
            weight = "700"
        else:
            weight = str(weight_raw) if weight_raw else "400"
        
        # FIXED: Load font with corrected path handling
        font = _load_font(size=size, weight=weight)
        
        # Get text content
        text = el.get("text", "")
        if etype == "WEATHER_CITY":
            text = weather["city"]
        elif etype == "WEATHER_MINMAX":
            text = f"{weather['min']}° / {weather['max']}°"
        elif etype == "WEATHER_NOTE":
            text = weather["desc"]
        elif etype == "WEATHER_ICON":
            text = weather["icon"]
            # FIXED: Use larger font for weather icons (better visibility on e-ink)
            icon_size = int(size * 1.3)
            font = _load_font(size=icon_size, weight=weight)
        elif etype == "DATE":
            text = date_str
        elif etype == "JOKE":
            text = joke
        
        # Wrap and draw text
        wrapped = _wrap(draw, text, font, max_w=max(8, w - TEXT_PADDING_X * 2))
        draw.multiline_text(
            (x + TEXT_PADDING_X, y + TEXT_PADDING_Y), 
            wrapped, 
            font=font, 
            fill=color, 
            spacing=TEXT_SPACING
        )
    
    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out.getvalue()

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    # Check font availability
    fonts_found = []
    if FONT_DIR.exists():
        fonts_found = [f.name for f in FONT_DIR.glob("*.ttf")]
    
    return jsonify({
        "status": "ok",
        "version": "eink-optimized-2025-10-26-v2",
        "gcs": True,
        "pexels": bool(PEXELS_API_KEY),
        "openweather": bool(OPENWEATHER_API_KEY),
        "default_device": DEFAULT_DEVICE,
        "default_mode": DEFAULT_MODE,
        "glass_alpha": GLASS_ALPHA,
        "font_dir": str(FONT_DIR),
        "font_dir_exists": FONT_DIR.exists(),
        "fonts_available": fonts_found
    })

# Designer static files
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

# Admin: Pexels prefetch
PEXELS_SEARCH = "https://api.pexels.com/v1/search"

@app.post("/admin/prefetch")
def admin_prefetch():
    tok = request.args.get("token") or request.headers.get("X-Admin-Token")
    if not ADMIN_TOKEN or tok != ADMIN_TOKEN:
        abort(401, "Unauthorized")
    
    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or ["abstract","geometry","nature","minimal","architecture","kids","space","ocean"]
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
            buf = io.BytesIO()
            im.save(buf, "PNG")
            buf.seek(0)
            name = f"images/{week}/{theme}/v_{i}.png"
            if not overwrite and bucket.blob(name).exists():
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
    objs = [b.name for b in storage_client.list_blobs(GCS_BUCKET, prefix=prefix)]
    return jsonify({"week": week, "theme": theme, "count": len(objs), "objects": objs})

# Render single frame
@app.get("/v1/frame")
def v1_frame():
    device = request.args.get("device") or DEFAULT_DEVICE
    theme = request.args.get("theme") or DEFAULT_THEME
    week = request.args.get("week") or _iso_week()
    
    prefix = f"images/{week}/{theme}/"
    blobs = list(storage_client.list_blobs(GCS_BUCKET, prefix=prefix))
    if not blobs:
        return jsonify({"error": f"no cached images for week={week} theme={theme}"}), 404
    
    bg_png = random.choice(blobs).download_as_bytes()
    bg_png = _fit_to_800x480(bg_png)
    
    layout = _load_layout(device)
    png = _render_from_layout(bg_png, layout)
    return send_file(io.BytesIO(png), mimetype="image/png")

# Random batch (returns first image + manifest header)
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
        bg = _fit_to_800x480(bg)
        frames.append(_render_from_layout(bg, layout))
    
    manifest = [b.name for b in picks]
    resp = send_file(io.BytesIO(frames[0]), mimetype="image/png")
    resp.headers["X-Random-Manifest"] = json.dumps(manifest)
    return resp

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Print diagnostic info on startup
    print("=" * 70)
    print("🖼️  Family Display Backend - E-ink Optimized")
    print("=" * 70)
    print(f"Font directory: {FONT_DIR}")
    print(f"Font directory exists: {FONT_DIR.exists()}")
    
    if FONT_DIR.exists():
        fonts = list(FONT_DIR.glob("*.ttf"))
        print(f"Found {len(fonts)} font file(s):")
        for f in fonts:
            print(f"  ✓ {f.name}")
    else:
        print("  ⚠ WARNING: Font directory does not exist!")
        print(f"  Expected location: {FONT_DIR}")
    
    print(f"\nGlass overlay alpha: {GLASS_ALPHA}/255 (transparency for e-ink)")
    print(f"Default device: {DEFAULT_DEVICE}")
    print("=" * 70)
    
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
