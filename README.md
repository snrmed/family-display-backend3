# Family Display – HTML Render Backend (Stage 1)

This backend renders an HTML layout (with CSS/SVG elements) to a PNG using headless Chromium (Playwright).  
It’s designed to replace Flask/Pillow overlays with **pixel-perfect HTML** so the preview and device output match 1:1.

## What’s included
- `backend/main.py` – FastAPI app exposing:
  - `GET /v1/render_data` – **stub** dynamic data (date, city, weather, joke, Pexels background path)
  - `GET /web/layouts/base.html` – example HTML layout
  - `GET /admin/render_now?device=...&layout=base&token=...` – headless render → PNG (saved to GCS if configured)
  - `GET /v1/frame?device=...` – latest render for the device (PNG)
- `backend/web/layouts/base.html` – minimal sample layout (800×480) with a bg image + two cards (glass + chip)
- `backend/requirements.txt` – FastAPI + Playwright + GCS SDK
- `backend/Dockerfile` – Cloud Run friendly; installs Chromium for Playwright
- `cloudbuild.yaml` – Cloud Build config to build/push/deploy
- `.gitignore` – ignores Python, Playwright cache, and common artifacts

## Env variables
- `GCS_BUCKET` – GCS bucket for saving renders (e.g., `family-display-packs`). Leave empty for local-only.
- `ADMIN_TOKEN` – token required by `/admin/render_now` (e.g., `adm_123456`).
- `PUBLIC_BASE_URL` – public base URL of this service (Cloud Run URL). Used so Chromium loads the layout page.

## Local run (Docker)
```bash
docker build -t family-html backend
docker run -p 8080:8080   -e GCS_BUCKET=family-display-packs   -e ADMIN_TOKEN=adm_123456   -e PUBLIC_BASE_URL=http://127.0.0.1:8080   family-html
```

Test endpoints:
- Layout preview:  
  `http://127.0.0.1:8080/web/layouts/base.html?backend=http://127.0.0.1:8080&device=familydisplay`
- Render + save:  
  `http://127.0.0.1:8080/admin/render_now?device=familydisplay&token=adm_123456`
- Device readout (latest):  
  `http://127.0.0.1:8080/v1/frame?device=familydisplay`

## Deploy (Cloud Run)
```bash
gcloud builds submit backend --tag gcr.io/$PROJECT_ID/family-html
gcloud run deploy family-display-backend   --image gcr.io/$PROJECT_ID/family-html   --region australia-southeast1   --platform managed   --allow-unauthenticated   --set-env-vars GCS_BUCKET=family-display-packs,ADMIN_TOKEN=adm_123456,PUBLIC_BASE_URL=https://<your-run-url>
```

## Next steps
- Replace `base.html` with your Designer-exported layout (exposing `#canvas` 800×480).
- Wire `/v1/render_data` to your real **OpenWeather** + **Pexels** cache.
- (Optional) Add `/admin/devices/<id>/config` and `/admin/layouts/<id>` for per-device presets.
