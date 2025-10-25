import os, io, random, time, hashlib, math
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import requests
from fastapi import FastAPI, Body, Query, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, Response, HTMLResponse
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

DEFAULT_ALPHA = int(os.getenv("OVERLAY_ALPHA", "160"))  # glass panel transparency

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

# Dynamic font cache (so we can size precisely)
_font_cache = {}
def font_px(px: int, weight: str = "Regular"):
    key = (px, weight)
    if key in _font_cache:
        return _font_cache[key]
    fname = f"Roboto-{weight}.ttf"
    path = os.path.join(FONT_DIR, fname)
    try:
        f = ImageFont.truetype(path, px)
    except Exception:
        f = ImageFont.load_default()
    _font_cache[key] = f
    return f

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

def glass_panel(img: Image.Image, box: Tuple[int,int,int,int], blur=6, alpha=DEFAULT_ALPHA, radius=14):
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
    """
    Returns:
      {
        "description": "Few Clouds",
        "temp": 33.2,
        "tmin": 26.0,
        "tmax": 34.8,
        "kind": "partly",
        "note": "Humid heat — stay hydrated"
      }
    Prefers OpenWeather (if WEATHER_KEY). Falls back to Open-Meteo (no key).
    """
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

    def note_for(kind: str, tmin: float, tmax: float, units: str) -> str:
        hot = (tmax >= (32 if units=="metric" else 90))
        cold = (tmin <= (5 if units=="metric" else 41))
        if kind == "storm": return "Thunderstorms possible"
        if kind == "rain":  return "Carry an umbrella"
        if kind == "snow":  return "Snow likely — take care"
        if kind == "fog":   return "Low visibility"
        if hot:             return "Humid heat — stay hydrated"
        if cold:            return "Chilly — layer up"
        if kind == "partly":return "Intervals of cloud and sun"
        if kind == "sunny": return "Clear and bright"
        return "Mostly cloudy"

    # --- OpenWeather path (if key present) ---
    if WEATHER_KEY:
        try:
            g = requests.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": city, "limit": 1, "appid": WEATHER_KEY}, timeout=8
            ).json()
            lat, lon = g[0]["lat"], g[0]["lon"]

            cur = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "units": units, "appid": WEATHER_KEY}, timeout=8
            ).json()
            desc = cur["weather"][0]["description"].title()
            temp = float(cur["main"]["temp"])

            # derive min/max from short-term forecast (next ~24–36h)
            fc = requests.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "units": units, "appid": WEATHER_KEY}, timeout=8
            ).json()
            temps = [float(it["main"]["temp"]) for it in (fc.get("list") or [])[:12] if it.get("main")]
            tmin = min(temps) if temps else temp
            tmax = max(temps) if temps else temp

            kind = classify(desc)
            return {"description": desc, "temp": temp, "tmin": tmin, "tmax": tmax,
                    "kind": kind, "note": note_for(kind, tmin, tmax, units)}
        except Exception:
            pass  # fall through to Open-Meteo

    # --- Open-Meteo (no key) ---
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1}, timeout=8).json()
        lat, lon = g["results"][0]["latitude"], g["results"][0]["longitude"]
        params = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max",
            "timezone": "auto",
        }
        if units == "imperial":
            params["temperature_unit"] = "fahrenheit"
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=8).json()
        cur = r.get("current", {})
        daily = r.get("daily", {})
        code = int(cur.get("weather_code", 3))
        temp = float(cur.get("temperature_2m", 20))
        tmin = float(daily.get("temperature_2m_min", [temp])[0])
        tmax = float(daily.get("temperature_2m_max", [temp])[0])

        if   code == 0: kind, desc = "sunny", "Sunny"
        elif code in (1,2,3): kind, desc = "partly", "Partly Cloudy"
        elif code in (45,48): kind, desc = "fog", "Fog"
        elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82): kind, desc = "rain", "Rain"
        elif code in (71,73,75,77,85,86): kind, desc = "snow", "Snow"
        elif code in (95,96,99): kind, desc = "storm", "Thunderstorm"
        else: kind, desc = "cloudy", "Cloudy"

        return {"description": desc, "temp": temp, "tmin": tmin, "tmax": tmax,
                "kind": kind, "note": note_for(kind, tmin, tmax, units)}
    except Exception:
        return {"description":"Sunny","temp":33 if units=="metric" else 92,
                "tmin":30 if units=="metric" else 86,
                "tmax":34 if units=="metric" else 93,
                "kind":"sunny","note":"Clear and bright"}

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
# Overlay composer (DYNAMIC): side-by-side bottom panels (~30% height)
# ─────────────────────────────────────────────────────────────────────
def add_dynamic_overlays(img: Image.Image, city: Optional[str], units: str, show_joke: bool, layout: str="glass") -> Image.Image:
    draw = ImageDraw.Draw(img)

    # Top-right date label
    date = datetime.now().strftime("%a %d %b %Y")
    pad = 10
    tw = int(draw.textlength(date, font=FONT_DATE))
    th = draw.textbbox((0,0), date, font=FONT_DATE)[3]
    dbox = (img.width - tw - pad*2 - 12, 12, img.width - 12, 12 + th + pad*2)
    glass_panel(img, dbox, alpha=DEFAULT_ALPHA)
    draw.text((dbox[0]+pad, dbox[1]+pad), date, fill=(0,0,0), font=FONT_DATE)

    # Reserve bottom 30% for two side-by-side panels
    total_h = int(img.height * 0.30)                 # ≈144px on 480px height
    gap = 12
    y0 = img.height - gap - total_h
    y1 = img.height - gap
    mid = img.width // 2
    left_box  = (gap, y0, mid - gap//2, y1)              # Weather
    right_box = (mid + gap//2, y0, img.width - gap, y1)  # Dad joke

    # Fetch live info
    wx = fetch_weather(city or "Darwin", units=units)
    joke_text = fetch_joke() if show_joke else ""

    # ---- Weather panel (left) ----
    glass_panel(img, left_box, alpha=DEFAULT_ALPHA)
    lp = 14  # inner padding
    icon_box = (left_box[0]+lp, left_box[1]+lp, left_box[0]+lp+60, left_box[1]+lp+52)
    draw_weather_icon(draw, wx.get("kind","sunny"), icon_box)

    # Typography sizes
    city_font   = font_px(32, "Bold")                 # current font size
    minmax_font = font_px(int(32*0.8), "Regular")     # 20% smaller
    note_font   = font_px(int(32*0.8*0.8), "Regular") # 20% smaller than min/max

    # Text blocks
    text_x = icon_box[2] + 10
    text_y = left_box[1] + lp

    draw.text((text_x, text_y), f"{city or 'Weather'}", fill=(0,0,0), font=city_font)
    text_y += city_font.size + 6

    u = "°C" if units=="metric" else "°F"
    draw.text((text_x, text_y), f"Min {round(wx['tmin'])}{u}  •  Max {round(wx['tmax'])}{u}",
              fill=(0,0,0), font=minmax_font)
    text_y += minmax_font.size + 6

    # Note line — wrap if needed
    note_box = (text_x, text_y, left_box[2]-lp, left_box[3]-lp)
    draw_wrapped(draw, wx.get("note",""), note_box, note_font, line_gap=4)

    # ---- Dad joke panel (right) ----
    if show_joke:
        glass_panel(img, right_box, alpha=DEFAULT_ALPHA)
        rp = 14
        joke_font = minmax_font  # same size as min/max
        draw_wrapped(draw, joke_text, (right_box[0]+rp, right_box[1]+rp, right_box[2]-rp, right_box[3]-rp),
                     joke_font, line_gap=6)

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
    variant: Optional[int] = Query(default=None, ge=0, le=7),
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

# Simple browser preview of all day/variant combos
@app.get("/preview", response_class=HTMLResponse)
def preview_page(variants: int = 2, city: str = "Darwin"):
    base = ""
    html = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<title>Family Display Preview</title>",
            "<style>body{font-family:system-ui,sans-serif;background:#f2f2f2;margin:0}h1{background:#222;color:#fff;margin:0;padding:12px;text-align:center}"+
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px;padding:20px;max-width:1300px;margin:0 auto}"+
            ".card{background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.15);border-radius:8px;overflow:hidden;text-align:center;padding-bottom:8px}"+
            "img{width:100%;display:block}.label{font-size:.9rem;color:#444;margin-top:6px}</style></head><body>",
            "<h1>Weekly Preview</h1><div class='grid'>"]
    for d in range(7):
        for v in range(variants):
            url = f"/v1/frame?day={d}&variant={v}&city={city}&joke=true&units=metric"
            html.append(f"<div class='card'><img src='{url}'/><div class='label'>Day {d} • Variant {v}</div></div>")
    html.append("</div></body></html>")
    return "".join(html)