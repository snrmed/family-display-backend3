# Kin:D Designer & Backend - Project State Reference
**Last Updated:** 2025-11-03  
**Status:** Production Ready ✅  
**Purpose:** Reference for future Claude conversations about this project

---

## 🎯 Project Overview

**Name:** Kin:D Family Display  
**Repo:** https://github.com/snrmed/family-display-backend3  
**Live Backend:** https://family-display-backend-867804884116.australia-southeast1.run.app  
**GCS Bucket:** family-display-packs  
**Canvas Size:** 800x480 (e-ink display)

**Purpose:** Cloud-rendered display system for family e-ink devices showing weather, jokes, calendar, and custom layouts with SVG graphics.

---

## ✅ Recent Major Fixes (2025-11-03)

### Issue: SVG Rendering Failure
**Problem:** Playwright using `file://` protocol couldn't fetch paths like `/gcs/assets/svgs/lemon.svg`, resulting in "svg" text instead of actual icons.

**Root Cause:** 
- base.html tried to fetch relative/absolute paths that file:// protocol can't resolve
- Missing `svg_base` with full PUBLIC_BASE_URL in render context
- No URL resolution logic for converting paths to full URLs

**Solution Implemented:**
1. **Backend (main.py):** Added `svg_base` field to render context with full URL
2. **Template (base.html):** Added `resolveUrl()` function to convert all paths to absolute URLs
3. **Weather icons:** Generate full URLs using `make_public_url()`

**Files Modified:**
- `backend/main.py` - Added svg_base to render context
- `backend/web/layouts/base.html` - Added URL resolution logic

**Status:** ✅ Fixed and deployed. All SVGs now render correctly.

---

## 📁 Current File Structure

```
backend/
├── main.py                              # FastAPI backend
├── web/
│   ├── designer/
│   │   └── overlay_designer_v3_full.html    # Layout designer UI
│   ├── layouts/
│   │   └── base.html                    # Render template for Playwright
│   ├── fonts/                           # Web fonts
│   ├── svgs/                            # (deprecated - now in GCS)
│   ├── presets/
│   │   ├── Theme 1.json
│   │   ├── Theme 2.json
│   │   └── ... Theme 10.json
│   └── assets/
│       └── weather-icons/               # (deprecated - now in GCS)
└── docs/
    ├── KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md
    ├── weather_icons.md
    └── live_icons.md

GCS Bucket (family-display-packs):
├── assets/
│   ├── svgs/                    # 55+ custom SVG files
│   │   ├── candy.svg
│   │   ├── lemon.svg
│   │   ├── glass_card_aqua.svg
│   │   ├── dad_joke_card_lime.svg
│   │   └── ... (see SVG_CATALOG.md)
│   └── weather-icons/           # 4 themes × 13 icons
│       ├── happy-skies/
│       ├── soft-skies/
│       ├── sunny-day/
│       └── blue-sky-pro/
├── layouts/
│   └── familydisplay.json       # Active layout
└── renders/
    └── familydisplay/
        └── latest.png           # Last rendered frame
```

---

## 🔧 Key Technical Details

### Environment Variables (Critical)
```bash
PUBLIC_BASE_URL=https://family-display-backend-867804884116.australia-southeast1.run.app
GCS_BUCKET=family-display-packs
ENABLE_RENDERING=true
ENABLE_PEXELS=true
ENABLE_OPENWEATHER=true
ENABLE_JOKES_API=true
WEATHER_ICON_PACK=happy-skies
DEFAULT_CITY=Darwin
RENDER_WIDTH=800
RENDER_HEIGHT=480
```

### API Endpoints
```
GET  /                                      # Service info
GET  /designer/                             # Designer UI
GET  /v1/render_data?device=familydisplay   # JSON context for rendering
GET  /v1/frame?device=familydisplay         # Rendered PNG
GET  /gcs/{path}                            # GCS asset proxy
GET  /layouts/{device}                      # Get layout JSON
POST /admin/layouts/{device}                # Save layout JSON
GET  /admin/render_now?token=adm_860510     # Force render
```

### URL Resolution Pattern (CRITICAL)
```python
# Backend: Always pass full URLs in context
svg_base = make_public_url("gcs/assets/svgs")
# Returns: "https://family-display-backend-867804884116.australia-southeast1.run.app/gcs/assets/svgs"

context = {
    "layout": layout_json,
    "svg_base": svg_base,  # Full URL, not relative path
    "weather": {
        "icon_url": make_public_url(f"gcs/assets/weather-icons/{theme}/{code}.svg")
    }
}
```

```javascript
// base.html: Resolve all paths to full URLs
function resolveUrl(path, svg_base) {
    if (path.startsWith("http")) return path;
    if (path.startsWith("/")) {
        const base = svg_base.split("/gcs/")[0];
        return base + path;
    }
    return svg_base + "/" + path;
}
```

---

## 🎨 Layout JSON Structure

### Standard Format
```json
{
  "name": "Layout Name",
  "meta": {
    "iconTheme": "happy-skies",
    "width": 800,
    "height": 480,
    "description": "Optional description"
  },
  "elements": [
    {
      "id": "unique-id",
      "kind": "text|icon|box",
      "x": 0,
      "y": 0,
      "w": 100,
      "h": 100,
      ...type-specific properties
    }
  ]
}
```

### Element Types

#### Text Element
```json
{
  "kind": "text",
  "type": "CITY|TEMP|HUMIDITY|DATE|JOKE|CUSTOM",
  "fontFamily": "Inter",
  "fontSize": 24,
  "color": "#ffffff",
  "weight": "400"
}
```

#### Icon/SVG Element
```json
{
  "kind": "icon",
  "src": "/gcs/assets/svgs/lemon.svg"
  // OR
  "src": "weather-icon"  // Special: uses live weather icon
}
```

#### Box Element
```json
{
  "kind": "box",
  "radius": 20,
  "fill": "rgba(255,255,255,0.1)",
  "border": "1px solid rgba(255,255,255,0.2)",
  "shadow": "0 8px 24px rgba(0,0,0,0.3)"
}
```

---

## 🎨 SVG Asset Inventory (55+ files)

### Categories
1. **Color Circles (16):** candy, lemon, mint, sunset, twilight, cool_blue, classic, mono_silver (+ white_inner variants)
2. **Glass Cards (4):** glass_card_aqua, glass_card_sky, glass_card_sunset, glass_card_violet
3. **Weather Cards (8):** weather_card_blue, weather_card_coral, weather_orientation_day, etc.
4. **Dad Joke Cards (4):** dad_joke_card_lime, dad_joke_card_mint, dad_joke_card_sky, dad_joke_card_tangerine
5. **Flat Posters (8):** flat_poster_circle_red/blue/green/black, flat_poster_rounded_*
6. **Backgrounds (11):** blob-scatter-haikei, layered-waves-haikei, low-poly-grid-haikei, etc.
7. **Special (3):** frosty, night, sunny

### Asset Paths
```
All SVGs: /gcs/assets/svgs/{filename}.svg
Weather icons: /gcs/assets/weather-icons/{theme}/{code}.svg
```

### Weather Icon Themes
- `happy-skies` - Kid-friendly faces and cheerful colors
- `soft-skies` - Gentle pastel minimalist icons  
- `sunny-day` - Clean OpenWeather-style defaults
- `blue-sky-pro` - Detailed professional icons

---

## 🔄 Typical Workflows

### Deploy New Layout
```bash
# 1. Create/modify JSON
# 2. Upload to GCS
gsutil cp layout.json gs://family-display-packs/layouts/familydisplay.json

# 3. Test render
curl "https://family-display-backend-867804884116.australia-southeast1.run.app/v1/frame?device=familydisplay" -o test.png
```

### Update Backend Code
```bash
# 1. Modify main.py or base.html
# 2. Commit to GitHub
git add backend/
git commit -m "Description"
git push

# 3. Cloud Build auto-deploys to Cloud Run
```

### Add New SVG Asset
```bash
# 1. Upload to GCS
gsutil cp new_icon.svg gs://family-display-packs/assets/svgs/

# 2. Use in layout
{
  "kind": "icon",
  "src": "/gcs/assets/svgs/new_icon.svg"
}
```

---

## ⚠️ Common Issues & Solutions

### Issue: SVG shows as "svg" text
**Cause:** Path not resolving to full URL  
**Fix:** Ensure svg_base in render context, check URL resolution logic  
**Check:** Browser console logs, backend logs for fetch errors

### Issue: Weather icon broken
**Cause:** iconTheme invalid or weather API failing  
**Fix:** Verify meta.iconTheme is valid, check /v1/render_data response  
**Check:** weather.icon_url should be full URL

### Issue: Box elements not rendering
**Cause:** JSON structure invalid or render failing  
**Fix:** Validate JSON, check element properties  
**Check:** Elements have x, y, w, h, kind fields

### Issue: Elements positioned wrong
**Cause:** Coordinates outside canvas bounds  
**Fix:** X should be 0-800, Y should be 0-480  
**Check:** Width + X <= 800, Height + Y <= 480

---

## 🎯 Design Patterns & Best Practices

### Color Transparency (Glass Morphism)
```json
"fill": "rgba(255,255,255,0.08-0.15)"
"border": "1px solid rgba(255,255,255,0.15-0.25)"
"shadow": "0 8px 24px rgba(0,0,0,0.25)"
```

### Typography
```json
// Headers
"fontSize": 24-48,
"weight": "600-700"

// Body
"fontSize": 16-20,
"weight": "400"

// Small text
"fontSize": 14-15,
"weight": "300-400"
```

### Layout Composition
- Weather info: Top left or full width card
- Date: Secondary card or below weather
- Decorative SVGs: Scattered or row-based
- Dad joke: Bottom, full width
- Background layers: Below content, full width

---

## 📝 Important Notes for Future Sessions

### When Working on Designer HTML
- Designer is at: `backend/web/designer/overlay_designer_v3_full.html`
- Designer saves/loads to GCS via API endpoints
- Uses localStorage for draft state
- Should support all element types (text, icon, box)
- Drag/drop positioning, visual editing

### When Working on Layouts
- Always validate JSON structure
- Test with small layout first
- Use full paths: `/gcs/assets/svgs/filename.svg`
- Weather icon uses special value: `"src": "weather-icon"`
- IconTheme in meta affects weather icons only

### When Working on Backend
- PUBLIC_BASE_URL must be set in Cloud Run
- All asset URLs must be absolute for Playwright
- svg_base passed in render context
- GCS proxy route handles /gcs/* paths
- Playwright renders from file:// protocol

### When Adding Features
- SVG assets go in GCS bucket, not repo
- Weather icon themes are complete (4 themes × 13 icons)
- Layout presets are in web/presets/
- Backend is stateless (all data in GCS)

---

## 🔗 Related Documentation

**In This Project:**
- `backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md` - Backend features
- `backend/docs/weather_icons.md` - Weather icon implementation
- `KIND_DESIGNER_ARCHITECTURE_SPEC.md` - Future multi-user plans (Phase 1-3)

**External (Created 2025-11-03):**
- LAYOUTS_README.md - Layout design guide
- SVG_CATALOG.md - Complete SVG asset reference
- FIX_SUMMARY.md - Technical details of rendering fixes
- DEPLOYMENT_GUIDE.md - Deployment instructions

---

## 🧪 Quick Tests

```bash
# Test backend health
curl https://family-display-backend-867804884116.australia-southeast1.run.app/

# Test render data (should include svg_base)
curl "https://family-display-backend-867804884116.australia-southeast1.run.app/v1/render_data?device=familydisplay" | jq .svg_base

# Test GCS asset access
curl "https://family-display-backend-867804884116.australia-southeast1.run.app/gcs/assets/svgs/lemon.svg"

# Test render
curl "https://family-display-backend-867804884116.australia-southeast1.run.app/v1/frame?device=familydisplay" -o test.png
```

---

## 💡 Context for AI Assistants

**When user mentions:**
- "SVG not rendering" → Check URL resolution (svg_base, resolveUrl function)
- "weather icon broken" → Check iconTheme validity, weather.icon_url
- "designer" → Refers to overlay_designer_v3_full.html
- "layout" → Refers to JSON file in GCS bucket
- "lemon" → One of 55+ SVG assets in GCS
- "glass card" → Glass morphism background SVGs
- "rendering" → Playwright + base.html → PNG output

**Key understanding:**
- Playwright uses file:// protocol, needs full absolute URLs
- GCS assets proxied through /gcs/* endpoint
- All paths must resolve to https:// URLs for fetch() to work
- svg_base is critical - must be full URL in render context
- Weather icons automatically selected based on meta.iconTheme

**Status:** System is working correctly as of 2025-11-03. SVGs render, weather icons display, boxes show properly. Five professional layouts created and ready for deployment.

---

**Version:** 1.0  
**Last Verified:** 2025-11-03  
**Next Review:** When designer HTML needs updates  
**Status:** ✅ Production Ready
