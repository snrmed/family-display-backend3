# Environment Variables for Cloud Run

## Copy-Paste Ready Configuration

```bash
# Core Configuration
GCS_BUCKET=family-display-packs
PUBLIC_BASE_URL=https://family-display-backend-867804884116.australia-southeast1.run.app
ADMIN_TOKEN=adm_860510

# API Keys
OPENWEATHER_KEY=your_openweather_api_key
PEXELS_API_KEY=your_pexels_api_key

# Feature Toggles
ENABLE_RENDERING=true
ENABLE_PEXELS=true
ENABLE_OPENWEATHER=true
ENABLE_JOKES_API=true

# Rendering Settings
RENDER_WIDTH=800
RENDER_HEIGHT=480
RENDER_PATH=backend/web/layouts/base.html
WEATHER_ICON_PACK=happy-skies

# Optional Settings
PORT=8080
DEFAULT_CITY=Darwin
LOG_LEVEL=info
```

## Variable Descriptions

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GCS_BUCKET` | - | ✅ Yes | Name of your Google Cloud Storage bucket |
| `PUBLIC_BASE_URL` | - | ✅ Yes | Full URL of your Cloud Run service |
| `ADMIN_TOKEN` | `adm_860510` | ✅ Yes | Admin key for protected routes |
| `OPENWEATHER_KEY` | - | ⚠️ If ENABLE_OPENWEATHER=true | OpenWeather API key |
| `PEXELS_API_KEY` | - | ⚠️ If ENABLE_PEXELS=true | Pexels API key |
| `ENABLE_RENDERING` | `true` | No | Enable Playwright PNG rendering |
| `ENABLE_PEXELS` | `true` | No | Enable Pexels background images |
| `ENABLE_OPENWEATHER` | `true` | No | Enable OpenWeather API |
| `ENABLE_JOKES_API` | `true` | No | Enable dad jokes API |
| `RENDER_WIDTH` | `800` | No | PNG render width in pixels |
| `RENDER_HEIGHT` | `480` | No | PNG render height in pixels |
| `RENDER_PATH` | `backend/web/layouts/base.html` | No | Path to base.html template |
| `WEATHER_ICON_PACK` | `happy-skies` | No | Default weather icon theme |
| `PORT` | `8080` | No | Service port (Cloud Run sets this) |
| `DEFAULT_CITY` | `Darwin` | No | Fallback city for weather |
| `LOG_LEVEL` | `info` | No | Logging verbosity |

## Cloud Run Setup via Console

1. Go to Cloud Run service
2. Click "Edit & Deploy New Revision"
3. Scroll to "Variables & Secrets"
4. Add each variable above
5. Click "Deploy"

## Cloud Run Setup via gcloud CLI

```bash
gcloud run services update family-display-backend \
  --region=australia-southeast1 \
  --set-env-vars="GCS_BUCKET=family-display-packs,\
PUBLIC_BASE_URL=https://family-display-backend-867804884116.australia-southeast1.run.app,\
ADMIN_TOKEN=adm_860510,\
ENABLE_RENDERING=true,\
ENABLE_PEXELS=true,\
ENABLE_OPENWEATHER=true,\
ENABLE_JOKES_API=true,\
RENDER_WIDTH=800,\
RENDER_HEIGHT=480,\
WEATHER_ICON_PACK=happy-skies,\
DEFAULT_CITY=Darwin" \
  --set-secrets="OPENWEATHER_KEY=openweather-key:latest,\
PEXELS_API_KEY=pexels-key:latest"
```

## Secrets Management (Recommended)

For API keys, use Secret Manager instead of environment variables:

```bash
# Create secrets
echo -n "your_openweather_key" | gcloud secrets create openweather-key --data-file=-
echo -n "your_pexels_key" | gcloud secrets create pexels-key --data-file=-

# Grant access to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding openweather-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding pexels-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## Feature Toggle Examples

### Disable Rendering (API-only mode)
```bash
ENABLE_RENDERING=false
```

### Use Local Fallback Weather
```bash
ENABLE_OPENWEATHER=false
```
This will use mock weather data.

### Disable Background Images
```bash
ENABLE_PEXELS=false
```
This will use a default gray background.

### Disable Jokes API
```bash
ENABLE_JOKES_API=false
```
This will use local fallback jokes.

## Critical Variables

**Must Be Set:**
- `GCS_BUCKET` - Without this, storage will be disabled
- `PUBLIC_BASE_URL` - Without this, asset URLs won't work correctly

**Highly Recommended:**
- `OPENWEATHER_KEY` - For real weather data
- `PEXELS_API_KEY` - For background images

**Can Use Defaults:**
- Everything else has sensible defaults
