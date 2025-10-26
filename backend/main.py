import os, io, json, time, hashlib, random, datetime, pathlib
from datetime import timezone, timedelta

import requests
from flask import Flask, request, jsonify, abort, send_file, send_from_directory
from google.cloud import storage
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -----------------------------------------------------------------------------
# App & Config
# -----------------------------------------------------------------------------
app = Flask(__name__)
VERSION = "pexels-sticker-parade-2025-10-26"

# Environment
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
DEFAULT_LAYOUT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "familydisplay")
DEFAULT_RENDER_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")  # default overlay style

# Canvas size (target display)
IMG_W, IMG_H = 800, 480

# Weekly theme set for Pexels prefetch
WEEKLY_THEME_SET = [
    "abstract backgrounds", "geometric shapes", "colorful gradients",
    "minimal art textures", "bokeh light wallpaper", "paper collage",
    "macro textures", "pastel abstract", "dark gradient background", "modern patterns"
]
PER_THEME_COUNT = int(os.getenv("PER_THEME_COUNT", "8"))

# Fonts (drop TTFs into backend/web/designer/fonts/ for designer; server renderer uses these)
FONT_DIR = os.getenv("FONT_DIR", "./fonts")  # relative to working dir when running locally
FONT_REG = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
FONT_LIGHT = os.path.join(FONT_DIR, "Roboto-Light.ttf")

# Dad joke fallbacks
FALLBACK_JOKES = [
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "I used to be a banker but I lost interest.",
    "I ordered a chicken and an egg from Amazon... I’ll let you know.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I told my computer I needed a break, and it said 'No problem — I’ll go to sleep.'"
]

# -----------------------------------------------------------------------------
# Paths / Storage helpers
# -----------------------------------------------------------------------------
def gcs_bucket():
    return storage.Client().bucket(GCS_BUCKET)

def now_utc():
    return datetime.datetime.now(timezone.utc)

def week_key(dt=None):
    dt = dt or now_utc()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"

# -----------------------------------------------------------------------------
# Serve Designer (same-origin)
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

# (Optional) image proxy to avoid exposing bucket paths publicly
@app.route("/img/<path:obj>", methods=["GET"])
def proxy_image(obj):
    bucket = gcs_bucket()
    blob = bucket.blob(obj)
    if not blob.exists():
        abort(404)
    data = blob.download_as_bytes()
    ctype = "image/jpeg" if obj.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return (data, 200, {"Content-Type": ctype, "Cache-Control": "public, max-age=86400"})

# -----------------------------------------------------------------------------
# Layout Save / Load (versioned)
# -----------------------------------------------------------------------------
def _layout_paths(device_id):
    base = f"layouts/{device_id}"
    return {"current": f"{base}/current.json", "versions_prefix": f"{base}/versions/"}

def _validate_layout(data):
    return isinstance(data, dict) and "elements" in data and isinstance(data["elements"], list)

@app.route("/admin/layouts/<device_id>", methods=["PUT"])
def admin_put_layout(device_id):
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    try:
        payload = request.get_json(force=True)
    except Exception:
        abort(400, "Invalid JSON")

    if not _validate_layout(payload):
        abort(400, "Invalid layout schema")

    now_ts = int(time.time())
    h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
    version = f"{now_ts}-{h}.json"

    bucket = gcs_bucket()
    paths = _layout_paths(device_id)
    # versioned copy
    ver_blob = bucket.blob(paths["versions_prefix"] + version)
    ver_blob.upload_from_string(json.dumps(payload), content_type="application/json")
    # current
    cur_blob = bucket.blob(paths["current"])
    cur_blob.upload_from_string(json.dumps(payload), content_type="application/json")

    return jsonify({"ok": True, "device": device_id, "version": version})

@app.route("/layouts/<device_id>", methods=["GET"])
def get_layout(device_id):
    bucket = gcs_bucket()
    paths = _layout_paths(device_id)
    blob = bucket.blob(paths["current"])
    if not blob.exists():
        # fallback to default device
        if device_id != DEFAULT_LAYOUT_DEVICE:
            defb = bucket.blob(_layout_paths(DEFAULT_LAYOUT_DEVICE)["current"])
            if defb.exists():
                return (defb.download_as_text(), 200, {"Content-Type": "application/json"})
        return jsonify({"elements": []})
    return (blob.download_as_text(), 200, {"Content-Type": "application/json"})

# -----------------------------------------------------------------------------
# Pexels: fetch and store weekly packs
# -----------------------------------------------------------------------------
PEXELS_BASE = "https://api.pexels.com/v1"

def pexels_headers():
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY not set")
    return {"Authorization": PEXELS_API_KEY}

def fetch_theme_images(theme, per=8):
    try:
        r = requests.get(
            f"{PEXELS_BASE}/search",
            headers=pexels_headers(),
            params={"query": theme, "per_page": per, "orientation": "landscape", "size": "large"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("photos", [])
    except Exception:
        pass
    return []

def store_photo_to_gcs(url, path):
    b = gcs_bucket()
    blob = b.blob(path)
    if blob.exists():  # skip if already saved
        return True
    try:
        resp = requests.get(url, timeout=25)
        if resp.status_code == 200:
            blob.upload_from_string(resp.content, content_type="image/jpeg")
            # store tiny meta for attribution if needed
            meta = b.blob(path + ".meta.json")
            meta.upload_from_string(json.dumps({"source": "pexels", "src": url}), content_type="application/json")
            return True
    except Exception:
        pass
    return False

@app.route("/admin/prefetch", methods=["POST"])
def admin_prefetch():
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or WEEKLY_THEME_SET
    per = int(body.get("per_theme_count") or PER_THEME_COUNT)
    wk = week_key()
    out = []
    for t in themes:
        photos = fetch_theme_images(t, per)
        saved = 0
        for i, p in enumerate(photos):
            srcs = p.get("src", {}) or {}
            url = srcs.get("landscape") or srcs.get("large2x") or srcs.get("large")
            if not url:
                continue
            slug = "".join([c for c in t.lower() if c.isalnum() or c in ("-", "_")]).replace(" ", "_")
            dst = f"images/{wk}/{slug}/img_{i}.jpg"
            if store_photo_to_gcs(url, dst):
                saved += 1
        out.append({"theme": t, "saved": saved})
    return jsonify({"ok": True, "week": wk, "themes": out})

# -----------------------------------------------------------------------------
# Cleanup: delete images older than N days (default 14)
# -----------------------------------------------------------------------------
def cleanup_older_than_days(prefix, days=14):
    bucket = gcs_bucket()
    cutoff = now_utc() - timedelta(days=days)
    removed = 0
    for blob in bucket.list_blobs(prefix=prefix):
        try:
            blob.reload()
            upd = blob.updated.replace(tzinfo=timezone.utc)
            if upd < cutoff:
                blob.delete()
                removed += 1
        except Exception:
            pass
    return removed

@app.route("/admin/cleanup", methods=["POST"])
def admin_cleanup():
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        abort(401, "Unauthorized")
    days = int((request.get_json(silent=True) or {}).get("days", 14))
    removed = cleanup_older_than_days("images/", days=days)
    return jsonify({"ok": True, "removed": removed, "days": days})

# -----------------------------------------------------------------------------
# Weather + Dad joke
# -----------------------------------------------------------------------------
def fetch_joke():
    try:
        r = requests.get(
            "https://icanhazdadjoke.com/",
            headers={"Accept": "application/json", "User-Agent": "FamilyDisplay/1.0"},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json().get("joke") or random.choice(FALLBACK_JOKES)
    except Exception:
        pass
    return random.choice(FALLBACK_JOKES)

def fetch_weather(city="Melbourne", country_code=None, units="metric", lat=None, lon=None):
    if not OPENWEATHER_API_KEY:
        return {"city": city, "min": 12, "max": 22, "icon": "🌤️", "note": "Partly cloudy"}
    try:
        if lat and lon:
            q = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": units}
        else:
            q = {"q": f"{city},{country_code}" if country_code else city, "appid": OPENWEATHER_API_KEY, "units": units}
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=q, timeout=10)
        if r.status_code != 200:
            raise Exception("OWM error")
        data = r.json()
        name = data.get("name") or city
        main = data.get("main", {})
        wx = data.get("weather", [{}])[0]
        desc = (wx.get("description") or "Clear").capitalize()
        temp = main.get("temp", 20)
        tmin = int(round(min(main.get("temp_min", temp), temp)))
        tmax = int(round(max(main.get("temp_max", temp), temp)))
        code = (wx.get("icon") or "01d")[:2]
        icon = {"01": "☀️", "02": "🌤️", "03": "⛅", "04": "☁️", "09": "🌧️", "10": "🌦️", "11": "⛈️", "13": "❄️", "50": "🌫️"}.get(code, "☀️")
        return {"city": name, "min": tmin, "max": tmax, "icon": icon, "note": desc}
    except Exception:
        return {"city": city, "min": 12, "max": 22, "icon": "🌤️", "note": "Partly cloudy"}

# -----------------------------------------------------------------------------
# Rendering helpers
# -----------------------------------------------------------------------------
def load_font(size=24, weight="regular"):
    path = FONT_REG
    if weight == "bold" and os.path.exists(FONT_BOLD): path = FONT_BOLD
    elif weight == "light" and os.path.exists(FONT_LIGHT): path = FONT_LIGHT
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()

def draw_text_wrapped(draw, txt, xy, w, font, fill, lh=1.2):
    x, y = xy
    words = (txt or "").split()
    line = ""
    _, fH = draw.textsize("Ay", font=font)
    line_h = int(fH * lh)
    for wd in words:
        test = wd if not line else line + " " + wd
        tw, _ = draw.textsize(test, font=font)
        if tw <= w or not line:
            line = test
        else:
            draw.text((x, y), line, font=font, fill=fill)
            y += line_h
            line = wd
    if line:
        draw.text((x, y), line, font=font, fill=fill)

def render_layout_on_image(img: Image.Image, layout: dict, inject=None) -> Image.Image:
    W, H = img.size
    out = img.convert("RGBA")
    drw = ImageDraw.Draw(out, "RGBA")

    def rr(x, y, w, h, radius=14, fill=(255, 255, 255, 160), outline=(185, 215, 211, 255), width=1, shadow=True):
        if shadow:
            shadow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow_img, "RGBA")
            sd.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(0, 0, 0, 80))
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(6))
            out.alpha_composite(shadow_img)
        drw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=outline, width=width)

    today = now_utc().astimezone().strftime("%A, %d %b")
    inj = {
        "city": "Melbourne",
        "min": 12,
        "max": 22,
        "icon": "🌤️",
        "note": "Partly cloudy",
        "date": today,
        "joke": random.choice(FALLBACK_JOKES),
    }
    if inject:
        inj.update(inject)

    for el in (layout.get("elements") or []):
        kind = el.get("kind", "box")
        x, y = int(el.get("x", 0)), int(el.get("y", 0))
        w, h = int(el.get("w", 150)), int(el.get("h", 50))
        color = el.get("color") or "#000000"

        if "box" in kind:
            rr(x, y, w, h, radius=14, fill=(255, 255, 255, 160), outline=(185, 215, 211, 255), width=1, shadow=True)
        else:
            text = el.get("text") or ""
            low = text.lower()
            # Simple semantic substitutions (designer placeholders -> live content)
            if "city" in low or "°" in low:
                text = f"{inj['city']} • {inj['max']}° / {inj['min']}°"
            if low.strip() in ("☀️","🌤️","⛅","🌧️","❄️","⚡","🌫️","🌙"):
                text = inj["icon"]
            if "sun" in low or "mon" in low or "tue" in low or "wed" in low or "thu" in low or "fri" in low or "sat" in low or "date" in low:
                text = inj["date"]
            if "joke" in low:
                text = inj["joke"]

            is_icon = any(ch in text for ch in ("☀️","🌤️","⛅","🌧️","❄️","⚡","🌫️","🌙","🌈"))
            size = max(14, int(h * (0.75 if not is_icon else 0.95)))
            font = load_font(size=size, weight="bold" if not is_icon else "regular")
            draw_text_wrapped(drw, text, (x + 8, y + 6), w - 16, font, color, lh=1.15)

    return out

# -----------------------------------------------------------------------------
# Load weekly images & preview
# -----------------------------------------------------------------------------
def list_week_images(week=None):
    wk = week or week_key()
    bucket = gcs_bucket()
    prefix = f"images/{wk}/"
    items = []
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.lower().endswith((".jpg", ".jpeg", ".png")):
            items.append(blob.name)
    return sorted(items)

def load_image_from_gcs(path):
    bucket = gcs_bucket()
    blob = bucket.blob(path)
    if not blob.exists():
        return None
    data = blob.download_as_bytes()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    # center-crop to 800x480
    im_ratio = im.width / im.height
    tgt_ratio = IMG_W / IMG_H
    if im_ratio > tgt_ratio:
        new_w = int(im.height * tgt_ratio)
        x0 = (im.width - new_w) // 2
        im = im.crop((x0, 0, x0 + new_w, im.height))
    else:
        new_h = int(im.width / tgt_ratio)
        y0 = (im.height - new_h) // 2
        im = im.crop((0, y0, im.width, y0 + new_h))
    return im.resize((IMG_W, IMG_H), Image.LANCZOS)

@app.route("/preview", methods=["GET"])
def preview():
    device_id = request.args.get("device_id", DEFAULT_LAYOUT_DEVICE)

    # layout
    bucket = gcs_bucket()
    blob = bucket.blob(f"layouts/{device_id}/current.json")
    layout = json.loads(blob.download_as_text()) if blob.exists() else {"elements": []}

    # background
    wk = request.args.get("week") or week_key()
    imgs = list_week_images(wk)
    if imgs:
        idx = random.randint(0, len(imgs) - 1)
        base = load_image_from_gcs(imgs[idx]) or Image.new("RGB", (IMG_W, IMG_H), (40, 40, 40))
    else:
        base = Image.new("RGB", (IMG_W, IMG_H), (40, 40, 40))

    # live data
    city = request.args.get("city", "Melbourne")
    lat = request.args.get("lat"); lon = request.args.get("lon")
    wx = fetch_weather(city=city, lat=lat, lon=lon)
    joke = fetch_joke()
    inject = {
        "city": wx["city"], "min": wx["min"], "max": wx["max"],
        "icon": wx["icon"], "note": wx["note"],
        "date": now_utc().astimezone().strftime("%A, %d %b"),
        "joke": joke,
    }

    composed = render_layout_on_image(base, layout, inject=inject)
    bio = io.BytesIO(); composed.save(bio, format="PNG"); bio.seek(0)
    return send_file(bio, mimetype="image/png")

# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.route("/")
def root():
    ok_gcs = True
    try: _ = gcs_bucket()
    except Exception: ok_gcs = False
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "gcs": ok_gcs,
        "default_device": DEFAULT_LAYOUT_DEVICE,
        "default_mode": DEFAULT_RENDER_MODE,
        "pexels": bool(PEXELS_API_KEY),
        "openweather": bool(OPENWEATHER_API_KEY),
    })

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # local dev
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)