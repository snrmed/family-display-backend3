# kin;D Family Display Backend

The kin;D Family Display is a smart e-ink frame that shows daily artwork, weather, jokes, and other curated content for families. This repository contains the backend service that powers those experiences.

---

## Table of Contents
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Development](#development)
  - [Requirements](#requirements)
  - [Environment Variables](#environment-variables)
  - [Run Locally](#run-locally)
  - [Tests](#tests)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Support](#support)

---

## Architecture

```
Designer UI (HTML/JS)
       ↓
Layout JSON stored in Google Cloud Storage
       ↓
FastAPI backend assembles render context
       ↓
Playwright (Chromium) renders PNG frames
       ↓
Family display device downloads latest frame
```

The backend is deployed to Google Cloud Run and relies on Google Cloud Storage for persistent assets such as layouts, presets, and rendered frames.

## Features

- **Dynamic content** – pulls fresh artwork, weather, and dad jokes from third-party APIs.
- **Headless rendering** – uses Playwright with Chromium to render HTML layouts into PNG frames.
- **Designer workflow** – integrates with the kin;D Designer web interface for creating and managing layouts.
- **Multi-user hierarchy (optional)** – supports organizing devices by email accounts and family groups.
- **Cloud-native** – optimized for Cloud Run with modular provider architecture.

## Tech Stack

- Python with FastAPI for the REST API layer
- Playwright (Chromium) for server-side rendering
- Google Cloud Storage for layouts, presets, and rendered frames
- Google Cloud Run for containerized deployment
- Optional integrations: Pexels (artwork), OpenWeather (weather), icanhazdadjoke (jokes)

## Development

### Requirements

- Python 3.11+
- Node.js (required by Playwright for Chromium downloads)
- Google Cloud SDK (for deployment tasks)
- Docker (optional, for local parity with Cloud Run)

### Environment Variables

Configuration is controlled through environment variables. The full reference is documented in [`backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md`](backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md).

Common toggles include:

| Variable | Purpose |
| --- | --- |
| `ENABLE_RENDERING` | Turn Playwright rendering on or off. |
| `ENABLE_EMAIL_USERS` | Enable hierarchical user/device storage. |
| `ENABLE_PEXELS` | Fetch curated background images from Pexels. |
| `ENABLE_OPENWEATHER` | Toggle OpenWeather integration. |
| `ENABLE_JOKES_API` | Toggle dad joke provider. |
| `CITY_MODE` | Either `default` (static city) or `fetch` (from layout JSON). |
| `DEFAULT_CITY` | Fallback city name when `CITY_MODE=default`. |
| `GCS_BUCKET` | Target Google Cloud Storage bucket for assets. |
| `ADMIN_TOKEN` | Shared secret for admin routes like render and prefetch. |

### Run Locally

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```
3. Set the required environment variables (see above).
4. Start the development server:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
   ```
5. Open `http://localhost:8080/docs` for the interactive API docs or `http://localhost:8080/designer/` for the layout designer.

### Tests

The project uses `pytest` for automated testing.

```bash
pytest
```

Additional linting or type checks can be added as needed.

## Deployment

Deployment is designed for Google Cloud Run. A `Dockerfile` and `cloudbuild.yaml` are included for building and deploying via Cloud Build.

High-level steps:

1. Build and push the container image:
   ```bash
   gcloud builds submit --tag gcr.io/<PROJECT_ID>/family-display-backend
   ```
2. Deploy to Cloud Run:
   ```bash
   gcloud run deploy family-display-backend \
       --image gcr.io/<PROJECT_ID>/family-display-backend \
       --region <REGION> \
       --platform managed \
       --allow-unauthenticated
   ```
3. Configure environment variables and secrets in the Cloud Run service settings.

## Project Structure

```
backend/
├── main.py                     # FastAPI entrypoint
├── web/
│   ├── designer/               # Designer HTML artifacts
│   ├── layouts/                # Base layout templates
│   ├── fonts/                  # Font assets
│   ├── presets/                # Prefabricated layout JSON files
│   └── svgs/                   # SVG assets
└── docs/
    └── KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md
```

Other top-level files:

- `Dockerfile` – container definition for Cloud Run
- `cloudbuild.yaml` – Google Cloud Build configuration
- `ENVIRONMENT_VARIABLES.md` – quick reference for environment settings
- `BUCKET_SETUP.md` and `BUCKET_STRUCTURE.txt` – details about Cloud Storage buckets and layout organization

## Troubleshooting

- **Playwright fails to launch Chromium** – ensure `playwright install chromium` has been run and that the server has required system dependencies (see Playwright docs).
- **Missing assets** – confirm the GCS bucket paths in your environment variables and that service accounts have access.
- **Slow renders** – rendering is CPU intensive; consider increasing Cloud Run CPU allocation or pre-rendering frames on a schedule.
- **Designer not loading** – verify that static files are mounted correctly and reachable at `/designer/`.

## Support

For questions, file an issue or reach out to the kin;D team. Contributions are welcome via pull requests.

---

> kin;D — Make a Smile ;D
