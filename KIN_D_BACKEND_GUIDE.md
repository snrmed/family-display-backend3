# Kin:D Backend Guide

## Main Components
| File | Purpose |
|------|----------|
| backend/main.py | Core FastAPI backend and rendering logic |
| backend/web/layouts/base.html | Render template for Playwright |
| backend/web/designer/overlay_designer_v3_full.html | Layout editor for browser |
| backend/web/designer/presets/*.json | Default and custom layout presets |
| backend/web/fonts/ | Font files |
| backend/web/svgs/ | SVG assets |
| backend/web/assets/weather-icons/ | Icon packs |

## Key Endpoints
| Endpoint | Description |
|-----------|-------------|
| `/` | Service info JSON |
| `/designer/` | Launch layout designer |
| `/v1/render_data?device=familydisplay` | Live JSON payload |
| `/v1/frame?device=familydisplay` | Render full PNG |
| `/admin/prefetch?token=adm_860510` | Refresh Pexels cache |
| `/admin/render_now?token=adm_860510` | Manual render trigger |

## Environment Variables
| Variable | Description |
|-----------|-------------|
| ENABLE_EMAIL_USERS | Email/device folder tree toggle |
| CITY_MODE | “fetch” or “default” city source |
| DEFAULT_CITY | Default city name |
| RENDER_PATH | Path to base.html |
| WEATHER_ICON_PACK | Default weather icon theme |
| PUBLIC_BASE_URL | Optional base for GCS assets |
