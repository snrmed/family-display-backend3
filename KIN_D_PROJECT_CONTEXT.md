# Kin:D / Family Display – Project Context

**Purpose:**  
A cloud-rendered display system that generates visual dashboards (weather, jokes, calendar, art) for family e-ink devices.

**Slogan:**  
> “Kin;D — Make a smile.”

**Stack Overview**
- **Backend:** FastAPI + Playwright (Chromium snapshot engine)
- **Deployment:** Google Cloud Run, Cloud Build CI/CD, Cloud Scheduler
- **Storage:** Google Cloud Storage (GCS)
- **Frontend assets:** `base.html`, Designer HTML, presets, fonts, and SVG assets
- **APIs:** Pexels (backgrounds), OpenWeather (weather), icanhazdadjoke (humor)

**Repo:** `https://github.com/snrmed/family-display-backend3`

**Folders**
```
backend/
  main.py
  web/
    layouts/
    designer/
    fonts/
    svgs/
    assets/weather-icons/
    presets/
```

**Naming Rules**
- Folder names: lowercase-with-dashes
- Presets: Theme 1.json → Theme 10.json
- Icon packs: happy-skies, soft-skies, sunny-day, blue-sky-pro
- Default device: familydisplay

**Core Environment Variables**
```
ENABLE_RENDERING=true
ENABLE_PEXELS=true
ENABLE_OPENWEATHER=true
ENABLE_JOKES_API=true
GCS_BUCKET=family-display-packs
PUBLIC_BASE_URL=https://family-display-backend-867804884116.australia-southeast1.run.app
WEATHER_ICON_PACK=happy-skies
```
