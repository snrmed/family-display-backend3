# Family Display – HTML Render Backend (Stage 1)

This backend renders an HTML layout (CSS/SVG elements) to a PNG using headless Chromium (Playwright).  
It replaces Flask/Pillow overlays with **pixel-perfect HTML**, so the preview and device output match.

## Endpoints
- `GET /v1/render_data?device=...&theme=...`  
  Returns JSON used by layouts (date, city, weather, joke, background URL).  
  For now this is a stub; wire real providers in Step 2.1.
- `GET /web/layouts/base.html`  
  Example layout (800×480) that hydrates from `/v1/render_data`.
- `GET /admin/render_now?device=...&layout=base&token=...`  
  Opens the layout headlessly, screenshots `#canvas`, saves PNG (`renders/<device>/latest.png`).
- `GET /v1/frame?device=...`  
  Returns the latest PNG for a device.

## Env vars
- `GCS_BUCKET` – GCS bucket for renders (e.g., `family-display-packs`).
- `ADMIN_TOKEN` – token required by `/admin/render_now` (e.g., `adm_123456`).
- `PUBLIC_BASE_URL` – public base URL of this service (Cloud Run URL).
- `DEFAULT_DEVICE_ID` – defaults to `familydisplay` (multi-device ready).
- `DEFAULT_CITY` – fallback city (e.g., `Darwin, AU`).
- `DEFAULT_UNITS` – `metric` or `imperial`.
- `TIMEZONE` – e.g., `Australia/Adelaide`.

## Local run (Docker)
```bash
docker build -t family-html backend
docker run -p 8080:8080 \
  -e GCS_BUCKET=family-display-packs \
  -e ADMIN_TOKEN=adm_123456 \
  -e PUBLIC_BASE_URL=http://127.0.0.1:8080 \
  -e DEFAULT_DEVICE_ID=familydisplay \
  -e DEFAULT_CITY="Darwin, AU" \
  -e DEFAULT_UNITS=metric \
  -e TIMEZONE=Australia/Adelaide \
  family-html