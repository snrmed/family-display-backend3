import os
import io
import random
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import requests
from fastapi import FastAPI, Response, HTTPException, Body, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from google.cloud import storage
except Exception:
    storage = None

# ----------------------------
# Config / Globals
# ----------------------------
EINK_PALETTE = [
    (255, 255, 255),  # white
    (0, 0, 0),        # black
    (255, 0, 0),      # red
    (255, 255, 0),    # yellow
    (0, 0, 255),      # blue
    (0, 128, 0),      # green
]

app = FastAPI()

# Env
_bucket = None
_bucket_name = os.getenv("GCS_BUCKET_NAME")

# Generation providers
_provider = os.getenv("GEN_PROVIDER", "deepai").lower()

# DeepAI
_DEEPAI_KEY = os.getenv("DEEPAI_API_KEY")
_DEEPAI_URL = "https://api.deepai.org/api/text2img"

# Hugging Face (optional fallback)
_hf_token = os.getenv("HUGGING_FACE_TOKEN") or os.getenv("HF_TOKEN")
_hf_model = os.getenv("HF_MODEL", "stabilityai/sd-turbo")

# Weather
_weather_api_key = os.getenv("WEATHER_API_KEY") or os.getenv("OWM_API_KEY")

# Dad joke
_joke_api_url = os.getenv("JOKE_API_URL", "https://icanhazdadjoke.com/")

# Caches
_cache_weather: Dict[str, Dict[str, Any]] = {}     # key -> {"ts": epoch, "data": {...}}
_cache_joke: Dict[str, Any] = {"ts": 0, "joke": None}
WEATHER_TTL = int(os.getenv("WEATHER_TTL_SECONDS", "900"))  # 15 min
JOKE_TTL = int(os.getenv("JOKE_TTL_SECONDS", "900"))        # 15 min

# Fallback jokes
FALLBACK_JOKES = [
    "Why did the picture go to jail? Because it was framed.",
    "I used to play piano by ear, but now I use my hands.",
    "I told my wife she should embrace her mistakes... she gave me a hug.",
    "I only know 25 letters of the alphabet. I don't know y.",
    "Parallel lines have so much in common. It’s a shame they’ll never meet.",
    "Did you hear about the claustrophobic astronaut? He just needed a little space.",
    "I’m reading a book about anti-gravity — it’s impossible to put down.",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "I used to be addicted to soap, but I’m clean now.",
    "Why did the scarecrow win an award? He was outstanding in his field."
]

# Fonts
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
def load_font(fname: str, size: int):
    path = os.path.join(FONT_DIR, fname)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

FONT_REG = load_font("Roboto-Regular.ttf", 26)
FONT_BOLD = load_font("Roboto-Bold.ttf", 32)
FONT_LIGHT = load_font("Roboto-Light.ttf", 24)
FONT_DATE = load_font("Roboto-Bold.ttf", 24)

# ----------------------------
# Infra helpers
# ----------------------------
def get_bucket():
    global _bucket
    if _bucket is not None:
        return _bucket
    if not _bucket_name or storage is None:
        _bucket = None
        return _bucket
    try:
        client = storage.Client()
        _bucket = client.bucket(_bucket_name)
    except Exception as e:
        print(f"WARNING: GCS init failed: {e}")
        _bucket = None
    return _bucket

def put_to_gcs(key: str, data: bytes, content_type: str = "image/png") -> bool:
    bucket = get_bucket()
    if not bucket:
        return False
    try:
        blob = bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return True
    except Exception as e:
        print(f"GCS upload failed for {key}: {e}")
        return False

def fetch_from_gcs(day_idx:int, var_idx:int):
    bucket = get_bucket()
    if not bucket:
        return None, None
    keys = [f"weekly/{day_idx}_{var_idx}.png", f"stale/{day_idx}_{var_idx}.png"]
    for k in keys:
        try:
            blob = bucket.blob(k)
            if blob.exists():
                return blob.download_as_bytes(), k
        except Exception as e:
            print(f"GCS fetch error for {k}: {e}")
    return None, None

def local_fallback(day_idx:int, var_idx:int):
    base = os.path.join(os.path.dirname(__file__), "fallback_art")
    p1 = os.path.join(base, f"fallback_{var_idx}.png")
    if os.path.exists(p1):
        with open(p1, "rb") as f:
            return f.read(), f"fallback_{var_idx}.png"
    p2 = os.path.join(base, f"{day_idx}_{var_idx}.png")
    if os.path.exists(p2):
        with open(p2, "rb") as f:
            return f.read(), f"{day_idx}_{var_idx}.png"
    return _seed_image_bytes(label=f"seed {day_idx}_{var_idx}"), "seed"

def _seed_image_bytes(w=800, h=480, label="fallback"):
    img = Image.new("RGB", (w, h), EINK_PALETTE[0])
    draw = ImageDraw.Draw(img)
    bar_w = w // len(EINK_PALETTE)
    for i, color in enumerate(EINK_PALETTE):
        draw.rectangle([i*bar_w, 0, (i+1)*bar_w-1, h//3], fill=color)
    draw.text((20, h//2 - 10), f"Family Display - {label}", fill=(0,0,0), font=FONT_REG)
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def cover_resize_to(img: Image.Image, w=800, h=480) -> Image.Image:
    src_w, src_h = img.size
    scale = max(w/src_w, h/src_h)
    new_w, new_h = int(src_w*scale), int(src_h*scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w)//2
    top = (new_h - h)//2
    return img.crop((left, top, left+w, top+h))

# ----------------------------
# Generators: DeepAI (primary), HF (optional fallback)
# ----------------------------
def deepai_text2image(prompt: str) -> bytes:
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
    out_url = j.get("output_url")
    if not out_url:
        raise RuntimeError(f"DeepAI: no output_url in response: {j}")
    ir = requests.get(out_url, timeout=60)
    ir.raise_for_status()
    return ir.content

def hf_text2image(prompt: str) -> bytes:
    if not _hf_token:
        raise RuntimeError("HUGGING_FACE_TOKEN not set")
    url = f"https://api-inference.huggingface.co/models/{_hf_model}"
    headers = {"Authorization": f"Bearer {_hf_token}", "Accept": "image/png", "Content-Type": "application/json"}
    payload = {"inputs": prompt}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"HF error: {r.status_code} {r.text[:200]}")
    return r.content

def generate_image_bytes(prompt: str) -> bytes:
    # Try selected provider first
    if _provider == "deepai":
        try:
            return deepai_text2image(prompt)
        except Exception as e:
            # Fallback to HF if configured
            if _hf_token:
                print(f"[WARN] DeepAI failed: {e}. Trying Hugging Face...")
                return hf_text2image(prompt)
            raise
    # If provider != deepai, try HF first
    if _hf_token:
        try:
            return hf_text2image(prompt)
        except Exception as e:
            if _DEEPAI_KEY:
                print(f"[WARN] HF failed: {e}. Trying DeepAI...")
                return deepai_text2image(prompt)
            raise
    # If no providers configured
    raise RuntimeError("No generation provider configured")

# ----------------------------
# Weather (robust + caching)
# ----------------------------
def fetch_weather(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, units: str="metric"):
    if not _weather_api_key:
        raise RuntimeError("WEATHER_API_KEY/OWM_API_KEY not set")
    cache_key = f"{city or lat},{lon}|{units}"
    now = time.time()
    if cache_key in _cache_weather and now - _cache_weather[cache_key]["ts"] < WEATHER_TTL:
        return _cache_weather[cache_key]["data"]

    # Geocode if city provided
    if city and (lat is None or lon is None):
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        gr = requests.get(geo_url, params={"q": city, "limit": 1, "appid": _weather_api_key}, timeout=10)
        gr.raise_for_status()
        arr = gr.json()
        if not arr:
            raise RuntimeError(f"City not found: {city}")
        lat, lon = arr[0]["lat"], arr[0]["lon"]

    if lat is None or lon is None:
        raise RuntimeError("Provide city or lat/lon")

    # Try One Call 3.0
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/3.0/onecall",
            params={"lat": lat, "lon": lon, "units": units, "exclude": "minutely,hourly,alerts", "appid": _weather_api_key},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            current = data.get("current", {})
            daily = (data.get("daily") or [{}])[0]
            desc = (current.get("weather") or daily.get("weather") or [{}])[0].get("description", "n/a").title()
            temp = current.get("temp")
            tmin = daily.get("temp", {}).get("min", temp)
            tmax = daily.get("temp", {}).get("max", temp)
            out = {"lat": lat, "lon": lon, "units": units, "description": desc, "temp": temp, "tmin": tmin, "tmax": tmax}
            _cache_weather[cache_key] = {"ts": now, "data": out}
            return out
    except Exception:
        pass

    # Try One Call 2.5
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/onecall",
            params={"lat": lat, "lon": lon, "units": units, "exclude": "minutely,hourly,alerts", "appid": _weather_api_key},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            current = data.get("current", {})
            daily = (data.get("daily") or [{}])[0]
            desc = (current.get("weather") or daily.get("weather") or [{}])[0].get("description", "n/a").title()
            temp = current.get("temp")
            tmin = daily.get("temp", {}).get("min", temp)
            tmax = daily.get("temp", {}).get("max", temp)
            out = {"lat": lat, "lon": lon, "units": units, "description": desc, "temp": temp, "tmin": tmin, "tmax": tmax}
            _cache_weather[cache_key] = {"ts": now, "data": out}
            return out
    except Exception:
        pass

    # Fallback: /weather + /forecast (derive min/max)
    try:
        wr = requests.get("https://api.openweathermap.org/data/2.5/weather",
                          params={"lat": lat, "lon": lon, "units": units, "appid": _weather_api_key},
                          timeout=10)
        fr = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                          params={"lat": lat, "lon": lon, "units": units, "appid": _weather_api_key},
                          timeout=10)
        if wr.status_code == 200:
            wj = wr.json()
            desc = (wj.get("weather") or [{}])[0].get("description", "n/a").title()
            temp = (wj.get("main") or {}).get("temp")
            tmin, tmax = temp, temp
            if fr.status_code == 200:
                fj = fr.json()
                temps = [item.get("main", {}).get("temp") for item in (fj.get("list") or []) if item.get("main")]
                temps = [t for t in temps if isinstance(t, (int, float))]
                if temps:
                    tmin, tmax = min(temps), max(temps)
            out = {"lat": lat, "lon": lon, "units": units, "description": desc, "temp": temp, "tmin": tmin, "tmax": tmax}
            _cache_weather[cache_key] = {"ts": now, "data": out}
            return out
    except Exception:
        pass

    raise RuntimeError("OpenWeatherMap request failed")

# ----------------------------
# Dad jokes (timeout + retry + cache + fallbacks)
# ----------------------------
def _fetch_dad_joke_once() -> Optional[str]:
    try:
        headers = {"Accept": "application/json", "User-Agent": "family-display/1.0"}
        r = requests.get(_joke_api_url, headers=headers, timeout=3)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and ct.startswith("application/json"):
            j = r.json()
            return j.get("joke") or (j.get("setup","") + (" " + j.get("delivery","") if j.get("delivery") else "")).strip() or None
        elif r.status_code == 200:
            return (r.text or "").strip() or None
    except Exception:
        return None
    return None

def fetch_dad_joke() -> str:
    now = time.time()
    if _cache_joke["joke"] and now - _cache_joke["ts"] < JOKE_TTL:
        return _cache_joke["joke"]
    joke = _fetch_dad_joke_once()
    if joke is None:
        time.sleep(0.5)
        joke = _fetch_dad_joke_once()
    if joke is None:
        joke = random.choice(FALLBACK_JOKES)
        print(f"[WARN] Dad joke fetch failed, using fallback: {joke}")
    _cache_joke["joke"] = joke
    _cache_joke["ts"] = now
    return joke

# ----------------------------
# Drawing helpers / layouts
# ----------------------------
def draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, box, font: ImageFont.ImageFont, fill=(0,0,0), line_spacing=6):
    x0, y0, x1, y1 = box
    max_width = x1 - x0
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    y = y0
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        h = bbox[3]-bbox[1]
        if y + h > y1:
            break
        draw.text((x0, y), line, fill=fill, font=font)
        y += h + line_spacing

def rounded_rectangle(draw: ImageDraw.ImageDraw, box: Tuple[int,int,int,int], radius: int, fill, outline=None, width: int=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def glass_panel(img: Image.Image, box: Tuple[int,int,int,int], blur_radius=6, opacity=220, radius=14):
    x0, y0, x1, y1 = box
    region = img.crop(box).filter(ImageFilter.GaussianBlur(blur_radius))
    overlay = Image.new("RGBA", (x1-x0, y1-y0), (255,255,255,opacity))
    region = region.convert("RGBA")
    region.alpha_composite(overlay)
    img.paste(region.convert("RGB"), (x0, y0))
    draw = ImageDraw.Draw(img)
    rounded_rectangle(draw, box, radius=radius, fill=None, outline=(0,0,0), width=1)

def card_panel(img: Image.Image, box: Tuple[int,int,int,int], radius=14):
    draw = ImageDraw.Draw(img)
    rounded_rectangle(draw, box, radius=radius, fill=(255,255,255), outline=(0,0,0), width=1)

def outline_panel(img: Image.Image, box: Tuple[int,int,int,int], radius=14):
    draw = ImageDraw.Draw(img)
    rounded_rectangle(draw, box, radius=radius, fill=None, outline=(0,0,0), width=2)

def add_text_panel(img: Image.Image, box: Tuple[int,int,int,int], layout: str):
    if layout == "glass":
        glass_panel(img, box, blur_radius=6, opacity=220, radius=14)
    elif layout == "card":
        card_panel(img, box, radius=14)
    elif layout == "outline":
        outline_panel(img, box, radius=14)

def add_date_label(img: Image.Image, layout: str):
    draw = ImageDraw.Draw(img)
    date_str = datetime.now().strftime("%a %d %b %Y")
    padding = 10
    text_w = int(draw.textlength(date_str, font=FONT_DATE))
    text_h = draw.textbbox((0,0), date_str, font=FONT_DATE)[3] - draw.textbbox((0,0), date_str, font=FONT_DATE)[1]
    box = (img.width - text_w - padding*2 - 12, 12, img.width - 12, 12 + text_h + padding*2)
    if layout in ("glass", "card", "outline"):
        add_text_panel(img, box, layout)
    draw.text((box[0]+padding, box[1]+padding), date_str, fill=(0,0,0), font=FONT_DATE)

def overlay_weather_layout(img: Image.Image, city: Optional[str], units: str, layout: str) -> Image.Image:
    try:
        wx = fetch_weather(city=city, units=units)
    except Exception:
        return img
    draw = ImageDraw.Draw(img)
    strip_h = 64
    box = (12, img.height - strip_h - 12, img.width - 12, img.height - 12)
    add_text_panel(img, box, layout)
    title = f"{city or 'Weather'}: {wx['description']}"
    temps = f"Min {round(wx['tmin'])}° / Max {round(wx['tmax'])}°{'C' if units=='metric' else 'F'}"
    draw.text((box[0]+14, box[1]+10), title, fill=(0,0,0), font=FONT_BOLD)
    draw.text((box[0]+14, box[1]+36), temps, fill=(0,0,0), font=FONT_REG)
    return img

def add_dad_joke_layout(img: Image.Image, layout: str, above: int = 0) -> Image.Image:
    draw = ImageDraw.Draw(img)
    joke_h = 110
    bottom_margin = 12 + above
    box = (12, img.height - bottom_margin - joke_h, img.width - 12, img.height - bottom_margin)
    add_text_panel(img, box, layout)
    text_box = (box[0]+14, box[1]+10, box[2]-14, box[3]-10)
    joke_text = fetch_dad_joke()
    draw_wrapped_text(draw, joke_text, text_box, font=FONT_REG, fill=(0,0,0), line_spacing=6)
    return img

def _img_to_bytes(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

# ----------------------------
# Routes
# ----------------------------
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    flags = [
        "ok",
        f"gcs={'on' if get_bucket() else 'off'}",
        f"gen={'deepai' if _DEEPAI_KEY else ('hf' if _hf_token else 'none')}",
        f"weather={'on' if _weather_api_key else 'off'}",
        f"fonts={'on' if isinstance(FONT_REG, ImageFont.FreeTypeFont) else 'off'}",
        f"default_layout=glass",
    ]
    return " ".join(flags)

@app.get("/v1/frame")
def v1_frame(
    request: Request,
    day: Optional[int] = None,
    variant: Optional[int] = None,
    overlay_wx: bool = Query(False, description="Show weather panel"),
    city: Optional[str] = None,
    units: str = "metric",
    joke: bool = Query(True, description="Show dad joke panel"),
    layout: str = Query("glass", description="glass|card|outline|minimal|poster")
):
    day_idx = day if day is not None else datetime.utcnow().weekday()
    var_idx = variant if variant is not None else random.randint(0, 3)

    img_bytes, key = fetch_from_gcs(day_idx, var_idx)
    source = "gcs" if img_bytes else "fallback"
    if img_bytes is None:
        img_bytes, key = local_fallback(day_idx, var_idx)

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    add_date_label(img, layout)

    if joke and overlay_wx:
        img = overlay_weather_layout(img, city=city, units=units, layout=layout)
        img = add_dad_joke_layout(img, layout=layout, above=64 + 12)
    elif joke:
        img = add_dad_joke_layout(img, layout=layout, above=0)
    elif overlay_wx:
        img = overlay_weather_layout(img, city=city, units=units, layout=layout)

    out = io.BytesIO()
    img.save(out, format="PNG")
    content = out.getvalue()

    etag = hashlib.sha1(content).hexdigest()
    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        return Response(status_code=304)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300",
        "X-Image-Source": source,
        "X-Image-Key": key or "",
    }
    return Response(content=content, media_type="image/png", headers=headers)

@app.get("/v1/weather")
def v1_weather(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, units: str="metric"):
    try:
        data = fetch_weather(city=city, lat=lat, lon=lon, units=units)
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/generate")
def admin_generate(
    prompt: str = Body(..., embed=True),
    day: int = Body(default=None),
    variants: int = Body(default=4),
    store: str = Body(default="weekly")
):
    if variants < 1 or variants > 8:
        variants = max(1, min(variants, 8))
    day_idx = day if day is not None else datetime.utcnow().weekday()

    results: List[Dict[str, Any]] = []
    for i in range(variants):
        try:
            raw = generate_image_bytes(prompt)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = cover_resize_to(img, 800, 480)
            out_b = io.BytesIO()
            img.save(out_b, format="PNG")
            out_bytes = out_b.getvalue()

            key = f"{store}/{day_idx}_{i}.png"
            saved = put_to_gcs(key, out_bytes)
            if not saved:
                local_dir = os.path.join(os.path.dirname(__file__), "fallback_art")
                os.makedirs(local_dir, exist_ok=True)
                with open(os.path.join(local_dir, f"{day_idx}_{i}.png"), "wb") as f:
                    f.write(out_bytes)
            results.append({"variant": i, "key": key, "saved_to_gcs": saved, "provider": _provider})
        except Exception as e:
            results.append({"variant": i, "error": str(e), "provider": _provider})
    return {"day": day_idx, "variants": results}

@app.get("/")
def root():
    return {
        "status": "ok",
        "version": "deepai-layouts-jokes-2025-10-24",
        "gcs": bool(get_bucket()),
        "gen_provider": "deepai" if _DEEPAI_KEY else ("hf" if _hf_token else "none"),
        "hf_model": _hf_model if _hf_token else None,
        "weather": bool(_weather_api_key),
        "default_layout": "glass"
    }