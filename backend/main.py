import os, io, random, time
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests
from fastapi import FastAPI, Body
from fastapi.responses import PlainTextResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from google.cloud import storage
except Exception:
    storage = None

app = FastAPI()

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
EINK_PALETTE = [
    (255, 255, 255),
    (0, 0, 0),
    (255, 0, 0),
    (255, 255, 0),
    (0, 0, 255),
    (0, 128, 0),
]

_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
_DEEPAI_KEY = os.getenv("DEEPAI_API_KEY")
_WEATHER_KEY = os.getenv("WEATHER_API_KEY") or os.getenv("OWM_API_KEY")
_JOKE_URL = "https://icanhazdadjoke.com/"
_DEEPAI_URL = "https://api.deepai.org/api/text2img"

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()

FONT_REG = _font("Roboto-Regular.ttf", 26)
FONT_BOLD = _font("Roboto-Bold.ttf", 32)
FONT_DATE = _font("Roboto-Bold.ttf", 24)

# ---------------------------------------------------------------------
# DeepAI theme prompts
# ---------------------------------------------------------------------
THEMES = [
    "Colorful geometric poster art with soft gradients and organic shapes, abstract paper-collage style. Modern minimalist design, bright clean palette.",
    "Abstract nature illustration with stylized sun, hills and sky. Bright flat colors, mid-century modern poster style.",
    "Blue-themed abstract poster with waves and circles, geometric sea and sun, vivid modern palette.",
    "Playful abstract art with circles, triangles and paper-cut textures, cheerful family vibe, bright flat vector look.",
    "Soft pastel minimalist abstract poster, simple geometric forms and generous negative space, Japanese zen design.",
    "Retro-tech geometric poster: grids, circles and lines, neon-pastel palette, futuristic retro feel.",
    "Warm sunset palette abstract landscape: layered hills, sun disc, smooth gradients, poster art style.",
    "Memphis design inspired abstract: bold shapes, dots, squiggles, high-contrast flat colors, graphic poster."
]

FALLBACK_JOKES = [
    "Why did the picture go to jail? Because it was framed.",
    "I told my wife she should embrace her mistakes... she gave me a hug.",
    "Parallel lines have so much in common. It’s a shame they’ll never meet.",
    "Did you hear about the claustrophobic astronaut? He just needed a little space.",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "I used to be addicted to soap, but I’m clean now.",
]

# ---------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------
_bucket = None
def bucket():
    global _bucket
    if _bucket: return _bucket
    if not _BUCKET_NAME or storage is None: return None
    try:
        _bucket = storage.Client().bucket(_BUCKET_NAME)
    except Exception as e:
        print(f"GCS init failed: {e}")
        _bucket = None
    return _bucket

def put_to_gcs(key: str, data: bytes, content_type="image/png"):
    b = bucket()
    if not b: return False
    try:
        blob = b.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return True
    except Exception as e:
        print("Upload failed:", e)
        return False

# ---------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------
def deepai_generate(prompt: str) -> bytes:
    if not _DEEPAI_KEY:
        raise RuntimeError("DEEPAI_API_KEY not set")
    r = requests.post(
        _DEEPAI_URL,
        headers={"api-key": _DEEPAI_KEY},
        data={"text": prompt},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"DeepAI error: {r.status_code} {r.text[:200]}")
    j = r.json()
    url = j.get("output_url")
    if not url:
        raise RuntimeError("DeepAI: no output_url")
    ir = requests.get(url, timeout=60)
    ir.raise_for_status()
    return ir.content

def fetch_weather(city="Darwin", units="metric"):
    # Returns: {"description": str, "temp": float, "kind": "sunny|partly|cloudy|rain|storm|snow|fog"}
    def classify(desc: str) -> str:
        s = desc.lower()
        if any(k in s for k in ["thunder", "storm"]): return "storm"
        if any(k in s for k in ["rain", "drizzle", "shower"]): return "rain"
        if "snow" in s: return "snow"
        if any(k in s for k in ["mist","fog","haze","smoke"]): return "fog"
        if any(k in s for k in ["cloud","overcast"]):
            return "partly" if any(k in s for k in ["few","scattered","broken","partly"]) else "cloudy"
        if any(k in s for k in ["clear","sunny"]): return "sunny"
        return "cloudy"

    if not _WEATHER_KEY:
        return {"description":"Sunny","temp":33,"kind":"sunny"}
    try:
        geo = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                           params={"q":city,"limit":1,"appid":_WEATHER_KEY}, timeout=8).json()
        lat, lon = geo[0]["lat"], geo[0]["lon"]
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"lat":lat,"lon":lon,"units":units,"appid":_WEATHER_KEY}, timeout=8)
        data = r.json()
        desc = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        return {"description": desc, "temp": temp, "kind": classify(desc)}
    except Exception:
        return {"description":"Sunny","temp":33,"kind":"sunny"}

def fetch_joke():
    try:
        r = requests.get(_JOKE_URL, headers={"Accept":"application/json"}, timeout=3)
        if r.status_code==200: 
            j = r.json()
            return j.get("joke") or j.get("setup") or random.choice(FALLBACK_JOKES)
    except Exception: 
        pass
    return random.choice(FALLBACK_JOKES)

# ---------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------
def cover_resize(img,w=800,h=480):
    sw,sh = img.size
    sc = max(w/sw, h/sh)
    nw,nh = int(sw*sc), int(sh*sc)
    img = img.resize((nw,nh), Image.LANCZOS)
    return img.crop(((nw-w)//2,(nh-h)//2,(nw-w)//2+w,(nh-h)//2+h))

def glass_panel(img,box,blur=6,alpha=220,radius=14):
    x0,y0,x1,y1 = box
    region = img.crop(box).filter(ImageFilter.GaussianBlur(blur))
    overlay = Image.new("RGBA",(x1-x0,y1-y0),(255,255,255,alpha))
    region = region.convert("RGBA")
    region.alpha_composite(overlay)
    img.paste(region.convert("RGB"),(x0,y0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box,radius=radius,outline=(0,0,0),width=1)

def draw_wrapped(draw,text,box,font, line_gap=6):
    x0,y0,x1,y1=box
    words=text.split()
    line=""
    y=y0
    for w in words:
        test=(line+" "+w).strip()
        if draw.textlength(test,font=font)<=x1-x0: 
            line=test
        else:
            draw.text((x0,y),line,fill=(0,0,0),font=font)
            y+=font.size+line_gap
            line=w
            if y>y1: break
    if line and y<=y1: draw.text((x0,y),line,fill=(0,0,0),font=font)

# ---- Weather Icons (vector-style via Pillow) ------------------------
def draw_sun(draw, cx, cy, r=14):
    # core
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(255, 200, 0), outline=(0,0,0))
    # rays
    for i in range(12):
        ang = i * (360/12)
        dx = int((r+8) * __import__("math").cos(__import__("math").radians(ang)))
        dy = int((r+8) * __import__("math").sin(__import__("math").radians(ang)))
        draw.line((cx, cy, cx+dx, cy+dy), fill=(0,0,0), width=2)

def draw_cloud(draw, x, y, w=54, h=28):
    # a simple cloud made of 3 circles + base
    ell = [
        (x, y+h//4, x+w//2, y+h),                    # left puff
        (x+w//3, y, x+w-w//6, y+h),                  # middle puff
        (x+w//2, y+h//4, x+w, y+h),                  # right puff
    ]
    for e in ell:
        draw.ellipse(e, fill=(240,240,240), outline=(0,0,0))
    # base line
    draw.line((x+6, y+h, x+w-6, y+h), fill=(0,0,0), width=2)

def draw_raindrops(draw, x, y, count=3, gap=14):
    for i in range(count):
        cx = x + i*gap
        draw.line((cx, y, cx-3, y+10), fill=(0,0,255), width=2)

def draw_snowflakes(draw, x, y, count=3, gap=14):
    for i in range(count):
        cx = x + i*gap
        # simple asterisk
        draw.line((cx-5, y, cx+5, y+10), fill=(0,0,0), width=2)
        draw.line((cx+5, y, cx-5, y+10), fill=(0,0,0), width=2)
        draw.line((cx, y-2, cx, y+12), fill=(0,0,0), width=2)

def draw_lightning(draw, x, y):
    # zigzag bolt
    pts = [(x, y), (x+8, y+2), (x+2, y+14), (x+14, y+12), (x+6, y+26)]
    draw.line(pts, fill=(255, 165, 0), width=3)

def draw_weather_icon(draw, kind: str, box):
    """
    Draws a 40x40-ish icon within the given box (x0,y0,x1,y1).
    """
    x0,y0,x1,y1 = box
    cx, cy = (x0+x1)//2, (y0+y1)//2
    w, h = x1-x0, y1-y0

    if kind == "sunny":
        draw_sun(draw, cx, cy, r=min(w,h)//3)
    elif kind == "partly":
        # sun peeking above a cloud
        draw_sun(draw, cx-6, cy-6, r=10)
        draw_cloud(draw, x0+6, y0+10, w=48, h=24)
    elif kind == "cloudy":
        draw_cloud(draw, x0+4, y0+8, w=54, h=28)
    elif kind == "rain":
        draw_cloud(draw, x0+4, y0+6, w=54, h=26)
        draw_raindrops(draw, x0+14, y0+30)
    elif kind == "storm":
        draw_cloud(draw, x0+4, y0+6, w=54, h=26)
        draw_lightning(draw, x0+24, y0+26)
    elif kind == "snow":
        draw_cloud(draw, x0+4, y0+6, w=54, h=26)
        draw_snowflakes(draw, x0+12, y0+28)
    else:  # fog or unknown
        # three horizontal lines to suggest fog
        for i in range(3):
            yy = y0+12 + i*8
            draw.line((x0+6, yy, x1-6, yy), fill=(150,150,150), width=2)

# ---------------------------------------------------------------------
# Overlays
# ---------------------------------------------------------------------
def add_overlay(img,city="Darwin"):
    draw=ImageDraw.Draw(img)
    # Date (top-right)
    date=datetime.now().strftime("%a %d %b %Y")
    padding = 10
    text_w = int(draw.textlength(date, font=FONT_DATE))
    text_h = draw.textbbox((0,0), date, font=FONT_DATE)[3]
    box=(img.width - text_w - padding*2 - 12, 12, img.width - 12, 12 + text_h + padding*2)
    glass_panel(img,box)
    draw.text((box[0]+padding,box[1]+padding),date,fill=(0,0,0),font=FONT_DATE)

    # Weather + Joke (bottom)
    wx=fetch_weather(city)
    joke=fetch_joke()

    # Weather strip
    strip_h = 64
    box_w=(12,img.height - strip_h - 12, img.width - 12, img.height - 12 - 48)
    glass_panel(img,box_w)

    # Icon (left), Text (right)
    icon_box = (box_w[0]+10, box_w[1]+8, box_w[0]+10+60, box_w[1]+8+48)
    draw_weather_icon(draw, wx.get("kind","sunny"), icon_box)

    title = f"{city}: {wx['description']} {round(wx['temp'])}°C"
    draw.text((icon_box[2]+10, box_w[1]+10), title, fill=(0,0,0), font=FONT_BOLD)

    # Dad joke bar
    box_j=(12, img.height - 48, img.width - 12, img.height - 12)
    glass_panel(img,box_j)
    draw_wrapped(draw, joke, (box_j[0]+14, box_j[1]+10, box_j[2]-14, box_j[3]-10), FONT_REG)
    return img

# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@app.get("/healthz", response_class=PlainTextResponse)
def health(): 
    return "ok deepai-weekpack + icons"

@app.post("/admin/generate")
def gen_weekly(
    city: str = Body(default="Darwin"),
    variants: int = Body(default=4),
    days: int = Body(default=7)
):
    """Generate 7 days × 4 variants (28 images) for this ISO week, with weather icons."""
    week_id = datetime.utcnow().strftime("%G%V")  # e.g. 2025W43
    prefix = f"weekly/{week_id}"
    results=[]
    for d in range(days):
        for v in range(variants):
            theme=random.choice(THEMES)
            try:
                raw=deepai_generate(theme)
                img=Image.open(io.BytesIO(raw)).convert("RGB")
                img=cover_resize(img,800,480)
                add_overlay(img,city)
                buf=io.BytesIO()
                img.save(buf,format="PNG")
                ok=put_to_gcs(f"{prefix}/{d}_{v}.png",buf.getvalue())
                results.append({"day":d,"variant":v,"saved":ok,"theme":theme[:80]})
            except Exception as e:
                results.append({"day":d,"variant":v,"error":str(e)})
    return {"week":week_id,"count":len(results),"prefix":prefix,"results":results}

@app.get("/")
def root():
    return {
        "status":"ok",
        "version":"deepai-weekpack-icons-2025-10-25",
        "gcs":bool(bucket()),
        "provider":"deepai",
        "weekly_pack":True,
        "default_layout":"glass",
        "icons":"built-in"
    }