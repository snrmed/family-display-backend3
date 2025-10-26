# backend/main.py
import os, io, json, time, random, datetime, pathlib
from typing import List, Optional

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory, abort, redirect
from google.cloud import storage
from PIL import Image, ImageDraw, ImageFont

# -----------------------------------------------------------------------------
# App / Env
# -----------------------------------------------------------------------------
app = Flask(__name__)

PROJECT_VERSION = os.getenv("PROJECT_VERSION", time.strftime("%Y-%m-%d"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

DEFAULT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "familydisplay")
DEFAULT_RENDER_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")
DEFAULT_THEME = "abstract"
PER_THEME_COUNT = int(os.getenv("PER_THEME_COUNT", "8") or 8)
FONT_DIR = os.getenv("FONT_DIR", "")  # e.g. ./backend/web/designer/fonts

# GCS
_gcs = storage.Client()
_bucket = _gcs.bucket(GCS_BUCKET)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _iso_week() -> str:
    today = datetime.date.today()
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"

def _blob_text(name: str) -> Optional[str]:
    b = _bucket.blob(name)
    try:
        if not b.exists():  # type: ignore
            return None
    except Exception:
        return None
    return b.download_as_text()

def _put_json(name: str, data: dict, public: bool = False):
    b = _bucket.blob(name)
    b.cache_control = "no-cache"
    b.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    if public:
        b.make_public()

def _put_png(name: str, png: bytes, public: bool = False):
    b = _bucket.blob(name)
    b.cache_control = "public, max-age=3600"
    b.upload_from_string(png, content_type="image/png")
    if public:
        b.make_public()

def _download_and_fit(url: str, size=(800, 480)) -> Image.Image:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    tw, th = size
    ratio = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * ratio), int(im.height * ratio)
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))

def _load_font(size: int, weight: str = "400") -> ImageFont.FreeTypeFont:
    path = None
    if FONT_DIR and os.path.isdir(FONT_DIR):
        if weight >= "700" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Bold.ttf")):
            path = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
        elif weight <= "300" and os.path.exists(os.path.join(FONT_DIR, "Roboto-Light.ttf")):
            path = os.path.join(FONT_DIR, "Roboto-Light.ttf")
        elif os.path.exists(os.path.join(FONT_DIR, "Roboto-Regular.ttf")):
            path = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)

def _draw_glass(draw: ImageDraw.ImageDraw, xy, radius=14, fill=(255,255,255,160), outline=(185,215,211,255), width=1):
    x, y, w, h = xy
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=outline, width=width)

def _get_weather_note(city="Darwin", country="AU"):
    if not OPENWEATHER_API_KEY:
        return {"city": city, "temp": 28, "min": 22, "max": 33, "desc": "Few clouds", "icon": "⛅"}
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"q": f"{city},{country}", "appid": OPENWEATHER_API_KEY, "units": "metric"},
                         timeout=10)
        j = r.json()
        main = j.get("main", {})
        weather = (j.get("weather") or [{}])[0]
        temp = int(round(main.get("temp", 28)))
        mn = int(round(main.get("temp_min", temp)))
        mx = int(round(main.get("temp_max", temp)))
        desc = weather.get("description", "—").title()
        code = (weather.get("icon") or "02d")
        icon = "☀️" if code.startswith("01") else "⛅" if code.startswith("02") else "☁️" if code.startswith("03") else "🌧️"
        name = j.get("name") or city
        return {"city": name, "temp": temp, "min": mn, "max": mx, "desc": desc, "icon": icon}
    except Exception:
        return {"city": city, "temp": 28, "min": 22, "max": 33, "desc": "Few clouds", "icon": "⛅"}

def _dad_joke():
    fallbacks = [
        "What do you call a fake noodle? An impasta.",
        "I used to play piano by ear… now I use my hands.",
        "Why did the scarecrow win an award? He was outstanding in his field.",
        "I’m reading a book on anti-gravity. It’s impossible to put down."
    ]
    try:
        r = requests.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"}, timeout=8)
        if r.status_code == 200:
            return r.json().get("joke") or random.choice(fallbacks)
    except Exception:
        pass
    return random.choice(fallbacks)

def _layout_paths(device: str):
    base = f"layouts/{device}"
    return {"current": f"{base}/current.json",
            "versions": f"{base}/versions/{int(time.time())}.json"}

def _choose_cached_image(week: Optional[str], theme: Optional[str]) -> Optional[bytes]:
    w = week or _iso_week()
    t = theme or DEFAULT_THEME
    prefix = f"images/{w}/{t}/"
    blobs = list(_gcs.list_blobs(GCS_BUCKET, prefix=prefix))
    if not blobs:
        return None
    return random.choice(blobs).download_as_bytes()

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/")
def index():
    return jsonify({
        "status": "ok",
        "version": f"pexels-sticker-parade-{PROJECT_VERSION}",
        "gcs": True,
        "openweather": bool(OPENWEATHER_API_KEY),
        "pexels": bool(PEXELS_API_KEY),
        "default_device": DEFAULT_DEVICE,
        "default_mode": DEFAULT_RENDER_MODE
    })

# -----------------------------------------------------------------------------
# Designer static (same-origin)
# -----------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
DESIGNER_DIR = BASE_DIR / "web" / "designer"

@app.route("/designer/")
def designer_root():
    # Change filename if you use another name
    return send_from_directory(DESIGNER_DIR, "overlay_designer_v3_full.html")

@app.route("/designer/<path:fname>")
def designer_static(fname: str):
    return send_from_directory(DESIGNER_DIR, fname)

# -----------------------------------------------------------------------------
# Layouts (GCS)
# -----------------------------------------------------------------------------
@app.get("/layouts/<device>")
def get_layout(device: str):
    cur = _layout_paths(device)["current"]
    s = _blob_text(cur)
    if s:
        try:
            return jsonify(json.loads(s))
        except Exception:
            pass
    # minimal default (works with preview)
    return jsonify({
        "device": device,
        "mode": DEFAULT_RENDER_MODE,
        "elements": [
            {"kind": "box",  "x": 16, "y": 360, "w": 360, "h": 96, "role":"CARD_WEATHER"},
            {"kind": "box",  "x": 400,"y": 360, "w": 384, "h": 96, "role":"CARD_JOKE"},
            {"kind": "box",  "x": 620,"y": 16,  "w": 164, "h": 48, "role":"CARD_GENERIC"},
            {"kind": "text", "x": 28, "y": 372, "w": 320, "h": 28, "text":"City","type":"WEATHER_CITY","color":"#000000"},
            {"kind": "text", "x": 28, "y": 404, "w": 320, "h": 22, "text":"21° / 12°","type":"WEATHER_MINMAX","color":"#000000"},
            {"kind": "icon", "x": 320,"y": 372, "w": 28,  "h": 28,  "text":"⛅","type":"WEATHER_ICON","color":"#000000"},
            {"kind": "text", "x": 412,"y": 372, "w": 360, "h": 70, "text":"Dad joke...","type":"JOKE","color":"#000000"},
            {"kind": "text", "x": 632,"y": 28,  "w": 140, "h": 28, "text":"Sat, 25 Oct","type":"DATE","color":"#000000"}
        ]
    })

@app.put("/admin/layouts/<device>")
def put_layout(device: str):
    tok = request.args.get("token") or request.headers.get("X-Admin-Token")
    if ADMIN_TOKEN and tok != ADMIN_TOKEN:
        abort(401, "Unauthorized")
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400
    paths = _layout_paths(device)
    _put_json(paths["current"], data, public=False)
    _put_json(paths["versions"], data, public=False)
    return jsonify({"status": "saved", "device": device, "version": paths["versions"].split("/")[-1].split(".")[0]})

# -----------------------------------------------------------------------------
# Pexels prefetch
# -----------------------------------------------------------------------------
_PEXELS_SEARCH = "https://api.pexels.com/v1/search"

@app.post("/admin/prefetch")
def admin_prefetch():
    tok = request.args.get("token") or request.headers.get("X-Admin-Token")
    if ADMIN_TOKEN and tok != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    payload = request.get_json(silent=True) or {}
    themes = payload.get("themes") or ["nature","geometry","minimal","ocean","architecture","kids","abstract","space"]
    if isinstance(themes, str):
        themes = [t.strip() for t in themes.split(",") if t.strip()]
    per_theme = int(payload.get("per_theme", payload.get("count", PER_THEME_COUNT)))
    overwrite = bool(payload.get("overwrite", False))
    week = payload.get("week") or _iso_week()

    if not PEXELS_API_KEY:
        return jsonify({"error": "PEXELS_API_KEY missing"}), 500

    headers = {"Authorization": PEXELS_API_KEY}
    saved = []
    for theme in themes:
        params = {"query": theme, "per_page": max(8, per_theme), "orientation": "landscape", "size": "large"}
        res = requests.get(_PEXELS_SEARCH, headers=headers, params=params, timeout=30)
        if res.status_code != 200:
            continue
        photos = (res.json().get("photos") or [])[:per_theme]
        i = 0
        for p in photos:
            src = p.get("src", {})
            url = src.get("large2x") or src.get("large") or src.get("original")
            if not url:
                continue
            im = _download_and_fit(url, size=(800, 480))
            out = io.BytesIO()
            im.save(out, format="PNG", optimize=True)
            out.seek(0)
            name = f"images/{week}/{theme}/v_{i}.png"
            if not overwrite and _bucket.blob(name).exists():  # type: ignore
                i += 1
                continue
            _put_png(name, out.getvalue(), public=False)
            saved.append(name)
            i += 1

    return jsonify({"status": "done", "week": week, "themes": themes, "saved": len(saved)})

# -----------------------------------------------------------------------------
# List cached images
# -----------------------------------------------------------------------------
@app.get("/v1/list")
def v1_list():
    week = request.args.get("week") or _iso_week()
    theme = request.args.get("theme")
    limit = int(request.args.get("limit", "500"))
    prefix = f"images/{week}/"
    if theme:
        prefix += f"{theme.strip().rstrip('/')}/"
    blobs = _gcs.list_blobs(GCS_BUCKET, prefix=prefix)
    out = []
    for i, b in enumerate(blobs):
        if i >= limit:
            break
        out.append(b.name)
    return jsonify({"week": week, "theme": theme, "count": len(out), "objects": out})

# -----------------------------------------------------------------------------
# Frame rendering
# -----------------------------------------------------------------------------
def _render_frame(bg_png: bytes, layout: dict) -> bytes:
    im = Image.open(io.BytesIO(bg_png)).convert("RGB")
    draw = ImageDraw.Draw(im, "RGBA")

    weather = _get_weather_note()
    joke = _dad_joke()
    now = datetime.datetime.now()
    date_str = now.strftime("%a, %d %b")

    for el in layout.get("elements", []):
        kind = el.get("kind", "box")
        x = int(el.get("x", 0)); y = int(el.get("y", 0))
        w = int(el.get("w", 100)); h = int(el.get("h", 50))
        color = el.get("color", "#000000")
        etype = el.get("type")
        text = el.get("text", "")

        if kind == "box":
            _draw_glass(draw, (x, y, w, h))
        else:
            # dynamic substitutions
            if etype == "WEATHER_CITY":
                text = weather["city"]
            elif etype == "WEATHER_MINMAX":
                text = f'{weather["min"]}° / {weather["max"]}°'
            elif etype == "WEATHER_NOTE":
                text = weather["desc"]
            elif etype == "WEATHER_ICON":
                text = weather["icon"]
            elif etype == "DATE":
                text = date_str
            elif etype == "JOKE":
                text = joke

            size = max(14, int(h * 0.65))
            weight = "700" if "bold" in (el.get("weight","").lower()) else "400"
            font = _load_font(size=size, weight=weight)
            wrapped = _wrap_text(draw, text, font, max_w=w - 12)
            draw.multiline_text((x + 8, y + 6), wrapped, font=font, fill=color, spacing=4)

    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.getvalue()

@app.get("/v1/frame")
def v1_frame():
    device = request.args.get("device") or DEFAULT_DEVICE
    week = request.args.get("week")
    theme = request.args.get("theme")
    # layout
    jl = _blob_text(_layout_paths(device)["current"])
    layout = json.loads(jl) if jl else get_layout(device).json
    # pick background
    bg = _choose_cached_image(week, theme)
    if not bg:
        # fallback simple gradient
        im = Image.new("RGB", (800, 480), (45, 60, 95))
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        bg = buf.getvalue()
    png = _render_frame(bg, layout)
    return send_file(io.BytesIO(png), mimetype="image/png")

# -----------------------------------------------------------------------------
# Random (auto theme if none) — returns first PNG + manifest header
# -----------------------------------------------------------------------------
@app.get("/v1/random")
def v1_random():
    week = request.args.get("week") or _iso_week()
    theme = request.args.get("theme")
    mode = request.args.get("mode") or DEFAULT_RENDER_MODE
    device = request.args.get("device") or DEFAULT_DEVICE

    # layout once
    jl = _blob_text(_layout_paths(device)["current"])
    layout = json.loads(jl) if jl else get_layout(device).json

    # If no theme: pick one from existing folders
    if not theme:
        base_prefix = f"images/{week}/"
        all_blobs = list(_gcs.list_blobs(GCS_BUCKET, prefix=base_prefix))
        if all_blobs:
            themes = sorted({b.name.split("/")[2] for b in all_blobs if len(b.name.split("/")) > 2})
            theme = random.choice(themes) if themes else DEFAULT_THEME
        else:
            theme = DEFAULT_THEME

    prefix = f"images/{week}/{theme}/"
    blobs = list(_gcs.list_blobs(GCS_BUCKET, prefix=prefix))
    if not blobs:
        return jsonify({"error": f"No cached images found for week={week}, theme={theme}"}), 404

    picks = random.sample(blobs, min(4, len(blobs)))
    images = []
    for b in picks:
        bg = b.download_as_bytes()
        try:
            png = _render_frame(bg, layout)
        except Exception:
            png = bg
        images.append(png)

    # Return first PNG, include manifest of all 4 in header
    from io import BytesIO
    manifest = [b.name for b in picks]
    headers = {"X-Random-Manifest": json.dumps(manifest)}
    return send_file(BytesIO(images[0]), mimetype="image/png", headers=headers)

# -----------------------------------------------------------------------------
# Errors
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Run local
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
