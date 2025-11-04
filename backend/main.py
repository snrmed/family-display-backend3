import os
import json
import random
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.cloud import storage
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kin:D Family Display Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = int(os.getenv("PORT", "8080"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "family-display-packs")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "adm_860510")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
ENABLE_RENDERING = os.getenv("ENABLE_RENDERING", "true").lower() == "true"
ENABLE_PEXELS = os.getenv("ENABLE_PEXELS", "true").lower() == "true"
ENABLE_OPENWEATHER = os.getenv("ENABLE_OPENWEATHER", "true").lower() == "true"
ENABLE_JOKES_API = os.getenv("ENABLE_JOKES_API", "true").lower() == "true"
ENABLE_EMAIL_USERS = os.getenv("ENABLE_EMAIL_USERS", "false").lower() == "true"
CITY_MODE = os.getenv("CITY_MODE", "default")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Darwin")
OPENWEATHER_ICON_BASE = "https://openweathermap.org/img/wn"
OPENWEATHER_ICON_SCALE = os.getenv("OPENWEATHER_ICON_SCALE", "@4x")
FALLBACK_WEATHER_ICON = "designer/svgs/weather_card_blue.svg"
RENDER_WIDTH = int(os.getenv("RENDER_WIDTH", "800"))
RENDER_HEIGHT = int(os.getenv("RENDER_HEIGHT", "480"))
RENDER_PATH = os.getenv("RENDER_PATH", "backend/web/layouts/base.html")

_DEFAULT_PEXELS_CATEGORIES = [
    "abstract",
    "geometric",
    "kids-shapes",
    "minimal",
    "paper-collage",
]
PEXELS_CATEGORIES = [
    c.strip()
    for c in os.getenv("PEXELS_CATEGORIES", ",".join(_DEFAULT_PEXELS_CATEGORIES)).split(",")
    if c.strip()
]
PEXELS_PER_CATEGORY = int(os.getenv("PEXELS_PER_CATEGORY", "8"))
PEXELS_ORIENTATION = os.getenv("PEXELS_ORIENTATION", "landscape")
PEXELS_IMAGE_SIZE = os.getenv("PEXELS_IMAGE_SIZE", "large")

storage_enabled = False
gcs_bucket = None
playwright_browser = None

try:
    storage_client = storage.Client()
    gcs_bucket = storage_client.bucket(GCS_BUCKET)
    storage_enabled = True
    logger.info(f"✓ GCS enabled: {GCS_BUCKET}")
except Exception as e:
    logger.warning(f"⚠️  GCS disabled: {e}")

if ENABLE_RENDERING:
    try:
        from playwright.async_api import async_playwright
        playwright = None
        playwright_browser = None
        
        @app.on_event("startup")
        async def startup():
            global playwright, playwright_browser
            playwright = await async_playwright().start()
            playwright_browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            logger.info("✓ Playwright browser started")
        
        @app.on_event("shutdown")
        async def shutdown():
            if playwright_browser:
                await playwright_browser.close()
            if playwright:
                await playwright.stop()
            logger.info("✓ Playwright stopped")
    except ImportError:
        logger.warning("⚠️  Playwright not available")
        ENABLE_RENDERING = False

LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I'm reading a book about anti-gravity. It's impossible to put down!",
    "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them.",
    "Why do we tell actors to 'break a leg?' Because every play has a cast.",
    "Helvetica and Times New Roman walk into a bar. 'Get out of here!' shouts the bartender. 'We don't serve your type.'",
    "Yesterday I saw a guy spill all his Scrabble letters on the road. I asked him, 'What's the word on the street?'",
    "What do you call a factory that makes okay products? A satisfactory.",
    "I used to hate facial hair, but then it grew on me.",
]

def make_public_url(path: str) -> str:
    """Build full public URL for assets"""
    if path.startswith("http"):
        return path
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else f"http://localhost:{PORT}"
    return f"{base}/{path.lstrip('/')}"


def get_pexels_categories() -> list[str]:
    """Return list of configured or discovered Pexels categories"""
    categories = set(PEXELS_CATEGORIES)

    if storage_enabled and ENABLE_PEXELS:
        try:
            blobs = gcs_bucket.list_blobs(prefix="pexels/current/", delimiter="/")
            prefixes: list[str] = []
            for page in blobs.pages:
                prefixes.extend(page.prefixes)
            for prefix in prefixes:
                name = prefix.rstrip("/").split("/")[-1]
                if name:
                    categories.add(name)
        except Exception as exc:
            logger.warning(f"Failed to list Pexels categories: {exc}")

    if not categories:
        categories = set(_DEFAULT_PEXELS_CATEGORIES)

    return sorted(categories)


def _list_pexels_objects(category: str) -> list[str]:
    """List blob names for a category under pexels/current"""
    if not storage_enabled or not ENABLE_PEXELS:
        return []

    safe_category = category.strip("/")
    prefix = f"pexels/current/{safe_category}/"
    names: list[str] = []

    try:
        blobs = gcs_bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            if blob.size == 0:
                continue
            names.append(blob.name)
    except Exception as exc:
        logger.warning(f"Failed to list Pexels objects for {category}: {exc}")

    return names


def choose_pexels_background(category: str | None) -> dict | None:
    """Select a random background image for the requested category"""
    if not ENABLE_PEXELS or not storage_enabled:
        return None

    categories = get_pexels_categories()
    if not categories:
        return None

    selected_category = category or ""
    if selected_category not in categories:
        selected_category = categories[0]

    blob_names = _list_pexels_objects(selected_category)

    if not blob_names:
        # Fallback to the first category that has files
        for fallback in categories:
            blob_names = _list_pexels_objects(fallback)
            if blob_names:
                selected_category = fallback
                break

    if not blob_names:
        return None

    blob_name = random.choice(blob_names)
    image_name = Path(blob_name).name
    public_path = f"gcs/{blob_name}"

    return {
        "category": selected_category,
        "image": image_name,
        "path": public_path,
        "url": make_public_url(public_path),
        "categories": categories,
    }


def _openweather_icon_filename(icon_code: str) -> str:
    scale = OPENWEATHER_ICON_SCALE or "@4x"
    if not scale.startswith("@"):
        scale = f"@{scale}"
    return f"{icon_code}{scale}.png"


async def _fetch_and_cache_openweather_icon(
    client: httpx.AsyncClient, icon_code: str
) -> str | None:
    """Ensure an OpenWeather icon is cached and return its public URL."""

    filename = _openweather_icon_filename(icon_code)
    blob_path = f"icons/openweather/{filename}"
    public_path = f"gcs/{blob_path}"

    if storage_enabled:
        try:
            blob = gcs_bucket.blob(blob_path)
            if blob.exists():
                return make_public_url(public_path)
        except Exception as exc:
            logger.warning(f"Failed to inspect cached icon {blob_path}: {exc}")

    if not storage_enabled:
        return f"{OPENWEATHER_ICON_BASE}/{filename}"

    icon_url = f"{OPENWEATHER_ICON_BASE}/{filename}"

    try:
        response = await client.get(icon_url, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"OpenWeather icon fetch failed for {icon_code}: {exc}")
        return None

    try:
        gcs_write_bytes(blob_path, response.content, "image/png")
        return make_public_url(public_path)
    except Exception as exc:
        logger.warning(f"Failed to cache OpenWeather icon {icon_code}: {exc}")
        return icon_url


async def resolve_openweather_icon(
    client: httpx.AsyncClient, icon_code: str | None
) -> str:
    """Resolve an icon URL, preferring cached copies then day variants."""

    candidates: list[str] = []

    if icon_code:
        candidates.append(icon_code)
        if icon_code.endswith("n"):
            candidates.append(icon_code[:-1] + "d")

    if "01d" not in candidates:
        candidates.append("01d")

    for code in candidates:
        cached = await _fetch_and_cache_openweather_icon(client, code)
        if cached:
            return cached

    return make_public_url(FALLBACK_WEATHER_ICON)


def rollover_pexels_current(categories: list[str], date_stamp: str) -> dict[str, int]:
    """Move current images to cache/date/category"""
    moved: dict[str, int] = {category: 0 for category in categories}

    if not storage_enabled or not ENABLE_PEXELS:
        return moved

    for category in categories:
        prefix = f"pexels/current/{category.strip('/')}/"
        cache_prefix = f"pexels/cache/{date_stamp}/{category.strip('/')}/"

        try:
            blobs = gcs_bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                if blob.name.endswith("/") or blob.size == 0:
                    continue
                destination = cache_prefix + Path(blob.name).name
                gcs_bucket.copy_blob(blob, gcs_bucket, destination)
                blob.delete()
                moved[category] += 1
        except Exception as exc:
            logger.warning(f"Failed to rollover Pexels images for {category}: {exc}")

    return moved


async def fetch_pexels_category(
    client: httpx.AsyncClient,
    category: str,
    api_key: str,
) -> tuple[int, list[str]]:
    """Fetch new images for a category and upload to GCS"""
    headers = {"Authorization": api_key}
    params = {
        "query": category.replace("-", " "),
        "per_page": max(1, PEXELS_PER_CATEGORY),
        "orientation": PEXELS_ORIENTATION,
        "size": PEXELS_IMAGE_SIZE,
    }

    saved_files: list[str] = []

    try:
        response = await client.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.error(f"Pexels search failed for {category}: {exc}")
        return 0, saved_files

    data = response.json()
    photos = data.get("photos", [])
    if not photos:
        logger.warning(f"No Pexels photos returned for {category}")
        return 0, saved_files

    random.shuffle(photos)
    selected = photos[: PEXELS_PER_CATEGORY]

    for index, photo in enumerate(selected):
        src = photo.get("src", {})
        image_url = src.get("landscape") or src.get("large") or src.get("large2x")
        if not image_url:
            continue

        filename = f"{category}_{photo.get('id', index)}.jpg"
        object_name = f"pexels/current/{category}/{filename}"

        try:
            image_response = await client.get(image_url, timeout=30)
            image_response.raise_for_status()
            gcs_write_bytes(object_name, image_response.content, "image/jpeg")
            saved_files.append(object_name)
        except Exception as exc:
            logger.warning(f"Failed to download Pexels image {image_url}: {exc}")

    return len(saved_files), saved_files


async def refresh_pexels_assets(categories: list[str]) -> dict[str, dict[str, int | list[str]]]:
    """Rollover current images and fetch new ones for each category"""
    summary: dict[str, dict[str, int | list[str]]] = {}

    if not storage_enabled or not ENABLE_PEXELS:
        return summary

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY not configured")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    rollover_counts = rollover_pexels_current(categories, today)

    async with httpx.AsyncClient() as client:
        for category in categories:
            downloaded, files = await fetch_pexels_category(client, category, api_key)
            summary[category] = {
                "rolled": rollover_counts.get(category, 0),
                "downloaded": downloaded,
                "files": files,
            }

    return summary


def gcs_read_json(key: str) -> dict:
    """Read JSON from GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = gcs_bucket.blob(key)
    if not blob.exists():
        raise FileNotFoundError(f"Blob not found: {key}")
    return json.loads(blob.download_as_text(encoding='utf-8'))

def gcs_write_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Write bytes to GCS"""
    if not storage_enabled:
        raise RuntimeError("GCS not enabled")
    blob = gcs_bucket.blob(key)
    blob.upload_from_string(data, content_type=content_type)
    logger.info(f"✓ Wrote {len(data)} bytes to {key}")

async def get_weather(city: str) -> dict:
    """Get weather data"""
    if ENABLE_OPENWEATHER:
        api_key = os.getenv("OPENWEATHER_KEY")
        if api_key:
            try:
                async with httpx.AsyncClient() as client:
                    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
                    r = await client.get(url, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        main_block = data.get("main", {})
                        wind_block = data.get("wind", {})
                        rain_block = data.get("rain", {})

                        temp_val = main_block.get("temp")
                        feels_like_val = main_block.get("feels_like")
                        humidity_val = main_block.get("humidity")

                        wind_speed = wind_block.get("speed")
                        wind_kmh = None
                        if isinstance(wind_speed, (int, float)):
                            wind_kmh = round(float(wind_speed) * 3.6)

                        rain_amount: float | None = None
                        rain_1h = rain_block.get("1h")
                        rain_3h = rain_block.get("3h")
                        if isinstance(rain_1h, (int, float)):
                            rain_amount = float(rain_1h)
                        elif isinstance(rain_3h, (int, float)):
                            rain_amount = float(rain_3h) / 3.0

                        if rain_amount is not None:
                            rain_amount = round(rain_amount, 1)
                            if rain_amount.is_integer():
                                rain_amount = int(rain_amount)

                        weather: dict[str, Any] = {
                            "temp": round(temp_val) if isinstance(temp_val, (int, float)) else None,
                            "feels_like": round(feels_like_val) if isinstance(feels_like_val, (int, float)) else None,
                            "humidity": int(humidity_val) if isinstance(humidity_val, (int, float)) else None,
                            "rain": rain_amount,
                            "wind": wind_kmh,
                            "icon": data.get("weather", [{}])[0].get("icon", "01d"),
                            "desc": data.get("weather", [{}])[0].get("description", "").title() or "Sunny",
                        }

                        name = data.get("name")
                        if isinstance(name, str) and name.strip():
                            weather["city"] = name.strip()

                        country_code = data.get("sys", {}).get("country")
                        if isinstance(country_code, str) and country_code.strip():
                            weather["country_code"] = country_code.strip()

                        weather["icon_url"] = await resolve_openweather_icon(
                            client, weather.get("icon")
                        )

                        tz_offset = data.get("timezone", 0)
                        weather["timezone_offset"] = tz_offset

                        coord = data.get("coord", {})
                        lat = coord.get("lat")
                        lon = coord.get("lon")

                        if lat is not None and lon is not None:
                            try:
                                forecast_url = (
                                    "https://api.openweathermap.org/data/2.5/forecast"
                                    f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
                                )
                                forecast_resp = await client.get(forecast_url, timeout=5)
                                forecast_resp.raise_for_status()
                                forecast_data = forecast_resp.json()

                                target_date = (
                                    datetime.now(timezone.utc)
                                    .astimezone(timezone(timedelta(seconds=tz_offset)))
                                    .date()
                                )

                                min_samples: list[float] = []
                                max_samples: list[float] = []

                                local_timezone = timezone(timedelta(seconds=tz_offset))

                                for entry in forecast_data.get("list", []):
                                    dt_val = entry.get("dt")
                                    if dt_val is None:
                                        continue

                                    local_dt = datetime.fromtimestamp(dt_val, tz=timezone.utc).astimezone(local_timezone)
                                    if local_dt.date() != target_date:
                                        continue

                                    main_block = entry.get("main", {})
                                    min_val = main_block.get("temp_min")
                                    max_val = main_block.get("temp_max")

                                    if isinstance(min_val, (int, float)):
                                        min_samples.append(float(min_val))
                                    if isinstance(max_val, (int, float)):
                                        max_samples.append(float(max_val))

                                if min_samples:
                                    weather["temp_min"] = round(sum(min_samples) / len(min_samples))
                                else:
                                    api_min = data.get("main", {}).get("temp_min")
                                    if isinstance(api_min, (int, float)):
                                        weather["temp_min"] = round(api_min)

                                if max_samples:
                                    weather["temp_max"] = round(sum(max_samples) / len(max_samples))
                                else:
                                    api_max = data.get("main", {}).get("temp_max")
                                    if isinstance(api_max, (int, float)):
                                        weather["temp_max"] = round(api_max)
                            except Exception as exc:
                                logger.warning(f"OpenWeather forecast failed: {exc}")
                                api_min = data.get("main", {}).get("temp_min")
                                api_max = data.get("main", {}).get("temp_max")
                                if isinstance(api_min, (int, float)):
                                    weather["temp_min"] = round(api_min)
                                if isinstance(api_max, (int, float)):
                                    weather["temp_max"] = round(api_max)

                        if "temp_min" not in weather:
                            weather["temp_min"] = weather["temp"]
                        if "temp_max" not in weather:
                            weather["temp_max"] = weather["temp"]

                        comment_bits: list[str] = []
                        if weather.get("desc"):
                            comment_bits.append(weather["desc"])
                        feels_like = weather.get("feels_like")
                        if isinstance(feels_like, (int, float)):
                            comment_bits.append(f"Feels like {feels_like}°C")
                        humidity = weather.get("humidity")
                        if isinstance(humidity, (int, float)):
                            comment_bits.append(f"Humidity {int(humidity)}%")
                        if isinstance(wind_kmh, (int, float)):
                            comment_bits.append(f"Winds {int(wind_kmh)} km/h")
                        rain_amt = weather.get("rain")
                        if isinstance(rain_amt, (int, float)) and rain_amt > 0:
                            comment_bits.append(f"Rain {rain_amt} mm")
                        if comment_bits:
                            weather["comment"] = " · ".join(comment_bits)
                        else:
                            weather["comment"] = weather.get("desc", "") or "Sunny"

                        return weather
            except Exception as e:
                logger.warning(f"OpenWeather failed: {e}")

    return {
        "temp": 33,
        "feels_like": 33,
        "humidity": 45,
        "rain": 0,
        "wind": 5,
        "icon": "01d",
        "desc": "Sunny",
        "temp_min": 30,
        "temp_max": 36,
        "timezone_offset": 0,
        "icon_url": make_public_url(FALLBACK_WEATHER_ICON),
        "comment": "Sunny · Feels like 33°C · Humidity 45% · Winds 5 km/h",
    }

async def get_joke() -> str:
    """Get dad joke"""
    if ENABLE_JOKES_API:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://icanhazdadjoke.com/",
                    headers={"Accept": "application/json"},
                    timeout=5
                )
                if r.status_code == 200:
                    return r.json()["joke"]
        except Exception as e:
            logger.warning(f"Joke API failed: {e}")
    
    return random.choice(LOCAL_JOKES)

async def build_render_data(device: str = "familydisplay") -> dict:
    """Build complete data context for rendering"""
    
    if ENABLE_EMAIL_USERS:
        layout_key = f"users/default/devices/{device}/layouts/current.json"
    else:
        layout_key = f"layouts/{device}.json"
    
    try:
        layout = gcs_read_json(layout_key)
    except:
        logger.warning(f"Layout not found: {layout_key}, using default")
        layout = {
            "name": "default",
            "meta": {},
            "elements": []
        }
    
    layout_meta = layout.get("meta", {}) if isinstance(layout, dict) else {}

    layout_city = layout_meta.get("city")
    layout_country = (
        layout_meta.get("countryCode")
        or layout_meta.get("country_code")
        or layout_meta.get("country")
    )
    layout_country_name = layout_meta.get("countryName") or layout_meta.get("country_name")
    layout_timezone = layout_meta.get("timezone") or layout_meta.get("timeZone")

    city_lookup = DEFAULT_CITY
    if CITY_MODE == "fetch" and layout_city:
        city_lookup = layout_city
    if CITY_MODE == "fetch" and layout_city and layout_country:
        city_lookup = f"{layout_city},{layout_country}"

    weather = await get_weather(city_lookup)
    if not weather.get("icon_url"):
        weather["icon_url"] = make_public_url(FALLBACK_WEATHER_ICON)

    if layout_city:
        weather["city"] = layout_city
    elif not weather.get("city"):
        weather["city"] = (city_lookup.split(",")[0]).strip()

    if layout_country:
        weather["country_code"] = layout_country
    if layout_country_name:
        weather["country_name"] = layout_country_name

    tz_offset = weather.get("timezone_offset")
    now_utc = datetime.now(timezone.utc)
    now = now_utc
    tz_identifier = None

    if isinstance(layout_timezone, str) and layout_timezone:
        try:
            tz = ZoneInfo(layout_timezone)
            now = now_utc.astimezone(tz)
            tz_identifier = layout_timezone
            offset_seconds = now.utcoffset().total_seconds() if now.utcoffset() else None
            if offset_seconds is not None:
                weather["timezone_offset"] = int(offset_seconds)
        except Exception as exc:
            logger.warning(f"Failed to apply layout timezone {layout_timezone}: {exc}")

    if tz_identifier is None and isinstance(tz_offset, (int, float)):
        city_tz = timezone(timedelta(seconds=int(tz_offset)), name=weather.get("city") or "city")
        now = now_utc.astimezone(city_tz)
        tz_identifier = city_tz.tzname(now)

    if tz_identifier:
        weather["timezone_name"] = tz_identifier

    weather["local_datetime"] = now.isoformat()

    dad_joke = await get_joke()

    selected_category = layout_meta.get("pexelsCategory")
    pexels_info = None

    if ENABLE_PEXELS and storage_enabled:
        pexels_info = choose_pexels_background(selected_category)

    if pexels_info:
        bg_url = pexels_info["url"]
    else:
        bg_url = make_public_url("gcs/pexels/current/abstract_0.jpg")
        if ENABLE_PEXELS:
            categories = get_pexels_categories()
            pexels_info = {
                "category": selected_category or (categories[0] if categories else None),
                "image": None,
                "path": None,
                "url": bg_url,
                "categories": categories,
            }
    
    date_str = now.strftime("%a, %d %b")
    
    if storage_enabled:
        svg_base = make_public_url("gcs/assets/svgs")
    else:
        svg_base = make_public_url("designer/svgs")
    
    return {
        "layout": layout,
        "weather": weather,
        "dad_joke": dad_joke,
        "date": date_str,
        "bg_url": bg_url,
        "pexels": pexels_info,
        "svg_base": svg_base,
        "timestamp": now.isoformat()
    }

async def render_html_to_png(html_path: str, context: Dict[str, Any]) -> bytes:
    """Render base.html to PNG using Playwright"""
    if not ENABLE_RENDERING or playwright_browser is None:
        raise RuntimeError("Rendering disabled")
    
    page = await playwright_browser.new_page(
        viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}
    )
    
    raw_json = json.dumps(context)
    encoded_data = quote(raw_json, safe="")
    url = f"file://{os.path.abspath(html_path)}?data={encoded_data}"
    
    logger.info(f"🎨 Rendering: {url[:100]}...")
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=10000)
        await page.wait_for_timeout(1500)
        png_bytes = await page.screenshot(type="png", full_page=False)
        await page.close()
        logger.info(f"✅ Rendered {len(png_bytes)} bytes")
        return png_bytes
    except Exception as e:
        logger.error(f"Render failed: {e}")
        await page.close()
        raise

@app.get("/")
def root():
    return {
        "service": "Kin:D Family Display Backend",
        "status": "running",
        "features": {
            "rendering": ENABLE_RENDERING,
            "pexels": ENABLE_PEXELS,
            "openweather": ENABLE_OPENWEATHER,
            "jokes": ENABLE_JOKES_API,
            "gcs": storage_enabled
        }
    }

@app.get("/v1/render_data")
async def get_render_data(device: str = "familydisplay"):
    """Get render context data"""
    try:
        data = await build_render_data(device)
        return data
    except Exception as e:
        logger.error(f"Render data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/frame")
async def get_frame(device: str = "familydisplay"):
    """Render and return PNG frame"""
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Frame generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/render_now")
async def admin_render_now(device: str = "familydisplay", token: str = None):
    """Force render and save to GCS"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if not ENABLE_RENDERING:
        raise HTTPException(status_code=503, detail="Rendering disabled")
    
    try:
        context = await build_render_data(device)
        png_bytes = await render_html_to_png(RENDER_PATH, context)
        
        if ENABLE_EMAIL_USERS:
            render_key = f"users/default/devices/{device}/renders/latest.png"
        else:
            render_key = f"renders/{device}/latest.png"
        
        gcs_write_bytes(render_key, png_bytes, "image/png")
        
        return {
            "status": "rendered",
            "device": device,
            "size": len(png_bytes),
            "path": render_key
        }
    except Exception as e:
        logger.error(f"Admin render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gcs/{path:path}")
def get_gcs_asset(path: str):
    """Serve assets from GCS bucket"""
    if not storage_enabled:
        raise HTTPException(status_code=500, detail="GCS not configured")
    
    blob = gcs_bucket.blob(path)
    if not blob.exists():
        logger.warning(f"❌ Asset not found: {path}")
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    
    data = blob.download_as_bytes()
    
    if path.endswith(".svg"):
        ctype = "image/svg+xml"
    elif path.endswith(".png"):
        ctype = "image/png"
    elif path.endswith(".jpg") or path.endswith(".jpeg"):
        ctype = "image/jpeg"
    elif path.endswith(".json"):
        ctype = "application/json"
    else:
        ctype = "application/octet-stream"
    
    return Response(
        content=data,
        media_type=ctype,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )

def _discover_local_svgs() -> list[str]:
    search_dirs = [
        Path("backend/web/designer/svgs"),
        Path("web/designer/svgs"),
        Path("web/svgs"),
    ]
    for directory in search_dirs:
        if directory.exists():
            svgs = sorted([p.name for p in directory.glob("*.svg")])
            if svgs:
                return svgs
    return []


def _discover_local_presets() -> tuple[list[str], str | None]:
    search_dirs: list[tuple[Path, str]] = [
        (Path("backend/web/designer/presets"), "/designer/presets"),
        (Path("web/presets"), "/presets"),
        (Path("web/designer/presets"), "/web/designer/presets"),
    ]

    for directory, base_url in search_dirs:
        if not directory.exists():
            continue

        presets = sorted([p.stem for p in directory.glob("*.json")])
        if presets:
            return presets, base_url

    return [], None


@app.get("/api/list-svgs")
def list_svgs():
    """List all SVG files available to the designer"""
    svgs: list[str] = []
    base_url = None

    if storage_enabled:
        try:
            blobs = gcs_bucket.list_blobs(prefix="assets/svgs/")
            svgs = [
                blob.name.split("/")[-1]
                for blob in blobs
                if blob.name.endswith(".svg")
            ]
            if svgs:
                base_url = "/gcs/assets/svgs"
                logger.info(f"Found {len(svgs)} SVGs in bucket")
        except Exception as e:
            logger.error(f"Failed to list SVGs from GCS: {e}")

    if not svgs:
        svgs = _discover_local_svgs()
        if svgs:
            base_url = "/designer/svgs"
            logger.info(f"Using {len(svgs)} local SVGs")

    return {"svgs": svgs, "base_url": base_url}


@app.get("/api/list-presets")
def list_presets():
    """List layout presets from GCS or local bundles"""
    presets: list[str] = []
    base_url: str | None = None

    if storage_enabled:
        try:
            blobs = gcs_bucket.list_blobs(prefix="presets/")
            for blob in blobs:
                name = blob.name
                if not name.endswith(".json"):
                    continue

                relative = name[len("presets/"):]
                if not relative or relative.endswith("/"):
                    continue

                if "/" in relative:
                    relative = relative.split("/")[-1]

                presets.append(Path(relative).stem)

            if presets:
                presets = sorted(set(presets))
                base_url = "/gcs/presets"
                logger.info(f"Found {len(presets)} presets in bucket")
        except Exception as e:
            logger.error(f"Failed to list presets from GCS: {e}")

    if not presets:
        local_presets, local_base = _discover_local_presets()
        presets = local_presets
        base_url = local_base
        if presets:
            logger.info(f"Using {len(presets)} local presets")

    return {"presets": presets, "base_url": base_url}
@app.get("/api/pexels/categories")
def list_pexels_categories():
    """Expose available Pexels categories to the designer"""
    categories = get_pexels_categories()
    return {
        "categories": categories,
        "enabled": ENABLE_PEXELS and storage_enabled,
    }


async def _run_pexels_prefetch(token: str | None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    if not ENABLE_PEXELS:
        raise HTTPException(status_code=503, detail="Pexels disabled")

    if not storage_enabled:
        raise HTTPException(status_code=503, detail="GCS not configured")

    categories = get_pexels_categories()
    if not categories:
        raise HTTPException(status_code=404, detail="No Pexels categories configured")

    try:
        summary = await refresh_pexels_assets(categories)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Pexels prefetch failed: {exc}")
        raise HTTPException(status_code=500, detail="Pexels prefetch failed") from exc

    return {
        "status": "ok",
        "categories": categories,
        "summary": summary,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/admin/prefetch")
async def admin_prefetch_post(token: str = None):
    """Trigger rollover + fetch of Pexels assets"""
    return await _run_pexels_prefetch(token)


@app.get("/admin/prefetch")
async def admin_prefetch_get(token: str = None):
    """GET-compatible trigger for schedulers"""
    return await _run_pexels_prefetch(token)


@app.get("/layouts/{device}")
def get_layout(device: str, x_admin_token: str = Header(None)):
    """Get layout JSON"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    if ENABLE_EMAIL_USERS:
        key = f"users/default/devices/{device}/layouts/current.json"
    else:
        key = f"layouts/{device}.json"
    
    try:
        return gcs_read_json(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Layout not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/layouts/{device}")
def save_layout(device: str, layout: dict, x_admin_token: str = Header(None)):
    """Save layout JSON"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    if ENABLE_EMAIL_USERS:
        key = f"users/default/devices/{device}/layouts/current.json"
    else:
        key = f"layouts/{device}.json"
    
    try:
        json_str = json.dumps(layout, indent=2)
        gcs_write_bytes(key, json_str.encode('utf-8'), "application/json")
        return {"status": "saved", "path": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/designer/", response_class=HTMLResponse)
def get_designer():
    """Serve designer HTML"""
    paths = [
        "backend/web/designer/overlay_designer_v3_full.html",
        "web/designer/overlay_designer_v3_full.html",
        "overlay_designer_v3_full.html"
    ]
    
    for path in paths:
        if os.path.exists(path):
            logger.info(f"Serving designer from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    
    logger.error("Designer HTML not found in any path")
    return "<h1>Designer not found</h1><p>Checked paths: " + ", ".join(paths) + "</p>"

@app.get("/test/", response_class=HTMLResponse)
def get_test():
    """Serve test page"""
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Test Designer</title>
<style>
body{margin:0;padding:20px;font-family:sans-serif;background:#1a1a1a;color:#fff}
#canvas{position:relative;width:800px;height:480px;background:linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);border:2px solid #333;margin:20px auto}
.el{position:absolute;cursor:move;border:2px solid red}
.el.text{background:rgba(255,255,255,0.9);padding:10px;font-size:20px;color:#000}
button{padding:10px 20px;margin:5px;background:#2d8cf0;color:white;border:none;cursor:pointer;border-radius:4px}
button:hover{background:#1a6ec0}
#status{margin:10px;padding:10px;background:#333;border-radius:4px}
</style></head><body>
<h1>Designer Test</h1>
<div id="status">Ready</div>
<button onclick="testAddText()">Add Text</button>
<button onclick="testAddBox()">Add Box</button>
<button onclick="testFetchData()">Fetch Data</button>
<button onclick="testListSVGs()">List SVGs</button>
<div id="canvas"></div>
<script>
const canvas = document.getElementById('canvas');
const status = document.getElementById('status');
function log(msg) { status.textContent = msg; console.log(msg); }
function testAddText() {
  const el = document.createElement('div');
  el.className = 'el text';
  el.style.left = '100px';
  el.style.top = '100px';
  el.style.width = '200px';
  el.style.height = '40px';
  el.textContent = 'Test Text';
  canvas.appendChild(el);
  log('Added text element - count: ' + canvas.children.length);
}
function testAddBox() {
  const el = document.createElement('div');
  el.className = 'el box';
  el.style.left = '200px';
  el.style.top = '200px';
  el.style.width = '150px';
  el.style.height = '100px';
  el.style.background = 'rgba(255,255,255,0.2)';
  el.style.border = '2px solid blue';
  canvas.appendChild(el);
  log('Added box element - count: ' + canvas.children.length);
}
async function testFetchData() {
  try {
    const response = await fetch('/v1/render_data?device=familydisplay');
    const data = await response.json();
    log('Fetch OK: temp=' + data.weather.temp + ', joke=' + data.dad_joke.substring(0,30));
  } catch (error) {
    log('Fetch ERROR: ' + error.message);
  }
}
async function testListSVGs() {
  try {
    const response = await fetch('/api/list-svgs');
    const data = await response.json();
    log('SVGs: ' + data.svgs.length + ' found - ' + data.svgs.slice(0,3).join(', '));
  } catch (error) {
    log('SVG List ERROR: ' + error.message);
  }
}
log('Test page loaded - canvas ready');
</script></body></html>"""

if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")

if os.path.exists("web/presets"):
    app.mount("/presets", StaticFiles(directory="web/presets", html=True), name="presets")

if os.path.exists("web/svgs"):
    app.mount("/svgs", StaticFiles(directory="web/svgs"), name="svgs")

if os.path.exists("backend/web/designer/presets"):
    app.mount(
        "/designer/presets",
        StaticFiles(directory="backend/web/designer/presets", html=True),
        name="designer-presets",
    )

if os.path.exists("backend/web/designer/svgs"):
    app.mount(
        "/designer/svgs",
        StaticFiles(directory="backend/web/designer/svgs"),
        name="designer-svgs",
    )

if os.path.exists("backend/web/designer/weather-icons"):
    app.mount(
        "/designer/weather-icons",
        StaticFiles(directory="backend/web/designer/weather-icons"),
        name="designer-weather-icons",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
