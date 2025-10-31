# 🧠 Kin:D / Family Display Backend

A cloud-based backend for the **Kin:D / Family Display** project — a family-friendly e-ink / smart-display platform that shows daily art, weather, jokes, and calendar info on a low-power device such as an ESP32 or Raspberry Pi Pico with an e-paper screen.

Built with **FastAPI + Playwright** and deployed to **Google Cloud Run**, this backend provides:
- Dynamic daily content (images, weather, jokes)
- A browser-based **Designer** to visually create and save layouts
- Font, preset, and SVG asset hosting
- Scheduled image prefetch from **Pexels**
- PNG rendering pipeline via headless Chromium
- Storage in **Google Cloud Storage (GCS)** for layouts and assets

---

## 🏗️ Repository structure

```
family-display-backend3/
├── Dockerfile                # Playwright-enabled container build
├── cloudbuild.yaml           # Cloud Build → Artifact Registry → Cloud Run
├── README.md
└── backend/
    ├── main.py               # Unified FastAPI app
    ├── requirements.txt
    └── web/
        ├── designer/
        │   ├── overlay_designer_v3_full.html
        │   ├── presets/      # 10 themed + 2 custom layouts
        │   └── svgs/         # Cleaned icon pack
        ├── fonts/
        │   ├── fonts.css
        │   ├── fetch_fonts.sh
        │   └── <OFL .ttf families>
        └── layouts/
            └── base.html     # Renderer template (used by Playwright)
```

---

## ✨ Features

### 🎨 Visual Designer
- Served at `/designer/`
- Drag-and-drop overlay editor for cards, icons, and text
- Loads/saves layouts directly from GCS
- Uses bundled SVGs, fonts, and presets for fast prototyping

### 🖼️ Rendering
- Headless Chromium via **Playwright**
- Template: `backend/web/layouts/base.html`
- Merges live data (`/v1/render_data`) + saved layout → PNG
- Outputs stored in `renders/<device>/<date>/frame.png`

### 🌅 Image Source & Fallback
1. `pexels/current/` (latest prefetch)
2. `pexels/cache/<date>/` (previous week)
3. `images/current/`
4. `images/backup/`
5. 1×1 PNG placeholder

### 📦 Prefetch Scheduler
- Endpoint: `/admin/prefetch?token=<ADMIN_TOKEN>`
- Rolls over old `pexels/current/` → `pexels/cache/<date>/`
- Fetches new themed images via **Pexels API**
- Typically triggered daily/weekly by **Cloud Scheduler**

### 🃏 Jokes & Data
- Endpoint: `/v1/render_data`
- Tries `content/jokes.json` in GCS → else picks from local list
- Returns weather, date, and a dad joke

### 🔤 Fonts
- All **OFL-licensed**: Inter, Roboto, Atkinson Hyperlegible, Source Sans 3, Public Sans, Manrope, Space Grotesk, Outfit, Plus Jakarta Sans, Merriweather, Noto Sans
- Served from `/fonts/fonts.css`
- Shared between Designer and Renderer

---

## ☁️ Deployment on Google Cloud Run

### 1. Prerequisites
- **Google Cloud SDK** configured
- **Artifact Registry** repo:  
  `australia-southeast1-docker.pkg.dev/<PROJECT_ID>/family-display/backend`
- **GCS bucket** (e.g. `family-display-packs`)
- Optional **Cloud Scheduler** job hitting `/admin/prefetch`

### 2. Environment variables (set in Cloud Run → Variables & Secrets)

| Key | Example | Description |
|-----|----------|-------------|
| `GCS_BUCKET` | `family-display-packs` | bucket for assets & layouts |
| `ADMIN_TOKEN` | `adm_860510` | auth for admin routes |
| `PEXELS_API_KEY` | `pexels_...` | Pexels API token |
| `THEMES` | `abstract,geometric,kids,photo` | image theme rotation |

### 3. Build & deploy

Automatic via GitHub → Cloud Build trigger using `cloudbuild.yaml`.

---

## 🧪 Local development

### 1. Build container
```bash
docker build -t family-display .
```

### 2. Run
```bash
docker run -p 8080:8080   -e GCS_BUCKET=family-display-packs   -e ADMIN_TOKEN=adm_860510   family-display
```
Visit [http://localhost:8080/designer/](http://localhost:8080/designer/)

### 3. Test endpoints
```bash
curl http://localhost:8080/v1/render_data
curl http://localhost:8080/v1/frame --output frame.png
```

---

## 🔗 API summary

| Method | Path | Purpose |
|---------|------|----------|
| `GET` | `/designer/` | Load the visual layout designer |
| `GET` | `/presets/{name}.json` | Fetch preset layouts |
| `GET` | `/svgs/{name}` | Fetch SVG icon |
| `GET` | `/fonts/{subpath}` | Serve fonts or CSS |
| `GET` | `/layouts/{device}` | Load saved layout |
| `POST` | `/admin/layouts/{device}` | Save layout to GCS (requires admin token) |
| `GET` | `/v1/render_data` | Return live data JSON (weather, joke, date) |
| `GET` | `/v1/frame` | Return rendered PNG |
| `GET` | `/admin/prefetch` | Refresh Pexels image cache (requires admin token) |

---

## 🧰 Maintenance

### Backups
Layouts and content are stored in your GCS bucket:
```
family-display-packs/
├── layouts/<device>/current.json
├── pexels/current/
├── pexels/cache/<date>/
├── images/backup/
└── renders/<device>/<date>/frame.png
```

### Logs
All requests and build output appear in:
- **Cloud Run → Logs**
- **Cloud Build → History**

### Updating fonts
If fonts are missing, run:
```bash
cd backend/web/fonts
bash fetch_fonts.sh
```

---

## 🧑‍💻 Credits & License

- **Author:** Shekar Roopan  
- **Project name:** *Kin:D – Family Display*  
- Fonts under **OFL 1.1** license  
- Backend code under **MIT License**

---

> *Kin:D brings together art, weather, and family smiles — one e-ink frame at a time.*
