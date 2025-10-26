import os
import io
import json
import random
import datetime
import requests
import pathlib
from flask import Flask, send_file, send_from_directory, jsonify, request
from PIL import Image, ImageDraw, ImageFont
from google.cloud import storage

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
app = Flask(__name__)

GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
DEFAULT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "familydisplay")
DEFAULT_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")
FONT_DIR = os.getenv("FONT_DIR", "./backend/web/designer/fonts")
DEFAULT_THEME = "abstract"

storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET)

# -----------------------------------------------------------------------------
# FONT LOADING
# -----------------------------------------------------------------------------
def _load_font(size: int, weight: str = "400") -> ImageFont.FreeTypeFont:
    """Load Roboto or fallback to DejaVu."""
    try:
        if FONT_DIR and os.path.isdir(FONT_DIR):
            path = None
            if weight >= "700" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Bold.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
            elif weight <= "300" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Light.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Light.ttf")
            elif os.path.exists(os.path.join(FONT_DIR, "Roboto-Regular.ttf")):
                path = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
            if path:
                return ImageFont.truetype(path, size=size)
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()

# -----------------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------------
def _current_week():
    today = datetime.date.today()
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"

def _is_dark_background(png_bytes: bytes) -> bool:
    """Estimate brightness to choose text color."""
    im = Image.open(io.BytesIO(png_bytes)).convert("L").resize((50, 30))
    return sum(im.getdata()) / (50 * 30) < 110

def _get_weather(city="Darwin"):
    """Fetch weather for overlays."""
    if not OPENWEATHER_API_KEY:
        return {
            "city": city,
            "temp": 30,
            "min": 30,
            "max": 30,
            "desc": "Sunny",
            "icon": "☀️",
        }
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        r = requests.get(url, timeout=5)
        j = r.json()
        return {
            "city": city,
            "temp": int(j["main"]["temp"]),
            "min": int(j["main"]["temp_min"]),
            "max": int(j["main"]["temp_max"]),
            "desc": j["weather"][0]["description"].title(),
            "icon": "☀️" if "clear" in j["weather"][0]["main"].lower() else "⛅",
        }
    except Exception:
        return {
            "city": city,
            "temp": 30,
            "min": 30,
            "max": 30,
            "desc": "Sunny",
            "icon": "☀️",
        }

def _get_dad_joke():
    """Retrieve dad joke."""
    try:
        r = requests.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"}, timeout=5)
        j = r.json()
        return j.get("joke", "")
    except Exception:
        fallbacks = [
            "I'm reading a book on anti-gravity. It's impossible to put down.",
            "Why do pirates not know the alphabet? They always get stuck at 'C'.",
            "I used to play piano by ear... now I use my hands.",
            "Why can't you trust atoms? They make up everything!",
        ]
        return random.choice(fallbacks)

# -----------------------------------------------------------------------------
# RENDERING
# -----------------------------------------------------------------------------
def _render_overlay(bg_png: bytes, weather: dict, joke: str, date: str) -> bytes:
    im = Image.open(io.BytesIO(bg_png)).convert("RGBA")
    draw = ImageDraw.Draw(im)
    dark_bg = _is_dark_background(bg_png)

    # Color based on background
    color = "#FFFFFF" if dark_bg else "#000000"
    f_title = _load_font(38, "700")
    f_body = _load_font(24, "400")

    # Layout (Sticker Parade)
    W, H = im.size
    pad = 20

    # Date
    tw, th = draw.textsize(date, font=f_body)
    draw.rounded_rectangle([W - tw - 60, pad, W - 20, pad + th + 16], radius=10, fill=(255,255,255,180))
    draw.text((W - tw - 50, pad + 8), date, font=f_body, fill=color)

    # Weather card
    box_y = H - 140
    draw.rounded_rectangle([pad, box_y, W//2 - 10, H - pad], radius=14, fill=(255,255,255,180))
    draw.text((pad + 20, box_y + 18), f"{weather['city']}", font=f_title, fill=color)
    draw.text((pad + 20, box_y + 66), f"{weather['min']}° / {weather['max']}°", font=f_body, fill=color)
    draw.text((pad + 220, box_y + 24), weather["icon"], font=f_title, fill=color)

    # Dad joke card
    joke_x = W//2 + 10
    draw.rounded_rectangle([joke_x, box_y, W - pad, H - pad], radius=14, fill=(255,255,255,180))
    draw.text((joke_x + 20, box_y + 28), joke, font=f_body, fill=color)

    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out.getvalue()

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "version": "pexels-fonts-contrast-random-2025-10-26",
        "gcs": bool(GCS_BUCKET),
        "pexels": bool(PEXELS_API_KEY),
        "openweather": bool(OPENWEATHER_API_KEY),
        "default_device": DEFAULT_DEVICE,
        "default_mode": DEFAULT_MODE
    })

@app.route("/v1/frame")
def v1_frame():
    theme = request.args.get("theme") or DEFAULT_THEME
    week = _current_week()

    prefix = f"images/{week}/{theme}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    if not blobs:
        return jsonify({"error": f"No images found for theme {theme}"}), 404

    blob = random.choice(blobs)
    bg_png = blob.download_as_bytes()
    weather = _get_weather("Darwin")
    joke = _get_dad_joke()
    date = datetime.date.today().strftime("%a, %d %b")
    frame = _render_overlay(bg_png, weather, joke, date)
    return send_file(io.BytesIO(frame), mimetype="image/png")

@app.route("/v1/random")
def v1_random():
    """Return 4 random rendered frames (random theme if not specified)."""
    week = request.args.get("week") or _current_week()
    theme = request.args.get("theme")
    mode = request.args.get("mode") or DEFAULT_MODE
    base = f"images/{week}/"

    # auto-pick a random theme if not specified
    if not theme:
        blobs = list(bucket.list_blobs(prefix=base))
        themes = sorted({b.name.split("/")[2] for b in blobs if len(b.name.split("/")) > 2})
        theme = random.choice(themes) if themes else DEFAULT_THEME

    prefix = f"{base}{theme}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    if not blobs:
        return jsonify({"error": f"No images found for theme {theme}"}), 404

    chosen = random.sample(blobs, min(4, len(blobs)))
    results = []
    for blob in chosen:
        bg_png = blob.download_as_bytes()
        weather = _get_weather("Darwin")
        joke = _get_dad_joke()
        date = datetime.date.today().strftime("%a, %d %b")
        frame = _render_overlay(bg_png, weather, joke, date)
        results.append(frame)

    manifest = [b.name for b in chosen]
    headers = {"X-Random-Manifest": json.dumps(manifest)}
    return send_file(io.BytesIO(results[0]), mimetype="image/png", headers=headers)

# -----------------------------------------------------------------------------
# DESIGNER + STATIC ROUTES
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
