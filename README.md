# 📘 Family Display Backend

> **A cloud backend for e-ink family dashboards** — fetches curated artwork, overlays weather and dad jokes, and serves layouts to ESP32 or Raspberry Pi Pico displays.  
> Built with **Flask + Google Cloud Run + GCS + Pexels API**.

---

## 🌈 Features
- **Sticker Parade** overlay renderer — clean frosted-glass cards with wrapped text.
- **Layout Designer** hosted at `/designer/` for drag-and-drop customization.
- **Per-device layouts** (`layouts/<device>/current.json`) with version history.
- **Weekly curated artwork** from **Pexels** (10 themes × 8 images).
- **Weather & Dad Jokes** overlays via OpenWeather + icanhazdadjoke.
- **Automatic 2-week cleanup** of old images in GCS.
- **Private GCS access** (no public bucket URLs).
- **Single default device** → `familydisplay`.

---

## 🗂️ Repository structure
```
family-display-backend3/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── web/
│       └── designer/
│           ├── overlay_designer_v3_full.html
│           ├── presets/
│           │   ├── center_float_light.json
│           │   ├── ... (9 other preset JSONs)
│           └── fonts/
│               ├── Roboto-Regular.ttf
│               ├── Roboto-Bold.ttf
│               └── Roboto-Light.ttf
├── Dockerfile
└── README.md
```

---

## ⚙️ Environment variables
| Variable | Example | Purpose |
|-----------|----------|----------|
| `GCS_BUCKET` | `family-display-packs` | Storage bucket for layouts & images |
| `ADMIN_TOKEN` | `super-secret` | Protects `/admin/*` endpoints |
| `PEXELS_API_KEY` | `px-xxxxxxxxxx` | Fetch weekly curated art |
| `OPENWEATHER_API_KEY` | `xxxxxxxxx...` | Weather overlay |
| `DEFAULT_LAYOUT_DEVICE` | `familydisplay` | Default device ID |
| `DEFAULT_RENDER_MODE` | `sticker_parade` | Overlay style |
| `DESIGNER_KEY` *(optional)* | `open-sesame` | Gate `/designer/?key=` access |

---

## 🚀 Deployment to Google Cloud Run

### 1️⃣ Build & deploy directly
```bash
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/family-display-backend backend
gcloud run deploy family-display-backend   --image gcr.io/$(gcloud config get-value project)/family-display-backend   --region australia-southeast1   --allow-unauthenticated   --set-env-vars GCS_BUCKET=family-display-packs,DEFAULT_LAYOUT_DEVICE=familydisplay,DEFAULT_RENDER_MODE=sticker_parade   --set-env-vars ADMIN_TOKEN=<secret>,PEXELS_API_KEY=<key>,OPENWEATHER_API_KEY=<key>
```

### 2️⃣ Verify
- `/` → JSON status  
- `/designer/` → opens layout designer  
- `/preview` → shows rendered PNG overlay  

---

## 🎨 Prefetch weekly Pexels images
Run this once a week (automate via **Cloud Scheduler**):

```bash
curl -X POST   -H "X-Admin-Token: <your-secret>"   -H "Content-Type: application/json"   -d '{"themes":["abstract backgrounds","colorful gradients"],"per_theme_count":8}'   https://family-display-backend-867804884116.australia-southeast1.run.app/admin/prefetch
```

Images are stored in:
```
images/<YYYY-Www>/<theme_slug>/img_<n>.jpg
```

---

## 🧩 Layout workflow
1. Open `/designer/?device=familydisplay&key=<DESIGNER_KEY>`  
2. Drag + edit elements, then **Save to Server**.  
3. JSON saved to GCS → `layouts/familydisplay/current.json`.  
4. Devices fetch `/layouts/familydisplay` using `If-None-Match` for cheap polling.  
5. Preview final image at `/preview`.

---

## 🧱 GCS security setup
```bash
gsutil uniformbucketlevelaccess set on gs://family-display-packs
gsutil pap set enforced gs://family-display-packs
gsutil iam ch serviceAccount:<CLOUD-RUN-SA>:roles/storage.objectAdmin gs://family-display-packs
```
No public reads — all access goes through the backend.

---

## 🧰 Local development
```bash
cd backend
pip install -r requirements.txt
python main.py
# open http://localhost:8080/
```

---

## 🕓 Maintenance jobs (recommended)
| Job | Endpoint | Schedule | Purpose |
|------|-----------|-----------|----------|
| Weekly image prefetch | `/admin/prefetch` | Every Mon 01:00 | New artwork |
| Daily cleanup | `/admin/cleanup` | Every day 03:00 | Remove > 2 week-old files |

Configure in **Cloud Scheduler** with OIDC auth or token header.

---

## 🧭 Useful endpoints
| Method | Path | Description |
|---------|------|-------------|
| `GET` | `/` | Status + version info |
| `GET` | `/preview` | Render PNG preview |
| `GET` | `/layouts/<device>` | Fetch current layout JSON |
| `PUT` | `/admin/layouts/<device>` | Save new layout (requires `ADMIN_TOKEN`) |
| `POST` | `/admin/prefetch` | Generate weekly art pack |
| `POST` | `/admin/cleanup` | Delete old images |
| `GET` | `/designer/` | Open the web designer |

---

## 🧠 Roadmap snapshot
- [x] Secure GCS + image proxy  
- [x] Hosted designer + versioned layouts  
- [ ] Claim token QR onboarding  
- [ ] Device registry + heartbeat  
- [ ] Rollback & history UI  
- [ ] CDN for image packs  
- [ ] Multi-user roles and themes  

---

## 🏁 License
MIT License © 2025 Family Display Project
