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
    if not _WEATHER_KEY: return {"description":"Sunny","temp":33}
    try:
        geo = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                           params={"q":city,"limit":1,"appid":_WEATHER_KEY}).json()
        lat, lon = geo[0]["lat"], geo[0]["lon"]
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"lat":lat,"lon":lon,"units":units,"appid":_WEATHER_KEY})
        data = r.json()
        return {"description":data["weather"][0]["description"].title(),
                "temp":data["main"]["temp"]}
    except Exception:
        return {"description":"Sunny","temp":33}

def fetch_joke():
    try:
        r = requests.get(_JOKE_URL, headers={"Accept":"application/json"}, timeout=3)
        if r.status_code==200: return r.json().get("joke")
    except Exception: pass
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

def draw_wrapped(draw,text,box,font):
    x0,y0,x1,y1=box
    words=text.split()
    line=""
    y=y0
    for w in words:
        test=(line+" "+w).strip()
        if draw.textlength(test,font=font)<=x1-x0: line=test
        else:
            draw.text((x0,y),line,fill=(0,0,0),font=font)
            y+=font.size+6
            line=w
    if line and y<y1: draw.text((x0,y),line,fill=(0,0,0),font=font)

def add_overlay(img,city="Darwin"):
    draw=ImageDraw.Draw(img)
    date=datetime.now().strftime("%a %d %b %Y")
    box=(img.width-260,12,img.width-12,12+50)
    glass_panel(img,box)
    draw.text((box[0]+10,box[1]+10),date,fill=(0,0,0),font=FONT_DATE)

    wx=fetch_weather(city)
    joke=fetch_joke()

    box_w=(12,img.height-130,img.width-12,img.height-70)
    glass_panel(img,box_w)
    draw.text((box_w[0]+14,box_w[1]+10),
              f"{city}: {wx['description']} {round(wx['temp'])}°C",
              fill=(0,0,0),font=FONT_BOLD)

    box_j=(12,img.height-60,img.width-12,img.height-12)
    glass_panel(img,box_j)
    draw_wrapped(draw,joke,(box_j[0]+14,box_j[1]+10,box_j[2]-14,box_j[3]-10),FONT_REG)
    return img

# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@app.get("/healthz", response_class=PlainTextResponse)
def health(): return "ok deepai-weekpack"

@app.post("/admin/generate")
def gen_weekly(
    city: str = Body(default="Darwin"),
    variants: int = Body(default=4),
    days: int = Body(default=7)
):
    """Generate 7 days × 4 variants (28 images) for this ISO week."""
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
                results.append({"day":d,"variant":v,"saved":ok,"theme":theme[:60]})
            except Exception as e:
                results.append({"day":d,"variant":v,"error":str(e)})
    return {"week":week_id,"count":len(results),"prefix":prefix,"results":results}

@app.get("/")
def root():
    return {
        "status":"ok",
        "version":"deepai-weekpack-2025-10-25",
        "gcs":bool(bucket()),
        "provider":"deepai",
        "weekly_pack":True,
        "default_layout":"glass"
    }