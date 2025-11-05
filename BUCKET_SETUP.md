# GCS Bucket Setup Guide

## Environment Variables

### Required Variables
```bash
GCS_BUCKET=family-display-packs
PUBLIC_BASE_URL=https://family-display-backend-867804884116.australia-southeast1.run.app
ADMIN_TOKEN=adm_860510
```

### API Keys (Required for features)
```bash
OPENWEATHER_KEY=your_openweather_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
```

### Feature Toggles
```bash
ENABLE_RENDERING=true
ENABLE_PEXELS=true
ENABLE_OPENWEATHER=true
ENABLE_JOKES_API=true
```

### Rendering Configuration
```bash
RENDER_WIDTH=800
RENDER_HEIGHT=480
RENDER_PATH=backend/web/layouts/base.html
WEATHER_ICON_PACK=happy-skies
```

### Optional Variables
```bash
PORT=8080
DEFAULT_CITY=Darwin
LOG_LEVEL=info
```

---

## GCS Bucket Structure

### Expected Directory Layout
```
family-display-packs/
├── web/
│   └── designer/
│       └── overlay_designer_v4_clean.html
│
├── assets/
│   ├── svgs/
│   │   ├── candy.svg
│   │   ├── lemon.svg
│   │   ├── mint.svg
│   │   ├── sunset.svg
│   │   ├── glass_card_aqua.svg
│   │   ├── glass_card_sky.svg
│   │   ├── dad_joke_card_lime.svg
│   │   └── ... (55+ SVG files)
│   │
│   └── weather-icons/
│       ├── happy-skies/
│       │   ├── 01d.svg
│       │   ├── 01n.svg
│       │   ├── 02d.svg
│       │   ├── 02n.svg
│       │   ├── 03d.svg
│       │   ├── 04d.svg
│       │   ├── 09d.svg
│       │   ├── 10d.svg
│       │   ├── 10n.svg
│       │   ├── 11d.svg
│       │   ├── 13d.svg
│       │   ├── 50d.svg
│       │   └── unknown.svg
│       ├── soft-skies/
│       │   └── (same 13 icons)
│       ├── sunny-day/
│       │   └── (same 13 icons)
│       └── blue-sky-pro/
│           └── (same 13 icons)
│
├── pexels/
│   └── current/
│       ├── abstract_0.jpg
│       ├── abstract_1.jpg
│       ├── abstract_2.jpg
│       ├── geometric_0.jpg
│       ├── geometric_1.jpg
│       ├── kids_0.jpg
│       ├── minimal_0.jpg
│       └── ... (category_number.jpg format)
│
└── devices/
    └── familydisplay/
        ├── config.json
        ├── layouts/
        │   └── current.json
        └── renders/
            └── latest.png
```

---

## Upload Commands

### 1. Upload Designer HTML
```bash
gsutil cp backend/web/designer/overlay_designer_v4_clean.html \
  gs://family-display-packs/web/designer/overlay_designer_v4_clean.html
```

### 2. Upload SVG Assets (if you have them locally)
```bash
gsutil -m cp -r backend/web/svgs/* \
  gs://family-display-packs/assets/svgs/
```

### 3. Upload Weather Icons (if you have them locally)
```bash
gsutil -m cp -r backend/web/assets/weather-icons/* \
  gs://family-display-packs/assets/weather-icons/
```

### 4. Upload Pexels Images
```bash
gsutil -m cp pexels-images/* \
  gs://family-display-packs/pexels/current/
```

### 5. Create Device Structure
```bash
# Create initial layout
echo '{"name":"Default","elements":[]}' | \
  gsutil cp - gs://family-display-packs/devices/familydisplay/layouts/current.json

# Create initial config
echo '{
  "location": {
    "city": "Darwin",
    "timezone": "Australia/Darwin"
  },
  "preferences": {
    "iconTheme": "happy-skies"
  }
}' | gsutil cp - gs://family-display-packs/devices/familydisplay/config.json
```

---

## Weather Icon Codes Reference

### OpenWeather Icon Codes
| Code | Condition | Description |
|------|-----------|-------------|
| 01d | Clear Sky | Day |
| 01n | Clear Sky | Night |
| 02d | Few Clouds | Day |
| 02n | Few Clouds | Night |
| 03d | Scattered Clouds | Day/Night |
| 04d | Broken Clouds | Day/Night |
| 09d | Shower Rain | Day/Night |
| 10d | Rain | Day |
| 10n | Rain | Night |
| 11d | Thunderstorm | Day/Night |
| 13d | Snow | Day/Night |
| 50d | Mist | Day/Night |
| unknown | Fallback | When code not found |

**Required:** Each theme folder needs all 13 SVG files.

---

## Pexels Image Naming Convention

### Format
```
{category}_{number}.jpg
```

### Examples
```
abstract_0.jpg
abstract_1.jpg
abstract_2.jpg
geometric_0.jpg
geometric_1.jpg
kids_0.jpg
kids_1.jpg
minimal_0.jpg
photo_0.jpg
```

### Categories Detected Automatically
The backend scans `pexels/current/` and extracts category names from filenames (everything before the first underscore).

---

## Device Configuration Format

### config.json
```json
{
  "location": {
    "city": "Darwin",
    "timezone": "Australia/Darwin"
  },
  "preferences": {
    "iconTheme": "happy-skies"
  }
}
```

### Supported Cities (Australian Timezones)
- Darwin (Australia/Darwin)
- Sydney (Australia/Sydney)
- Melbourne (Australia/Melbourne)
- Brisbane (Australia/Brisbane)
- Perth (Australia/Perth)
- Adelaide (Australia/Adelaide)
- Hobart (Australia/Hobart)
- Canberra (Australia/Sydney)

### Supported Icon Themes
- happy-skies
- soft-skies
- sunny-day
- blue-sky-pro

---

## Layout JSON Format

### current.json
```json
{
  "name": "My Layout",
  "meta": {
    "width": 800,
    "height": 480,
    "iconTheme": "happy-skies",
    "pexelsCategory": "abstract"
  },
  "elements": [
    {
      "kind": "text",
      "type": "TEMP",
      "x": 50,
      "y": 50,
      "width": 200,
      "height": 100,
      "fontSize": 48,
      "color": "#ffffff",
      "fontWeight": "700",
      "fontFamily": "Inter",
      "zIndex": 20
    },
    {
      "kind": "svg-overlay",
      "src": "/gcs/assets/svgs/lemon.svg",
      "x": 100,
      "y": 200,
      "width": 120,
      "height": 120,
      "opacity": 1,
      "zIndex": 15
    },
    {
      "kind": "box",
      "x": 0,
      "y": 400,
      "width": 800,
      "height": 80,
      "background": "rgba(0,0,0,0.5)",
      "borderColor": "#ffffff",
      "borderRadius": 0,
      "zIndex": 10
    }
  ]
}
```

---

## Verification Commands

### Check Bucket Contents
```bash
# List all files
gsutil ls -r gs://family-display-packs/

# Check SVGs
gsutil ls gs://family-display-packs/assets/svgs/

# Check weather icons
gsutil ls gs://family-display-packs/assets/weather-icons/happy-skies/

# Check Pexels images
gsutil ls gs://family-display-packs/pexels/current/

# Check designer HTML
gsutil ls gs://family-display-packs/web/designer/
```

### Test File Access
```bash
# Test designer HTML
curl https://family-display-backend-867804884116.australia-southeast1.run.app/designer/

# Test SVG asset
curl https://family-display-backend-867804884116.australia-southeast1.run.app/gcs/assets/svgs/lemon.svg

# Test weather icon
curl https://family-display-backend-867804884116.australia-southeast1.run.app/gcs/assets/weather-icons/happy-skies/01d.svg

# Test API endpoints
curl https://family-display-backend-867804884116.australia-southeast1.run.app/api/list-svgs
curl https://family-display-backend-867804884116.australia-southeast1.run.app/api/list-pexels-categories
```

---

## Notes

### Fonts
Fonts are NOT stored in GCS - they remain in the repo at `backend/web/fonts/` and are served via StaticFiles mount.

### Base.html
Base.html is NOT stored in GCS - it remains in the repo at `backend/web/layouts/base.html` for Playwright rendering.

### Presets
Presets are NOT stored in GCS - they remain in the repo at `backend/web/presets/` and are served via StaticFiles mount.

### What Goes in GCS vs Repo

**GCS (User Content):**
- Designer HTML (for easy updates)
- SVG assets (user can add more)
- Weather icon themes
- Pexels background images
- Device layouts (user-created)
- Device configurations
- Rendered PNG outputs

**Repo (Infrastructure):**
- base.html (rendering template)
- Fonts (web fonts for designer)
- Presets (template layouts)
- Backend code (main.py)
- Requirements and configs

---

## Quick Setup Script

```bash
#!/bin/bash
BUCKET="family-display-packs"

# Upload designer
gsutil cp backend/web/designer/overlay_designer_v4_clean.html \
  gs://$BUCKET/web/designer/overlay_designer_v4_clean.html

# Upload assets (if they exist locally)
gsutil -m cp -r backend/web/svgs/* gs://$BUCKET/assets/svgs/ 2>/dev/null || true
gsutil -m cp -r backend/web/assets/weather-icons/* gs://$BUCKET/assets/weather-icons/ 2>/dev/null || true

# Create device structure
echo '{"name":"Default","elements":[]}' | \
  gsutil cp - gs://$BUCKET/devices/familydisplay/layouts/current.json

echo '{
  "location": {
    "city": "Darwin",
    "timezone": "Australia/Darwin"
  },
  "preferences": {
    "iconTheme": "happy-skies"
  }
}' | gsutil cp - gs://$BUCKET/devices/familydisplay/config.json

echo "✅ Bucket setup complete!"
```

---

## Troubleshooting

### Designer Returns 404
```bash
# Check if file exists
gsutil ls gs://family-display-packs/web/designer/overlay_designer_v4_clean.html

# If missing, upload it
gsutil cp backend/web/designer/overlay_designer_v4_clean.html \
  gs://family-display-packs/web/designer/overlay_designer_v4_clean.html
```

### SVGs Not Showing
```bash
# Check SVG directory
gsutil ls gs://family-display-packs/assets/svgs/

# Test access via GCS proxy
curl https://family-display-backend-867804884116.australia-southeast1.run.app/gcs/assets/svgs/lemon.svg
```

### Weather Icons Not Working
```bash
# Check theme directory
gsutil ls gs://family-display-packs/assets/weather-icons/happy-skies/

# Verify all 13 icons exist
# Should see: 01d, 01n, 02d, 02n, 03d, 04d, 09d, 10d, 10n, 11d, 13d, 50d, unknown.svg
```

### Pexels Categories Empty
```bash
# Check pexels directory
gsutil ls gs://family-display-packs/pexels/current/

# Verify naming format: category_number.jpg
# Example: abstract_0.jpg, geometric_1.jpg
```
