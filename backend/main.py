import os, io, json, time, hashlib, random, datetime, pathlib
from datetime import timezone, timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, abort, send_file, send_from_directory
from google.cloud import storage
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
VERSION = "pexels-sticker-parade-2025-10-26"
app = Flask(__name__)

# ENV
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
DEFAULT_LAYOUT_DEVICE = os.getenv("DEFAULT_LAYOUT_DEVICE", "familydisplay")   # default test device
DEFAULT_RENDER_MODE = os.getenv("DEFAULT_RENDER_MODE", "sticker_parade")

# IMAGES
IMG_W, IMG_H = 800, 480
WEEKLY_THEME_SET = [
    "abstract backgrounds", "geometric shapes", "colorful gradients",
    "minimal art textures", "bokeh light wallpaper", "paper collage",
    "macro textures", "pastel abstract", "dark gradient background", "modern patterns"
]
PER_THEME_COUNT = 8

# FONTS
FONT_DIR = "./fonts"
FONT_REG = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
FONT_LIGHT = os.path.join(FONT_DIR, "Roboto-Light.ttf")

# FALLBACK JOKES
FALLBACK_JOKES = [
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "I used to be a banker but I lost interest.",
    "I ordered a chicken and an egg from Amazon... I’ll let you know.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I told my computer I needed a break, and it said 'No problem — I’ll go to sleep.'"
]

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def gcs_bucket():
    return storage.Client().bucket(GCS_BUCKET)

def now_utc():
    return datetime.datetime.now(timezone.utc)

def week_key(dt=None):
    dt = dt or now_utc()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"

def load_font(size=24, weight="regular"):
    path = FONT_REG
    if weight == "bold" and os.path.exists(FONT_BOLD): path = FONT_BOLD
    elif weight == "light" and os.path.exists(FONT_LIGHT): path = FONT_LIGHT
    try:
        return ImageFont.truetype(path, size=size)
    except:
        return ImageFont.load_default()

# -----------------------------------------------------------------------------
# STATIC FILES (Designer, Presets, Fonts)
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
# LAYOUT SAVE / LOAD
# -----------------------------------------------------------------------------
def _layout_paths(device_id):
    base = f"layouts/{device_id}"
    return {"current": f"{base}/current.json", "versions_prefix": f"{base}/versions/"}

def _validate_layout(data):
    return isinstance(data, dict) and "elements" in data

@app.route("/admin/layouts/<device_id>", methods=["PUT"])
def admin_put_layout(device_id):
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN: abort(401, "Unauthorized")
    try:
        payload = request.get_json(force=True)
    except:
        abort(400, "Invalid JSON")
    if not _validate_layout(payload): abort(400, "Invalid layout schema")

    now_ts = int(time.time())
    h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
    version = f"{now_ts}-{h}.json"

    bucket = gcs_bucket()
    paths = _layout_paths(device_id)
    # versioned
    vb = bucket.blob(paths["versions_prefix"] + version)
    vb.upload_from_string(json.dumps(payload), content_type="application/json")
    # current
    cb = bucket.blob(paths["current"])
    cb.upload_from_string(json.dumps(payload), content_type="application/json")

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
                return (defb.download_as_text(), 200, {"Content-Type":"application/json"})
        return jsonify({"elements": []})
    return (blob.download_as_text(), 200, {"Content-Type": "application/json"})

# -----------------------------------------------------------------------------
# PEXELS (for weekly background packs)
# -----------------------------------------------------------------------------
PEXELS_BASE = "https://api.pexels.com/v1"

def pexels_headers():
    if not PEXELS_API_KEY: raise RuntimeError("PEXELS_API_KEY not set")
    return {"Authorization": PEXELS_API_KEY}

def fetch_theme_images(theme, per=8):
    try:
        r = requests.get(f"{PEXELS_BASE}/search",
                         headers=pexels_headers(),
                         params={"query":theme,"per_page":per,"orientation":"landscape"},
                         timeout=20)
        if r.status_code == 200:
            return r.json().get("photos", [])
    except: pass
    return []

def store_photo_to_gcs(url, path):
    b = gcs_bucket()
    blob = b.blob(path)
    if blob.exists(): return True
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            blob.upload_from_string(resp.content, content_type="image/jpeg")
            return True
    except: pass
    return False

@app.route("/admin/prefetch", methods=["POST"])
def admin_prefetch():
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if ADMIN_TOKEN and token != ADMIN_TOKEN: abort(401)
    body = request.get_json(silent=True) or {}
    themes = body.get("themes") or WEEKLY_THEME_SET
    per = body.get("per_theme_count") or PER_THEME_COUNT
    wk = week_key()
    out = []
    for t in themes:
        photos = fetch_theme_images(t, per)
        saved = 0
        for i,p in enumerate(photos):
            src = p.get("src",{}).get("landscape") or p.get("src",{}).get("large")
            if not src: continue
            theme_slug = "".join([c for c in t.lower() if c.isalnum() or c in ("_","-")])
            dst = f"images/{wk}/{theme_slug}/img_{i}.jpg"
            if store_photo_to_gcs(src, dst): saved+=1
        out.append({"theme":t,"saved":saved})
    return jsonify({"ok":True,"week":wk,"themes":out})

# -----------------------------------------------------------------------------
# WEATHER + JOKE
# -----------------------------------------------------------------------------
def fetch_joke():
    try:
        r=requests.get("https://icanhazdadjoke.com/",headers={"Accept":"application/json"},timeout=5)
        if r.status_code==200: return r.json().get("joke")
    except: pass
    return random.choice(FALLBACK_JOKES)

def fetch_weather(city="Melbourne"):
    if not OPENWEATHER_API_KEY:
        return {"city":city,"min":12,"max":22,"icon":"🌤️","note":"Partly cloudy"}
    try:
        r=requests.get("https://api.openweathermap.org/data/2.5/weather",
                       params={"q":city,"appid":OPENWEATHER_API_KEY,"units":"metric"},
                       timeout=8)
        if r.status_code!=200: raise Exception()
        d=r.json(); main=d.get("main",{}); wx=d.get("weather",[{}])[0]
        desc=wx.get("description","Clear").capitalize()
        temp=main.get("temp",20)
        return {"city":d.get("name",city),"min":int(temp-3),"max":int(temp+3),
                "icon":"☀️","note":desc}
    except:
        return {"city":city,"min":12,"max":22,"icon":"🌤️","note":"Partly cloudy"}

# -----------------------------------------------------------------------------
# RENDER PREVIEW
# -----------------------------------------------------------------------------
def draw_text_wrapped(draw, txt, xy, w, font, fill):
    x, y = xy
    words = txt.split()
    line=""
    for wd in words:
        test = (line+" "+wd).strip()
        tw,_=draw.textsize(test,font=font)
        if tw<=w or not line: line=test
        else:
            draw.text((x,y),line,font=font,fill=fill); y+=font.size+3; line=wd
    if line: draw.text((x,y),line,font=font,fill=fill)

def render_overlay(img, layout, inject):
    out=img.convert("RGBA")
    drw=ImageDraw.Draw(out,"RGBA")
    def rr(x,y,w,h,fill=(255,255,255,160)):
        drw.rounded_rectangle([x,y,x+w,y+h],radius=14,fill=fill,outline=(185,215,211,255))
    for el in layout.get("elements",[]):
        k=el.get("kind","box"); x=int(el.get("x",0)); y=int(el.get("y",0))
        w=int(el.get("w",150)); h=int(el.get("h",50))
        if "box" in k: rr(x,y,w,h)
        else:
            text=el.get("text","")
            if "city" in text.lower(): text=f"{inject['city']} • {inject['max']}°/{inject['min']}°"
            if "joke" in text.lower(): text=inject["joke"]
            f=load_font(int(h*0.6),"bold")
            draw_text_wrapped(drw,text,(x+8,y+6),w-16,f,"black")
    return out

@app.route("/preview")
def preview():
    device_id = request.args.get("device_id", DEFAULT_LAYOUT_DEVICE)
    bucket=gcs_bucket()
    blob=bucket.blob(f"layouts/{device_id}/current.json")
    layout=json.loads(blob.download_as_text()) if blob.exists() else {"elements":[]}

    # pick bg
    wk=week_key()
    imgs=[b.name for b in bucket.list_blobs(prefix=f"images/{wk}/") if b.name.endswith(".jpg")]
    bg=Image.new("RGB",(IMG_W,IMG_H),(50,50,50))
    if imgs:
        chosen=random.choice(imgs)
        data=bucket.blob(chosen).download_as_bytes()
        bg=Image.open(io.BytesIO(data)).convert("RGB").resize((IMG_W,IMG_H))
    wx=fetch_weather("Melbourne")
    joke=fetch_joke()
    composed=render_overlay(bg,layout,{"city":wx["city"],"min":wx["min"],"max":wx["max"],"icon":wx["icon"],"joke":joke})
    bio=io.BytesIO(); composed.save(bio,"PNG"); bio.seek(0)
    return send_file(bio,mimetype="image/png")

# -----------------------------------------------------------------------------
# ROOT
# -----------------------------------------------------------------------------
@app.route("/")
def root():
    return jsonify({
        "status":"ok","version":VERSION,
        "default_device":DEFAULT_LAYOUT_DEVICE,
        "default_mode":DEFAULT_RENDER_MODE,
        "pexels":bool(PEXELS_API_KEY),
        "openweather":bool(OPENWEATHER_API_KEY),
        "gcs":True
    })

# -----------------------------------------------------------------------------
# RUN
# -----------------------------------------------------------------------------
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",8080)),debug=True)