
# Family Display Backend — HF + Weather + Vivid FS Fallbacks (2025-10-24)

Includes:
- Hugging Face text→image generation (`/admin/generate`)
- OpenWeatherMap weather (`/v1/weather`, and overlay via `/v1/frame?overlay_wx=true&city=Darwin`)
- 8 vivid Floyd–Steinberg–dithered fallback posters in `backend/fallback_art/fallback_0..7.png`
- Cloud Run–ready `Dockerfile` and `requirements.txt`

## Env vars
- `HUGGING_FACE_TOKEN` (or `HF_TOKEN`)
- `HF_MODEL` (default `stabilityai/sdxl-turbo`)
- `WEATHER_API_KEY` (or `OWM_API_KEY`)
- `GCS_BUCKET_NAME` (optional)


## Fonts & overlays
- Includes Roboto Regular/Bold/Light in `backend/fonts/`
- Date label added at top-right using Roboto-Bold 24px
- Dad joke added at bottom with wrapping and line spacing (stacks above weather strip if both enabled)


## Layout presets
- New `layout` query: `glass` (default), `card`, `outline`, `minimal`, `poster`
- Example: `/v1/frame?layout=glass&overlay_wx=true&city=Darwin`
- Panels stack cleanly: joke sits above weather when both enabled.


## Dad jokes + Caching + ETag
- icanhazdadjoke with 3s timeout and one retry; hardcoded fallback jokes if offline.
- Simple cache: weather (15 min), joke (15 min) to reduce network churn.
- /v1/frame now returns an ETag and supports If-None-Match for 304.
