# Dynamic Text Types Reference

This document lists all supported dynamic text types that can be used in Kin:D layout elements. These types automatically populate with live data from the backend when rendering.

---

## 📋 Overview

Dynamic text types allow layout elements to display real-time information without hardcoding values. When you set an element's `type` property to one of these values, the renderer will automatically populate it with the appropriate data.

### Usage in JSON

```json
{
  "kind": "text",
  "type": "TEMP",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 60,
  "fontSize": 32,
  "color": "#ffffff"
}
```

---

## 🌤️ Weather Types

### Temperature

| Type | Output Example | Description |
|------|----------------|-------------|
| `TEMP` | `31°` | Current temperature |
| `WEATHER_TEMP` | `31°` | Current temperature (alias) |

### Location

| Type | Output Example | Description |
|------|----------------|-------------|
| `CITY` | `Darwin` | City name |
| `WEATHER_CITY` | `Darwin` | City name (alias) |

### Weather Conditions

| Type | Output Example | Description |
|------|----------------|-------------|
| `WEATHER_DESC` | `Scattered Clouds` | Short weather description |
| `WEATHER_DESC_EXTENDED` | `scattered clouds` | Extended weather description |
| `WEATHER_NOTE` | `Scattered Clouds` | Weather note (alias for DESC) |

### Temperature Range

| Type | Output Example | Description |
|------|----------------|-------------|
| `WEATHER_MINMAX` | `26° / 33°` | Today's min/max temperatures |
| `MINMAX` | `26° / 33°` | Today's min/max (alias) |

### Weather Metrics

| Type | Output Example | Description |
|------|----------------|-------------|
| `HUMIDITY` | `58%` | Current humidity percentage |
| `WEATHER_HUMIDITY` | `58%` | Current humidity (alias) |
| `RAIN` | `0mm` | Rainfall amount |
| `WIND` | `6 km/h` | Wind speed |

### Tomorrow's Forecast

| Type | Output Example | Description |
|------|----------------|-------------|
| `TOMORROW_DESC` | `Light Rain` | Tomorrow's weather description |
| `TOMORROW_TEMP` | `29° / 35°` | Tomorrow's min/max temperatures |

### Weather Icon

| Type | Usage | Description |
|------|-------|-------------|
| `WEATHER_ICON` | For icon elements | Displays current weather icon emoji |

**Note:** For SVG weather icons, use `kind: "svg-overlay"` with `src: "weather-icon"` instead.

---

## 📅 Date & Time Types

| Type | Output Example | Description |
|------|----------------|-------------|
| `DATE` | `Thu, 06 Nov` | Current date formatted for display |

---

## 😄 Content Types

| Type | Output Example | Description |
|------|----------------|-------------|
| `JOKE` | `Why don't scientists trust atoms? Because they make up everything!` | Random dad joke from API |

---

## 🔧 Custom Text

| Type | Usage | Description |
|------|-------|-------------|
| `CUSTOM` | User-defined | Displays the text from the `text` property |

**Example:**
```json
{
  "kind": "text",
  "type": "CUSTOM",
  "text": "Good Morning!",
  "x": 100,
  "y": 100
}
```

---

## 📊 Data Source Mapping

### Weather Data Structure (from backend)

```json
{
  "weather": {
    "temp": 33,
    "humidity": 58,
    "rain": 0,
    "wind": 6,
    "icon": "03d",
    "desc": "Scattered Clouds",
    "desc_extended": "scattered clouds",
    "temp_min": 31,
    "temp_max": 33,
    "city": "Darwin",
    "tomorrow": {
      "temp_min": 29,
      "temp_max": 35,
      "desc": "Partly Cloudy"
    }
  }
}
```

### Other Data

```json
{
  "date": "Thu, 06 Nov",
  "dad_joke": "What do you call a fake noodle? An impasta!"
}
```

---

## ✅ Type Aliases

For maximum compatibility, both short and long forms are supported:

| Short Form | Long Form | Recommended |
|------------|-----------|-------------|
| `TEMP` | `WEATHER_TEMP` | Either |
| `CITY` | `WEATHER_CITY` | Either |
| `HUMIDITY` | `WEATHER_HUMIDITY` | Either |
| `MINMAX` | `WEATHER_MINMAX` | `WEATHER_MINMAX` |

**Recommendation:** Use the short forms (`TEMP`, `CITY`, `HUMIDITY`) for brevity, or prefixed forms (`WEATHER_*`) for clarity in large layouts.

---

## 🎨 Usage Examples

### Simple Temperature Display

```json
{
  "kind": "text",
  "type": "TEMP",
  "x": 50,
  "y": 50,
  "width": 150,
  "height": 80,
  "fontSize": 48,
  "color": "#ffffff",
  "fontWeight": "700",
  "textShadowType": "glow",
  "textShadowColor": "#000000",
  "textShadowIntensity": 1
}
```

### Weather Description with Shadow

```json
{
  "kind": "text",
  "type": "WEATHER_DESC_EXTENDED",
  "x": 100,
  "y": 200,
  "width": 300,
  "height": 50,
  "fontSize": 24,
  "color": "#ffffff",
  "fontFamily": "Inter",
  "textShadowType": "shadow",
  "textShadowColor": "#000000",
  "textShadowIntensity": 1.5
}
```

### Dad Joke Card

```json
{
  "kind": "text",
  "type": "JOKE",
  "x": 80,
  "y": 280,
  "width": 640,
  "height": 150,
  "fontSize": 22,
  "color": "#000000",
  "fontWeight": "600",
  "fontFamily": "Public Sans",
  "textShadowType": "glow",
  "textShadowColor": "#ffffff",
  "textShadowIntensity": 2
}
```

### Date Display

```json
{
  "kind": "text",
  "type": "DATE",
  "x": 620,
  "y": 20,
  "width": 160,
  "height": 40,
  "fontSize": 18,
  "color": "#ffffff",
  "fontWeight": "700"
}
```

---

## 🔄 Backend Integration

### Required Backend Configuration

Ensure these environment variables are set:

```bash
ENABLE_OPENWEATHER=true
OPENWEATHER_KEY=your_api_key_here
ENABLE_JOKES_API=true
DEFAULT_CITY=Darwin
```

### Data Flow

```
Designer → saves JSON with type
           ↓
Backend → reads layout JSON
           ↓
Backend → fetches weather/joke data
           ↓
Backend → passes data to base.html
           ↓
base.html → resolves type → displays data
```

---

## 🐛 Troubleshooting

### Element shows no text

**Possible causes:**
1. Type name misspelled
2. Backend API not enabled (check `ENABLE_OPENWEATHER`)
3. API key not configured
4. Network timeout fetching data

**Solution:** Check `/v1/debug/render_data` endpoint to see what data is available.

### Type not recognized

**Error:** Element displays blank or shows fallback text

**Solution:** Verify the type name matches one in this document exactly (case-sensitive).

### Temperature shows "--°"

**Cause:** Weather API returned no data or failed

**Solution:** 
1. Check `OPENWEATHER_KEY` is valid
2. Verify city name is correct in device config
3. Check backend logs for API errors

---

## 📝 Notes

1. **Case Sensitive:** Type names are case-sensitive. Use uppercase exactly as shown.
2. **Fallback Values:** If data is unavailable, elements show fallback text (e.g., `--°`, `No data`, `--° / --°`).
3. **Custom Text:** Use `type: "CUSTOM"` and set the `text` property for static content.
4. **Future Types:** More types (quotes, calendar events, etc.) may be added in future versions.
5. **Compatibility:** Both old (backend/web/layouts/base.html) and new base.html support all these types.

---

## 🚀 Adding New Types

To add a new dynamic type:

1. **Update backend** (`main.py`) to provide the data
2. **Update base.html** `resolveDynamicText()` function
3. **Update designer** `getDynamicText()` and dropdown options
4. **Document here** with example and usage

Example:

```javascript
// In base.html
case "QUOTE":
  return data.quote || "No quote today";
```

---

## 📚 Related Documentation

- [Backend Features & Config](backend/docs/KIN_D_BACKEND_FEATURES_AND_CONFIG_FULL.md)
- [Bucket Structure](BUCKET_STRUCTURE.txt)
- [Bucket Setup Guide](BUCKET_SETUP.md)

---

**Last Updated:** November 6, 2025  
**Version:** 4.0  
**Maintained by:** Kin:D Project
