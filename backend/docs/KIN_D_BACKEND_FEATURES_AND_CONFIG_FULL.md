# 🧠 Kin:D Family Display Backend — Developer Reference
*(Production Build v2.0.0)*

**Author:** Shekar Roopan  
**Maintainer:** Kin:D Project  
**Last Updated:** 31 Oct 2025  
**Status:** Production Ready  

---

This document explains how the **Kin:D / Family Display** backend (`main.py`) works — including its modular structure, environment-controlled features, provider auto-detection, and future-ready extensibility.

---

## ⚙️ 1. Overview

The backend is a **cloud-native FastAPI service** designed for Google Cloud Run with full integration into **Google Cloud Storage (GCS)**, **Playwright (Chromium)**, and multiple live content providers (Pexels, OpenWeather, icanhazdadjoke).  

It powers both the **Designer interface** and the **display rendering pipeline** for all Kin:D devices.

---

## 🧩 2. Architecture Summary

### 🏗️ Core Components

| Component | Description |
|------------|--------------|
| **FastAPI** | Web framework serving API and static routes |
| **Google Cloud Storage (GCS)** | Persistent storage for layouts, images, and renders |
| **Playwright (Chromium)** | Headless rendering engine producing PNG frames from `base.html` |
| **Pexels API** | Provides curated image content for themes |
| **OpenWeather API** | Supplies current weather info |
| **icanhazdadjoke API** | Provides dad jokes with local fallback |
| **Modular Providers** | Pluggable system for extending data sources (calendar, sports, etc.) |
| **Environment Variables** | Control every major feature (toggle, debug, hierarchy, etc.) |

---

## 🧮 3. Folder Structure

```
backend/
├── main.py                     # FastAPI backend (this file)
├── web/
│   ├── designer/overlay_designer_v3_full.html
│   ├── fonts/
│   ├── layouts/base.html
│   ├── presets/
│   └── svgs/
└── requirements.txt
```

---

## 🔧 4. Programmable Environment Variables

Each major feature is controlled through environment variables so you can reconfigure the backend without editing code.

| Variable | Default | Type | Description |
|-----------|----------|------|-------------|
| **PORT** | 8080 | int | Cloud Run port |
| **LOG_LEVEL** | `info` | string | Log verbosity (`debug`, `info`, `warning`) |
| **GCS_BUCKET** | — | string | Name of your Cloud Storage bucket |
| **ADMIN_TOKEN** | `adm_860510` | string | Global admin key for `/admin/*` routes |
| **ENABLE_EMAIL_USERS** | `false` | bool | Use hierarchical structure `users/<email>/devices/<device>` |
| **ENABLE_RENDERING** | `true` | bool | Activate Playwright/Chromium PNG generation |
| **ENABLE_RENDER_NOW** | `true` | bool | Enable `/admin/render_now` route |
| **ENABLE_PEXELS** | `true` | bool | Use Pexels API for themed image prefetch |
| **ENABLE_OPENWEATHER** | `true` | bool | Fetch live weather from OpenWeather |
| **ENABLE_JOKES_API** | `true` | bool | Use icanhazdadjoke API for dad jokes |
| **CITY_MODE** | `default` | string | `"default"` → use `DEFAULT_CITY`, `"fetch"` → read `"city"` from layout JSON |
| **DEFAULT_CITY** | `Darwin` | string | Fallback city for weather/jokes context |
| **PEXELS_API_KEY** | — | string | Pexels API key |
| **OPENWEATHER_KEY** | — | string | OpenWeather API key |
| **THEMES** | `abstract,geometric,kids,photo` | list | Pexels image categories |
| **CACHE_EXPIRY_DAYS** | 7 | int | Cache rollover age for Pexels images |
| **RENDER_PATH** | `backend/web/layouts/base.html` | string | HTML template path used by Playwright |
| **RENDER_WIDTH** | 800 | int | Render width (pixels) |
| **RENDER_HEIGHT** | 480 | int | Render height (pixels) |

All variables are read automatically at runtime — no rebuild needed.

---

## 🧱 5. Optional Email + Device Hierarchy

When `ENABLE_EMAIL_USERS=true`, layouts, renders, and configs are stored as:

```
users/<email_sanitized>/devices/<device_id>/layouts/current.json
users/<email_sanitized>/devices/<device_id>/renders/latest.png
```

When disabled, they remain at:
```
layouts/<device_id>.json
renders/<device_id>/latest.png
```

This allows instant multi-user expansion without code changes.

---

## 🌤️ 6. Modular Provider System

`/v1/render_data` aggregates all live data used by displays and renders.  
Each data type (weather, joke, etc.) is implemented as a **provider** function.  
Providers are registered in the `INFO_PROVIDERS` dict and called dynamically.

Example:
```python
INFO_PROVIDERS = {
    "weather": ENABLE_OPENWEATHER,
    "joke": ENABLE_JOKES_API,
    "calendar": False,
    "sports": False,
}
```

Each provider is an async function returning a dictionary or value:
```python
async def get_weather(city: str) -> dict:
    ...
async def get_joke() -> str:
    ...
```

Adding a new feature (e.g. quotes, calendar, sports) only requires:
1. Writing `get_<feature>()`
2. Setting `INFO_PROVIDERS["<feature>"] = True`
3. Adding an environment variable toggle (optional)

This makes the backend auto-detect new features through the provider registry.

---

## 🖼️ 7. Rendering Pipeline (Playwright)

1. `/v1/frame` or `/admin/render_now` loads layout JSON + render data  
2. Injects JSON context (`date`, `city`, `weather`, `dad_joke`, etc.) into `base.html` via querystring  
3. Playwright opens Chromium headlessly, renders HTML → PNG screenshot  
4. PNG is uploaded to GCS under the appropriate path  
5. Devices fetch it via `/v1/frame` or direct bucket link  

You can toggle this system with `ENABLE_RENDERING=false` for API-only tests.

---

## 🧰 8. Admin Routes

| Route | Description |
|--------|--------------|
| `/admin/render_now` | Forces immediate render for a device (saves `latest.png` and dated copy). Controlled by `ENABLE_RENDER_NOW`. |
| `/admin/prefetch` | Rolls over `pexels/current/` → `pexels/cache/YYYY-MM-DD/` and fetches new themed images. Controlled by `ENABLE_PEXELS`. |

Both require the correct `ADMIN_TOKEN`.

---

## 🌐 9. Data Flow Summary

**Designer HTML**  
⬇️ Saves → `layouts/<device>.json` or `users/<email>/devices/<device>/layouts/current.json`  

**Backend `/v1/render_data`**  
⬆️ Reads layout JSON → merges providers → returns combined JSON  

**Backend `/v1/frame`**  
🧠 Uses layout + render data → Chromium → uploads PNG to GCS  

**Device Firmware (ESP32, etc.)**  
⬇️ Fetches `/v1/frame` or GCS signed URL → displays PNG  

---

## 🪄 10. Debugging

Set:
```bash
LOG_LEVEL=debug
```

to see:
- API call traces  
- Provider fetch logs  
- GCS writes / reads  
- Playwright render timing  

Use:
```bash
gcloud run services logs read family-display-backend --region=australia-southeast1
```
to view logs in Cloud Run.

---

## 🧭 11. Adding New Providers Later

To add, for example, a **quote** or **calendar** provider:

1. Write a function in `main.py`:
   ```python
   async def get_quote():
       async with httpx.AsyncClient() as c:
           r = await c.get("https://api.quotable.io/random")
           return {"quote": r.json().get("content")}
   ```

2. Register it:
   ```python
   INFO_PROVIDERS["quote"] = True
   ```

3. Merge its output in `build_render_data()`:
   ```python
   if INFO_PROVIDERS.get("quote"):
       data["quote"] = await get_quote()
   ```

4. Optional: add a new env variable `ENABLE_QUOTES=true` for toggling.

That’s it — the backend will automatically include the new field in the JSON returned by `/v1/render_data` and available to the renderer.

---

## ✅ 12. Summary of Key Advantages

- 🔄 **Feature toggles** via environment variables (no redeploy needed)  
- 🧱 **Modular providers** – add new content with minimal edits  
- ☁️ **Cloud-only design** – GCS stores everything, no local persistence  
- 🎨 **Headless rendering** – dynamic PNG output with Playwright  
- 👨‍👩‍👧‍👦 **User/device hierarchy** – scalable multi-user model ready  
- 🪶 **Lightweight logs** – switchable verbosity  

---

### 🏁 Example Production Environment (Cloud Run)

```bash
LOG_LEVEL=info
ENABLE_EMAIL_USERS=true
ENABLE_RENDERING=true
ENABLE_RENDER_NOW=true
ENABLE_PEXELS=true
ENABLE_OPENWEATHER=true
ENABLE_JOKES_API=true
CITY_MODE=fetch
DEFAULT_CITY=Darwin
PEXELS_API_KEY=<pexels-key>
OPENWEATHER_KEY=<owm-key>
GCS_BUCKET=family-display-packs
ADMIN_TOKEN=adm_860510
```

---

> **Kin:D — Make a Smile ;D**  
> This backend was built to scale gracefully, extend easily, and power every smile your display makes.
