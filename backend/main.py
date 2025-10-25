import os, io, random, time, hashlib, math
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import requests
from fastapi import FastAPI, Body, Query, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from google.cloud import storage
except Exception:
    storage = None

app = FastAPI()

# ─────────────────────────────────────────────────────────────────────
# Config / Env
# ─────────────────────────────────────────────────────────────────────
EINK_PALETTE = [
    (255,255,255),(0,0,0),(255,0,0),(255,255,0),(0,0,255),(0,128,0)
]

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
DEEPAI_KEY  = os.getenv("DEEPAI_API_KEY")
WEATHER_KEY = os.getenv("WEATHER_API_KEY") or os.getenv("OWM_API_KEY")
JOKE_URL    = os.getenv("JOKE_URL","https://icanhazdadjoke.com/")
DEEPAI_URL  = "https://api.deepai.org/api/text2img"

# Caches
CACHE_JOKE = {"ts":0, "joke":None}
JOKE_TTL   = int(os.getenv("JOKE_TTL_SECONDS","900"))

# Fonts (Roboto in ./fonts)
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()
FONT_REG  = _font("Roboto-Regular.ttf", 26)
FONT_BOLD = _font("Roboto-Bold.ttf",    32)
FONT_DATE = _font("Roboto-Bold.ttf",    24)

# Themes for weekly backgrounds
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

# ─────────────────────────────────────────────────────────────────────
# GCS helpers
# ─────────────────────────────────────────────────────────────────────
_gcs_bucket = None
def gcs_bucket():
    global _gcs_bucket
    if _gcs_bucket is not None:
        return _gcs_bucket
    if not BUCKET_NAME or storage is None:
        return None
    try:
        _gcs_bucket = storage.Client().bucket(BUCKET_NAME)
    except Exception as e:
        print("GCS init failed:", e)
        _gcs_bucket = None
    return _gcs_bucket

def gcs_put(key: str, data: bytes, content_type="image/png") -> bool:
    b = gcs_bucket()
    if not b: return False
    try:
        blob = b.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return True
    except Exception as e:
        print("GCS upload failed:", e)
        return False

def gcs_get(key: str) -> Optional[bytes]:
    b = gcs_bucket()
    if not b: return None
    try:
        blob = b.blob(key)
        if blob.exists():
            return blob.download_as_bytes()
    except Exception as e:
        print("GCS get failed:", e)
    return None

# ─────────────────────────────────────────────────────────────────────
# Image utils / overlays
# ─────────────────────────────────────────────────────────────────────
def cover_resize(img: Image.Image, w=800, h=480) -> Image.Image:
    sw, sh = img.size
    sc = max(w/sw, h/sh)
    nw, nh = int(sw*sc), int(sh*sc)
    img = img.resize((nw,nh), Image.LANCZOS)
    return img.crop(((nw-w)//2,(nh-h)//2,(nw-w)//2+w,(nh-h)//2+h))

def glass_panel(img: Image.Image, box: Tuple[int,int,int,int], blur=6, alpha=220, radius=14):
    x0,y0,x1,y1 = box
    region = img.crop(box).filter(ImageFilter.GaussianBlur(blur))
    overlay = Image.new("RGBA", (x1-x0, y1-y0), (255,255,255,alpha))
    region = region.convert("RGBA")
    region.alpha_composite(overlay)
    img.paste(region.convert("RGB"), (x0,y0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box, radius=radius, outline=(0,0,0), width=1)

def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, box, font, line_gap=6, fill=(0,0,0)):
    x0,y0,x1,y1 = box
    words = text.split()
    line, y = "", y0
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=font) <= (x1-x0):
            line = test
        else:
            if y + font.size > y1: break
            draw.text((x0,y), line, fill=fill, font=font)
            y += font.size + line_gap
            line = w
    if line and y + font.size <= y1:
        draw.text((x0,y), line, fill=fill, font=font)

# Weather icons (vector-drawn with Pillow)
def _sun(draw, cx, cy, r=14):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(255,200,0), outline=(0,0,0))
    for i in range(12):
        ang = i * 30
        dx = int((r+8)*math.cos(math.radians(ang)))
        dy = int((r+8)*math.sin(math.radians(ang)))
        draw.line((cx,cy,cx+dx,cy+dy), fill=(0,0,0), width=2)

def _cloud(draw, x, y, w=54, h=28):
    ell=[(x, y+h//4, x+w//2, y+h),
         (x+w//3, y, x+w-w//6, y+h),
         (x+w//2, y+h//4, x+w, y+h)]
    for e in ell: draw.ellipse(e, fill=(240,240,240), outline=(0,0,0))
    draw.line((x+6,y+h,x+w-6,y+h), fill=(0,0,0), width=2)

def _raindrops(draw, x, y, n=3, gap=14):
    for i in range(n):
        cx = x + i*gap
        draw.line((cx, y, cx-3, y+10), fill=(0,0,255), width=2)

def _snow(draw, x, y, n=3, gap=14):
    for i in range(n):
        cx = x + i*gap
        draw.line((cx-5,y, cx+5,y+10), fill=(0,0,0), width=2)
        draw.line((cx+5,y, cx-5,y+10), fill=(0,0,0), width=2)
        draw.line((cx,y-2, cx,y+12),  fill=(0,0,0), width=2)

def _bolt(draw, x, y):
    pts=[(x,y),(x+8,y+2),(x+2,y+14),(x+14,y+12),(x+6,y+26)]
    draw.line(pts, fill=(255,165,0), width=3)

def draw_weather_icon(draw, kind: str, box):
    x0,y0,x1,y1 = box
    if kind == "sunny":
        _sun(draw, (x0+x1)//2, (y0+y1)//2, r=min(x1-x0,y1-y0)//3)
    elif kind == "partly":
        _sun(draw, (x0+x1)//2-6, (y0+y1)//2-6, r=10)
        _cloud(draw, x0+6, y0+10, 48, 24)
    elif kind == "cloudy":
        _cloud(draw, x0+4, y0+8, 54, 28)
    elif kind == "rain":
        _cloud(draw, x0+4, y0+6, 54, 26); _raindrops(draw, x0+14, y0+30)
    elif kind == "storm":
        _cloud(draw, x0+4, y0+6, 54, 26); _bolt(draw, x0+24, y0+26)
    elif kind == "snow":
        _cloud(draw, x0+4, y0+6, 54, 26); _snow(draw, x0+12, y0+28)
    else:
        for i in range(3):
            yy = y0+12 + i*8
            draw.line((x0+6,yy,x1-6,yy), fill=(150,150,150), width=2)

# ─────────────────────────────────────────────────────────────────────
# External APIs
# ─────────────────────────────────────────────────────────────────────
def deepai_generate(prompt: str) -> bytes:
    if not DEEPAI_KEY:
        raise RuntimeError("DEEPAI_API_KEY not set")
    r = requests.post(
        DEEPAI_URL,
        headers={"api-key": DEEPAI_KEY},
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
    def classify(desc: str) -> str:
        s = desc.lower()
        if any(k in s for k in ["thunder","storm"]): return "storm"
        if any(k in s for k in ["rain","drizzle","shower"]): return "rain"
        if "snow" in s: return "snow"
        if any(k in s for k in ["mist","fog","haze","smoke"]): return "fog"
        if "cloud" in s or "overcast" in s:
            return "partly" if any(k in s for k in ["few","scattered","broken","partly"]) else "cloudy"
        if any(k in s for k in ["clear","sunny"]): return "sunny"
        return "cloudy"
    if not WEATHER_KEY:
        return {"description":"Sunny","temp":33,"kind":"sunny"}
    try:
        geor = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                            params={"q":city,"limit":1,"appid":WEATHER_KEY}, timeout=8)
        geor.raise_for_status()
        lat, lon = geor.json()[0]["lat"], geor.json()[0]["lon"]
        wr = requests.get("https://api.openweathermap.org/data/2.5/weather",
                          params={"lat":lat,"lon":lon,"units":units,"appid":WEATHER_KEY}, timeout=8)
        wr.raise_for_status()
        data = wr.json()
        desc = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        return {"description":desc, "temp":temp, "kind":classify(desc)}
    except Exception:
        return {"description":"Sunny","temp":33,"kind":"sunny"}

def fetch_joke() -> str:
    now = time.time()
    if CACHE_JOKE["joke"] and now - CACHE_JOKE["ts"] < JOKE_TTL:
        return CACHE_JOKE["joke"]
    try:
        r = requests.get(JOKE_URL, headers={"Accept":"application/json", "User-Agent":"family-display/1.0"}, timeout=3)
        if r.status_code == 200:
            j = r.json()
            joke = j.get("joke") or j.get("setup") or random.choice(FALLBACK_JOKES)
            CACHE_JOKE.update({"joke":joke,"ts":now})
            return joke
    except Exception:
        pass
    joke = random.choice(FALLBACK_JOKES)
    CACHE_JOKE.update({"joke":joke,"ts":now})
    return joke

# ─────────────────────────────────────────────────────────────────────
# Overlay composer (DYNAMIC)
# ─────────────────────────────────────────────────────────────────────
def add_dynamic_overlays(img: Image.Image, city: Optional[str], units: str, show_joke: bool, layout: str="glass") -> Image.Image:
    draw = ImageDraw.Draw(img)

    # Date (top-right)
    date = datetime.now().strftime("%a %d %b %Y")
    pad = 10
    text_w = int(draw.textlength(date, font=FONT_DATE))
    text_h = draw.textbbox((0,0), date, font=FONT_DATE)[3]
    box = (img.width - text_w - pad*2 - 12, 12, img.width - 12, 12 + text_h + pad*2)
    glass_panel(img, box); draw.text((box[0]+pad, box[1]+pad), date, fill=(0,0,0), font=FONT_DATE)

    # Weather strip
    wx = fetch_weather(city or "Darwin", units=units)
    strip_h = 64
    box_w = (12, img.height - strip_h - 12 - (48 if show_joke else 0), img.width - 12, img.height - 12 - (48 if show_joke else 0))
    glass_panel(img, box_w)

    icon_box = (box_w[0]+10, box_w[1]+8, box_w[0]+10+60, box_w[1]+8+48)
    draw_weather_icon(draw, wx.get("kind","sunny"), icon_box)
    title = f"{city or 'Weather'}: {wx['description']} {round(wx['temp'])}°{'C' if units=='metric' else 'F'}"
    draw.text((icon_box[2]+10, box_w[1]+10), title, fill=(0,0,0), font=FONT_BOLD)

    # Dad joke
    if show_joke:
        joke = fetch_joke()
        box_j = (12, img.height - 48, img.width - 12, img.height - 12)
        glass_panel(img, box_j)
        draw_wrapped(draw, joke, (box_j[0]+14, box_j[1]+10, box_j[2]-14, box_j[3]-10), FONT_REG)
    return img

# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok dynamic-overlays"

@app.get("/")
def root():
    return {
        "status":"ok",
        "version":"deepai-weekpack-dynamic-overlays-2025-10-25",
        "gcs":bool(gcs_bucket()),
        "provider":"deepai",
        "dynamic_overlays":True,
        "default_layout":"glass"
    }

@app.post("/admin/generate")
def admin_generate(
    days: int = Body(default=7),
    variants: int = Body(default=4),
    week: Optional[str] = Body(default=None, description="ISO week like 2025W43"),
):
    """
    Generate BACKGROUNDS ONLY for the given (or current) ISO week:
    Saves to: weekly/<WEEK>/<day>_<variant>.png
    """
    if variants < 1 or variants > 8: variants = max(1, min(variants, 8))
    if days < 1 or days > 7: days = max(1, min(days, 7))
    week_id = week or datetime.utcnow().strftime("%G%V")  # e.g., 2025W43
    prefix = f"weekly/{week_id}"
    out: List[Dict[str,Any]] = []

    for d in range(days):
        for v in range(variants):
            theme = random.choice(THEMES)
            try:
                raw = deepai_generate(theme)
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                img = cover_resize(img, 800, 480)
                buf = io.BytesIO(); img.save(buf, format="PNG")
                key = f"{prefix}/{d}_{v}.png"
                ok = gcs_put(key, buf.getvalue())
                out.append({"day":d,"variant":v,"key":key,"saved":ok,"theme":theme[:80]})
            except Exception as e:
                out.append({"day":d,"variant":v,"error":str(e)})
    return {"week":week_id, "count":len(out), "prefix":prefix, "results":out}

@app.get("/v1/frame")
def v1_frame(
    request: Request,
    week: Optional[str] = Query(default=None, description="ISO week like 2025W43 (defaults to current)"),
    day: Optional[int] = Query(default=None, ge=0, le=6),
    variant: Optional[int] = Query(default=None, ge=0, le=3),
    city: Optional[str] = Query(default=None),
    units: str = Query(default="metric", regex="^(metric|imperial)$"),
    joke: bool = Query(default=True),
    layout: str = Query(default="glass")
):
    """Serve a composed frame: background from GCS + dynamic overlays."""
    wk = week or datetime.utcnow().strftime("%G%V")
    d  = day if day is not None else datetime.utcnow().weekday()
    v  = variant if variant is not None else random.randint(0, 3)
    key = f"weekly/{wk}/{d}_{v}.png"

    # 1) Get background from GCS, else fallback
    bg_bytes = gcs_get(key)
    if not bg_bytes:
        # fallback placeholder
        img = Image.new("RGB", (800,480), EINK_PALETTE[0])
        draw = ImageDraw.Draw(img)
        draw.text((20,20), f"Missing background: {wk}/{d}_{v}.png", fill=(0,0,0), font=FONT_BOLD)
    else:
        img = Image.open(io.BytesIO(bg_bytes)).convert("RGB")

    # 2) Compose dynamic overlays
    img = add_dynamic_overlays(img, city=city, units=units, show_joke=joke, layout=layout)

    # 3) ETag for battery/network savings
    out = io.BytesIO(); img.save(out, format="PNG")
    content = out.getvalue()
    etag = hashlib.sha1(content).hexdigest()
    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        return Response(status_code=304)
    return Response(content=content, media_type="image/png",
                    headers={"ETag": etag, "Cache-Control":"public, max-age=300",
                             "X-Background-Key": key})