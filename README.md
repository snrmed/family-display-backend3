# 🖼️ kin;D Family Display Backend

This repository contains the **backend service** powering the **kin;D Family Display** — a smart, cloud-connected e-ink display that brings art, weather, jokes, and inspiration to your home every day.  

The backend runs on **Google Cloud Run**, uses **FastAPI**, and renders visual layouts using **Playwright (Chromium)** with dynamic data from APIs like **Pexels**, **OpenWeather**, and **icanhazdadjoke**.

---

## 🚀 Features

- 🌤️ **Live Data Providers** — Weather, jokes, and more (modular architecture)  
- 🧱 **Dynamic Layouts** — Designed via the Kin;D Designer HTML tool  
- ☁️ **Cloud Storage** — All layouts, renders, and presets are stored in GCS  
- 🧠 **Headless Rendering** — Uses Playwright to render PNG frames from HTML templates  
- 👨‍👩‍👧‍👦 **Multi-User Ready** — Optional email + device hierarchy system  
- 🪶 **Lightweight API** — Optimized for Cloud Run and ESP32/pico clients  
- 🎨 **Themed Visuals** — Fetches curated images from Pexels (weekly rotation)  

---

## 🧩 System Overview

```
[ Designer HTML ]
       ↓
Save JSON Layouts → [ Google Cloud Storage ]
       ↓
Build Render Data → [ FastAPI Backend ]
       ↓
Chromium → Render PNG Frame
       ↓
[ Family Display Device ]
```

---

## ⚙️ Environment Variables

See the full list and explanations in  
[`backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md`](backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md).

Key variables include:

| Variable | Description |
|-----------|--------------|
| `ENABLE_RENDERING` | Enable Playwright rendering |
| `ENABLE_EMAIL_USERS` | Hierarchical user/device storage |
| `ENABLE_PEXELS` | Pexels integration for themed backgrounds |
| `ENABLE_OPENWEATHER` | Weather provider toggle |
| `ENABLE_JOKES_API` | Dad joke provider toggle |
| `CITY_MODE` | “default” (static) or “fetch” (from layout JSON) |
| `DEFAULT_CITY` | Fallback city name |
| `GCS_BUCKET` | Target Cloud Storage bucket |
| `ADMIN_TOKEN` | Admin key for render/prefetch routes |

---

## 🧰 Development

### Local Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Deploy to Cloud Run

The repository includes a ready-to-use `Dockerfile` and `cloudbuild.yaml`.  
Deploy from GitHub using **Cloud Build** and link to **Cloud Run** in your chosen region.

---

## 📦 Folder Structure

```
backend/
├── main.py                     # FastAPI backend
├── web/
│   ├── designer/overlay_designer_v3_full.html
│   ├── layouts/base.html
│   ├── fonts/
│   ├── presets/
│   └── svgs/
└── docs/
    └── KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md
```

---

## 💡 Quick Testing

After deployment:

- View Designer UI:  
  👉 `https://<your-cloudrun-url>/designer/`

- Render current frame:  
  👉 `https://<your-cloudrun-url>/v1/frame?device=familydisplay`

- Admin Prefetch (Pexels):  
  👉 `https://<your-cloudrun-url>/admin/prefetch?token=adm_860510`

---

## 🧠 Developer Documentation

Full backend reference, environment variable matrix, and modular provider architecture are detailed in:  
👉 [**KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md**](backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md)

---

## 🌞 kin;D — Make a Smile ;D

Welcome to **kin;D**, the creative, cloud-powered family display that turns your wall or fridge into a living canvas of smiles.  
From weather and dad jokes to curated art and family reminders — kin;D makes every glance a little brighter.  

> **kin;D — Make a Smile ;D**  
> A smart display for families, built to share joy.
