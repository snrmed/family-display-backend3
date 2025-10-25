# main.py
import os, io, json, time, hashlib, random, datetime
from datetime import timezone, timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, abort, send_file
from google.cloud import storage
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -----------------------------------------------------------------------------
# Config / Env
# -----------------------------------------------------------------------------
VERSION = "pexels-layouts-sticker-parade-2025-10-26"

GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # required for /admin/prefetch
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # optional for weather
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # required for PUT /admin/layouts/<id>

# Default behavior
DEFAULT_LAYOUT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "default")
DEFAULT_RENDER_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")  # <- your requested default
WEEKLY_THEME_SET = [
    # Ten themes — safe searches that tend to look great on displays
    "abstract backgrounds",
    "geometric shapes",
    "colorful gradients",
    "minimal art textures",
    "bokeh light wallpaper",
    "paper collage",
    "macro textures",
    "pastel abstract",
    "dark gradient background",
    "modern patterns"
]
PER_THEME_COUNT = int(os.getenv("PER_THEME_COUNT", "8"))  # images per theme
IMG_W, IMG_H = 800, 480

# Local fonts (drop your TTFs into a /fonts dir next to this file)
FONT_DIR = os.getenv("FONT_DIR", "./fonts")
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
# App & GCS
# -----------------------------------------------------------------------------
app = Flask(__name__)

def gcs_bucket():
    return storage.Client().bucket(GCS_BUCKET)

def now_utc():
    return datetime.datetime.now(timezone.utc)

def week_key(dt=None):
    dt = dt or now_utc()
    # ISO week is fine but we want stability → use Monday-based week
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"

# -----------------------------------------------------------------------------
# Layouts (Save / Load)
# -----------------------------------------------------------------------------
def _layout_paths(device_id):
    base = f"layouts/{device_id}"
    return {"current": f"{base}/current.json", "versions_prefix": f"{base}/versions/"}

def _validate_layout(data):
    if not isinstance(data, dict): return False
    if "elements" not in data or not isinstance(data["elements"], list): return False
    # Optional: further validation of each element
    return True

@app.route("/admin/layouts/<device_id>", methods=["PUT"])
def admin_put_layout(device_id):
    # Simple shared-secret auth
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        abort(400, "Invalid JSON")

    if not _validate_layout(payload):
        abort(400, "Invalid layout schema")

    now_ts = int(time.time())
    h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    version_name = f"{now_ts}-{h}.json"

    bucket = gcs_bucket()
    paths = _layout_paths(device_id)

    # write versioned copy
    ver_blob = bucket.blob(paths["versions_prefix"] + version_name)
    ver_blob.cache_control = "no-store"
    ver_blob.upload_from_string(json.dumps(payload, separators=(",", ":")), content_type="application/json")

    # update current
    cur_blob = bucket.blob(paths["current"])
    cur_blob.cache_control = "no-store"
    cur_blob.upload_from_string(json.dumps(payload, separators=(",", ":")), content_type="application/json")

    return jsonify({"ok": True, "device": device_id, "version": version_name, "path_current": paths["current"]})

@app.route("/layouts/<device_id>", methods=["GET"])
def get_layout(device_id):
    bucket = gcs_bucket()
    paths = _layout_paths(device_id)
    blob = bucket.blob(paths["current"])
    if not blob.exists():
        # Try default device layout
        if device_id != DEFAULT_LAYOUT_DEVICE:
            default_blob = bucket.blob(_layout_paths(DEFAULT_LAYOUT_DEVICE)["current"])
            if default_blob.exists():
                default_blob.reload()
                etag = default_blob.etag
                inm = request.headers.get("If-None-Match")
                if inm and inm == etag:
                    return ("", 304, {"ETag": etag, "Cache-Control": "no-cache, must-revalidate"})
                data = default_blob.download_as_text()
                return (data, 200, {"Content-Type": "application/json", "Cache-Control": "no-cache, must-revalidate", "ETag": etag})
        # otherwise empty
        return jsonify({"elements": []})

    blob.reload()
    etag = blob.etag
    inm = request.headers.get("If-None-Match")
    if inm and inm == etag:
        return ("", 304, {"ETag": etag, "Cache-Control": "no-cache, must-revalidate"})

    data = blob.download_as_text()
    return (data, 200, {"Content-Type": "application/json", "Cache-Control": "no-cache, must-revalidate", "ETag": etag})

# -----------------------------------------------------------------------------
# Pexels: fetch curated / search per theme, store in GCS weekly
# -----------------------------------------------------------------------------
PEXELS_BASE = "https://api.pexels.com/v1"

def pexels_headers():
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY not set")
    return {"Authorization": PEXELS_API_KEY}

def fetch_theme_images(theme, per_page=8):
    # try search; fallback to curated
    try:
        q = {"query": theme, "per_page": per_page, "orientation": "landscape", "size": "large"}
        r = requests.get(f"{PEXELS_BASE}/search", headers=pexels_headers(), params=q, timeout=20)
        if r.status_code == 200:
            data = r.json()
            photos = data.get("photos", [])
            if photos:
                return photos
    except Exception:
        pass

    # fallback curated
    try:
        r = requests.get(f"{PEXELS_BASE}/curated", headers=pexels_headers(), params={"per_page": per_page}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            photos = data.get("photos", [])
            return photos
    except Exception:
        pass

    return []

def store_photo_to_gcs(url, dst_path):
    bucket = gcs_bucket()
    blob = bucket.blob(dst_path)
    if blob.exists():
        return True
    try:
        rr = requests.get(url, timeout=30)
        if rr.status_code == 200:
            blob.upload_from_string(rr.content, content_type="image/jpeg")
            # bake minimal attribution JSON next to it
            meta_blob = bucket.blob(dst_path + ".meta.json")
            meta_blob.upload_from_string(json.dumps({"source": "pexels", "src": url}), content_type="application/json")
            return True
    except Exception:
        return False
    return False

@app.route("/admin/prefetch", methods=["POST"])
def admin_prefetch():
    # Auth
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        abort(401, "Unauthorized")

    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or WEEKLY_THEME_SET
    per = int(body.get("per_theme_count") or PER_THEME_COUNT)

    wk = week_key()
    out = {"week": wk, "themes": []}

    for theme in themes:
        photos = fetch_theme_images(theme, per_page=per)
        saved = 0
        items = []
        for i, ph in enumerate(photos):
            # prefer src.large2x or src.landscape
            src = ph.get("src", {}) or {}
            url = src.get("landscape") or src.get("large2x") or src.get("large") or ph.get("url")
            if not url:
                continue
            # path: images/<week>/<theme_slug>/img_<i>.jpg
            theme_slug = "".join([c for c in theme.lower() if c.isalnum() or c in ("-", "_")]).replace(" ", "_")
            dst = f"images/{wk}/{theme_slug}/img_{i}.jpg"
            ok = store_photo_to_gcs(url, dst)
            if ok:
                saved += 1
                items.append(dst)
        out["themes"].append({"theme": theme, "saved": saved, "objects": items})
    return jsonify(out)

# -----------------------------------------------------------------------------
# Cleanup: delete images older than N days (2 weeks default)
# -----------------------------------------------------------------------------
def cleanup_older_than_days(prefix, days=14):
    bucket = gcs_bucket()
    cutoff = now_utc() - timedelta(days=days)
    # Expect week folders: images/<YYYY-Www>/...
    removed = 0
    for blob in bucket.list_blobs(prefix=prefix):
        # try parse from name (week), fallback updated/created time
        parts = blob.name.split("/")
        if len(parts) >= 3:
            wk = parts[1]  # YYYY-Www
            try:
                year = int(wk.split("-W")[0])
                week = int(wk.split("-W")[1])
                # Monday of that week
                # ISO week: get Monday by building date from year-week-1 and adjusting
                monday = datetime.date.fromisocalendar(year, week, 1)
                week_dt = datetime.datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
                if week_dt < cutoff:
                    blob.delete()
                    removed += 1
                    continue
            except Exception:
                pass
        # fallback to time-based
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
# Data: Weather, Dad joke
# -----------------------------------------------------------------------------
def fetch_joke():
    try:
        r = requests.get("https://icanhazdadjoke.com/", headers={
            "Accept": "application/json",
            "User-Agent": "FamilyDisplay/1.0"
        }, timeout=8)
        if r.status_code == 200:
            return r.json().get("joke") or random.choice(FALLBACK_JOKES)
    except Exception:
        pass
    return random.choice(FALLBACK_JOKES)

def fetch_weather(city="Melbourne", country_code=None, units="metric", lat=None, lon=None):
    if not OPENWEATHER_API_KEY:
        return {"city": city, "min": 12, "max": 21, "icon": "🌤️", "note": "Partly cloudy"}
    try:
        if lat and lon:
            q = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": units}
        else:
            q = {"q": f"{city},{country_code}" if country_code else city, "appid": OPENWEATHER_API_KEY, "units": units}
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=q, timeout=10)
        if r.status_code != 200:
            return {"city": city, "min": 12, "max": 21, "icon": "🌤️", "note": "Partly cloudy"}
        data = r.json()
        name = data.get("name") or city
        main = data.get("main", {})
        wx = data.get("weather", [{}])[0]
        desc = wx.get("description", "Clear").capitalize()
        # OWM returns only 'temp' current; derive min/max as +/- (rough)
        temp = main.get("temp", 20)
        tmin = int(round(min(main.get("temp_min", temp), temp)))
        tmax = int(round(max(main.get("temp_max", temp), temp)))
        # icon map (simple)
        code = (wx.get("icon") or "01d")[:2]
        icon = {"01": "☀️", "02": "🌤️", "03": "⛅", "04": "☁️", "09": "🌧️", "10": "🌦️", "11": "⛈️", "13": "❄️", "50": "🌫️"}.get(code, "☀️")
        return {"city": name, "min": tmin, "max": tmax, "icon": icon, "note": desc}
    except Exception:
        return {"city": city, "min": 12, "max": 21, "icon": "🌤️", "note": "Partly cloudy"}

# -----------------------------------------------------------------------------
# Render overlay (server-side), mode: 'sticker_parade' default
# -----------------------------------------------------------------------------
def load_font(size=24, weight="regular"):
    path = FONT_REG
    if weight == "bold": path = FONT_BOLD if os.path.exists(FONT_BOLD) else FONT_REG
    if weight == "light": path = FONT_LIGHT if os.path.exists(FONT_LIGHT) else FONT_REG
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()

def draw_text_wrapped(draw, txt, xy, w, font, fill, lh=1.2):
    # naive wrap
    x, y = xy
    words = (txt or "").split()
    line = ""
    _, fH = draw.textsize("Ay", font=font)
    line_h = int(fH * lh)
    for i, wd in enumerate(words):
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

def render_layout_on_image(img: Image.Image, layout: dict, mode="sticker_parade", inject=None) -> Image.Image:
    """
    mode 'sticker_parade': draw frosted boxes and put text/icons in them.
    inject: dict with {city, min, max, icon, note, date, joke}
    """
    W, H = img.size
    out = img.convert("RGBA")
    drw = ImageDraw.Draw(out, "RGBA")

    # Helpers
    def rr(x, y, w, h, radius=14, fill=(255,255,255,160), outline=(185,215,211,255), width=1, shadow=True):
        # shadow
        if shadow:
            shadow_img = Image.new("RGBA", (W, H), (0,0,0,0))
            sd = ImageDraw.Draw(shadow_img, "RGBA")
            sd.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=(0,0,0,80))
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(6))
            out.alpha_composite(shadow_img)
        drw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=fill, outline=outline, width=width)

    # Inject defaults
    today = now_utc().astimezone().strftime("%A, %d %b")
    inj = {
        "city": "Melbourne",
        "min": 12,
        "max": 21,
        "icon": "🌤️",
        "note": "Partly cloudy",
        "date": today,
        "joke": random.choice(FALLBACK_JOKES)
    }
    if inject:
        inj.update(inject)

    # Draw
    for el in (layout.get("elements") or []):
        kind = el.get("kind", "box")
        x, y = int(el.get("x", 0)), int(el.get("y", 0))
        w, h = int(el.get("w", 150)), int(el.get("h", 50))
        color = el.get("color") or "#000000"
        if "box" in kind:
            rr(x, y, w, h, radius=14, fill=(255,255,255,160), outline=(185,215,211,255), width=1, shadow=True)
        else:
            # text/icon
            text = el.get("text") or ""
            # semantic injection by rough matching
            lower = text.lower()
            if "darwin" in lower or "melbourne" in lower or "•" in lower or "°" in lower:
                text = f"{inj['city']} • {inj['max']}° / {inj['min']}°"
            if lower.strip() in ("☀️","🌤️","⛅","🌧️","❄️","⚡","🌫️","🌙"):
                text = inj["icon"]
            if "sunday" in lower or "monday" in lower or "tuesday" in lower or "date" in lower:
                text = inj["date"]
            if "i used to" in lower or "..." in lower or "hands" in lower or "dad" in lower or "joke" in lower:
                text = inj["joke"]

            # font sizing: approximate from element height
            # for icons, make it bigger
            is_icon = any(ch in text for ch in ("☀️","🌤️","⛅","🌧️","❄️","⚡","🌫️","🌙","🌈"))
            size = max(14, int(h * (0.75 if not is_icon else 0.95)))
            f = load_font(size=size, weight="bold" if not is_icon else "regular")
            # wrap
            draw_text_wrapped(drw, text, (x+8, y+6), w-16, f, color, lh=1.15)

    return out

# -----------------------------------------------------------------------------
# Image selection from GCS
# -----------------------------------------------------------------------------
def list_week_images(week=None):
    wk = week or week_key()
    bucket = gcs_bucket()
    prefix = f"images/{wk}/"
    items = []
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.lower().endswith(".jpg") or blob.name.lower().endswith(".jpeg") or blob.name.lower().endswith(".png"):
            items.append(blob.name)
    return sorted(items)

def load_image_from_gcs(path):
    bucket = gcs_bucket()
    blob = bucket.blob(path)
    if not blob.exists():
        return None
    data = blob.download_as_bytes()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    # fit center-crop to 800x480
    im_ratio = im.width / im.height
    tgt_ratio = IMG_W / IMG_H
    if im_ratio > tgt_ratio:
        # too wide → crop sides
        new_w = int(im.height * tgt_ratio)
        x0 = (im.width - new_w)//2
        im = im.crop((x0, 0, x0+new_w, im.height))
    else:
        # too tall → crop top/bottom
        new_h = int(im.width / tgt_ratio)
        y0 = (im.height - new_h)//2
        im = im.crop((0, y0, im.width, y0+new_h))
    im = im.resize((IMG_W, IMG_H), Image.LANCZOS)
    return im

# -----------------------------------------------------------------------------
# Routes: status, preview render
# -----------------------------------------------------------------------------
@app.route("/")
def root():
    # quick status
    # also indicate default render mode
    # and if GCS reachable
    try:
        _ = gcs_bucket()
        gcs_ok = True
    except Exception:
        gcs_ok = False

    return jsonify({
        "status": "ok",
        "version": VERSION,
        "gcs": gcs_ok,
        "default_mode": DEFAULT_RENDER_MODE,
        "pexels": bool(PEXELS_API_KEY),
        "openweather": bool(OPENWEATHER_API_KEY),
    })

@app.route("/preview", methods=["GET"])
def preview():
    """
    Render a preview PNG using:
      - device_id: which layout to load
      - week (optional) else current
      - idx (optional) choose which weekly image; default random
      - city (optional)
      - lat/lon (optional)
      - mode (optional) default 'sticker_parade'
    """
    device_id = request.args.get("device_id", DEFAULT_LAYOUT_DEVICE)
    the_mode = request.args.get("mode", DEFAULT_RENDER_MODE)

    # fetch layout
    lay_resp = get_layout(device_id)
    if isinstance(lay_resp, tuple):
        body = lay_resp[0] if lay_resp[1] == 200 else None
        layout = json.loads(body) if body else {"elements": []}
    else:
        layout = lay_resp.get_json()

    # choose a background image
    wk = request.args.get("week") or week_key()
    images = list_week_images(wk)
    if not images:
        # no weekly images yet → return transparent base with just overlay
        base = Image.new("RGB", (IMG_W, IMG_H), (30, 30, 30))
    else:
        idx_param = request.args.get("idx")
        if idx_param is not None:
            try:
                idx = int(idx_param) % len(images)
            except Exception:
                idx = 0
        else:
            idx = random.randint(0, max(0, len(images)-1))
        base = load_image_from_gcs(images[idx]) or Image.new("RGB", (IMG_W, IMG_H), (20, 20, 20))

    # weather + joke
    city = request.args.get("city", "Melbourne")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    wx = fetch_weather(city=city, lat=lat, lon=lon)  # safe even if no key
    joke = fetch_joke()
    inject = {
        "city": wx["city"],
        "min": wx["min"],
        "max": wx["max"],
        "icon": wx["icon"],
        "note": wx["note"],
        "date": now_utc().astimezone().strftime("%A, %d %b"),
        "joke": joke
    }

    composed = render_layout_on_image(base, layout, mode=the_mode, inject=inject)
    bio = io.BytesIO()
    composed.save(bio, format="PNG")
    bio.seek(0)
    return send_file(bio, mimetype="image/png")

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Local run
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=bool(os.getenv("DEBUG", "0") == "1"))