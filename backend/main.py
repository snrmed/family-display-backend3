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
    (255, 255, 255),
    (0, 0, 0),
    (255, 0, 0),
    (255, 255, 0),
    (0, 0, 255),
    (0, 128, 0),
]

app = FastAPI()

_bucket = None
_bucket_name = os.getenv("GCS_BUCKET_NAME")

_provider = os.getenv("GEN_PROVIDER", "deepai").lower()
_DEEPAI_KEY = os.getenv("DEEPAI_API_KEY")
_DEEPAI_URL = "https://api.deepai.org/api/text2img"

_hf_token = os.getenv("HUGGING_FACE_TOKEN") or os.getenv("HF_TOKEN")
_hf_model = os.getenv("HF_MODEL", "stabilityai/sd-turbo")

_weather_api_key = os.getenv("WEATHER_API_KEY") or os.getenv("OWM_API_KEY")
_joke_api_url = os.getenv("JOKE_API_URL", "https://icanhazdadjoke.com/")

_cache_weather: Dict[str, Dict[str, Any]] = {}
_cache_joke: Dict[str, Any] = {"ts": 0, "joke": None}
WEATHER_TTL = int(os.getenv("WEATHER_TTL_SECONDS", "900"))
JOKE_TTL = int(os.getenv("JOKE_TTL_SECONDS", "900"))

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

# ----------------------------
# Themed prompts for DeepAI
# ----------------------------
THEME_PROMPTS = [
    "Colorful geometric poster art with soft gradients and organic shapes, abstract paper-collage style. Modern minimalist design, bright clean palette, flat illustration suitable for e-ink background.",
    "Abstract nature illustration with stylized sun, hills and sky. Bright flat colors, mid-century modern poster style, simple geometry.",
    "Blue-themed abstract poster with waves and circles, geometric sea and sun, vivid modern palette, clean minimal layout.",
    "Playful abstract art with circles, triangles and paper-cut textures, cheerful family vibe, bright flat vector look.",
    "Soft pastel minimalist abstract poster, simple geometric forms and generous negative space, Japanese zen design.",
    "Retro-tech geometric poster: grids, circles and lines, neon-pastel palette, futuristic retro feel.",
    "Warm sunset palette abstract landscape: layered hills, sun disc, smooth gradients, poster art style.",
    "Memphis design inspired abstract: bold shapes, dots, squiggles, high-contrast flat colors, graphic poster."
]

# ----------------------------
# Fonts
# ----------------------------
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def load_font(fname: str, size: int):
    path = os.path.join(FONT_DIR, fname)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

FONT_REG = load_font("Roboto-Regular.ttf", 26)
FONT_BOLD = load_font("Roboto-Bold.ttf", 32)
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
# Generators
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

def generate_image_bytes(prompt: str) -> bytes:
    try:
        return deepai_text2image(prompt)
    except Exception as e:
        print(f"[WARN] DeepAI failed: {e}")
        raise

# ----------------------------
# Weather + Dad jokes
# ----------------------------
def fetch_weather(city="Darwin", units="metric"):
    if not _weather_api_key:
        raise RuntimeError("WEATHER_API_KEY not set")
    try:
        geo = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                           params={"q": city, "limit": 1, "appid": _weather_api_key}, timeout=5)
        lat, lon = geo.json()[0]["lat"], geo.json()[0]["lon"]
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"lat": lat, "lon": lon, "units": units, "appid": _weather_api_key}, timeout=5)
        data = r.json()
        desc = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        return {"description": desc, "temp": temp}
    except Exception:
        raise RuntimeError("Weather fetch failed")

def fetch_dad_joke() -> str:
    now = time.time()
    if _cache_joke["joke"] and now - _cache_joke["ts"] < JOKE_TTL:
        return _cache_joke["joke"]
    try:
        headers = {"Accept": "application/json", "User-Agent": "family-display/1.0"}
        r = requests.get(_joke_api_url, headers=headers, timeout=3)
        if r.status_code == 200:
            j = r.json()
            joke = j.get("joke") or j.get("setup", "")
            _cache_joke.update({"joke": joke, "ts": now})
            return joke
    except Exception:
        pass
    joke = random.choice(FALLBACK_JOKES)
    _cache_joke.update({"joke": joke, "ts": now})
    return joke

# ----------------------------
# Drawing helpers
# ----------------------------
def draw_wrapped_text(draw, text, box, font, fill=(0,0,0), line_spacing=6):
    x0, y0, x1, y1 = box
    max_width = x1 - x0
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            lines.append(current)
            current = w
    if current: lines.append(current)
    y = y0
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        h = bbox[3]-bbox[1]
        if y + h > y1: break
        draw.text((x0, y), line, fill=fill, font=font)
        y += h + line_spacing

def glass_panel(img, box, blur_radius=6, opacity=220, radius=14):
    x0, y0, x1, y1 = box
    region = img.crop(box).filter(ImageFilter.GaussianBlur(blur_radius))
    overlay = Image.new("RGBA", (x1-x0, y1-y0), (255,255,255,opacity))
    region = region.convert("RGBA")
    region.alpha_composite(overlay)
    img.paste(region.convert("RGB"), (x0, y0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box, radius=radius, outline=(0,0,0), width=1)

def add_date_label(img):
    draw = ImageDraw.Draw(img)
    date_str = datetime.now().strftime("%a %d %b %Y")
    padding = 10
    text_w = int(draw.textlength(date_str, font=FONT_DATE))
    text_h = draw.textbbox((0,0), date_str, font=FONT_DATE)[3]
    box = (img.width - text_w - padding*2 - 12, 12, img.width - 12, 12 + text_h + padding*2)
    glass_panel(img, box)
    draw.text((box[0]+padding, box[1]+padding), date_str, fill=(0,0,0), font=FONT_DATE)

def overlay_weather_and_joke(img, city="Darwin"):
    draw = ImageDraw.Draw(img)
    try:
        wx = fetch_weather(city)
        joke = fetch_dad_joke()
    except Exception:
        wx = {"description":"Sunny","temp":33}
        joke = random.choice(FALLBACK_JOKES)
    # Weather panel
    box_w = (12, img.height - 130, img.width - 12, img.height - 70)
    glass_panel(img, box_w)
    draw.text((box_w[0]+14, box_w[1]+10),
              f"{city}: {wx['description']} {round(wx['temp'])}°C",
              fill=(0,0,0), font=FONT_BOLD)
    # Joke panel
    box_j = (12, img.height - 60, img.width - 12, img.height - 12)
    glass_panel(img, box_j)
    draw_wrapped_text(draw, joke, (box_j[0]+14, box_j[1]+10, box_j[2]-14, box_j[3]-10),
                      font=FONT_REG, fill=(0,0,0))
    return img

# ----------------------------
# Routes
# ----------------------------
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok deepai-themed"

@app.post("/admin/generate")
def admin_generate(
    prompt: Optional[str] = Body(default=None, embed=True),
    day: int = Body(default=None),
    variants: int = Body(default=4),
    store: str = Body(default="weekly")
):
    if variants < 1 or variants > 8:
        variants = max(1, min(variants, 8))
    day_idx = day if day is not None else datetime.utcnow().weekday()

    used_prompt = prompt if (prompt and prompt.strip().lower() != "auto") else random.choice(THEME_PROMPTS)
    results: List[Dict[str, Any]] = []

    for i in range(variants):
        try:
            raw = generate_image_bytes(used_prompt)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = cover_resize_to(img, 800, 480)
            add_date_label(img)
            overlay_weather_and_joke(img)

            out_b = io.BytesIO()
            img.save(out_b, format="PNG")
            out_bytes = out_b.getvalue()

            key = f"{store}/{day_idx}_{i}.png"
            saved = put_to_gcs(key, out_bytes)
            results.append({"variant": i, "key": key, "saved_to_gcs": saved, "provider": _provider})
        except Exception as e:
            results.append({"variant": i, "error": str(e), "provider": _provider})
    return {"day": day_idx, "used_prompt": used_prompt, "variants": results}

@app.get("/")
def root():
    return {
        "status": "ok",
        "version": "deepai-themed-2025-10-25",
        "gcs": bool(get_bucket()),
        "provider": "deepai",
        "weather": bool(_weather_api_key),
        "default_layout": "glass"
    }