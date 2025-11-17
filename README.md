# kin;D Family Display

> Make a Smile ;D

A complete smart e-ink display system that brings daily artwork, weather, jokes, and curated content to your family's space. Features a cloud-powered backend service and ESP32 firmware for beautiful 7-color e-ink displays.

---

## What is kin;D?

The kin;D Family Display is an intelligent e-ink photo frame that automatically updates with:

- Daily curated artwork from Unsplash
- Real-time weather with beautiful icons
- Dad jokes to brighten your day
- Fully customizable layouts via drag-and-drop designer
- 7-color Spectra-6 e-ink display (800×480)
- Ultra-low power consumption (weeks on battery)

---

## Quick Start

Choose your path:

### For End Users (Setting Up a Device)
1. Flash the firmware to your ESP32 - see [Firmware Quick Start](firmware/README.md#-quick-start-guide-for-beginners)
2. Connect to `KIND-Setup` WiFi network
3. Configure your display via the setup portal
4. Enjoy your new family display!

### For Designers (Customizing Layouts)
1. Open the designer at `http://your-backend-url/designer/`
2. Choose a preset or start from scratch
3. Drag and drop widgets, backgrounds, and text
4. Save your layout and see it on your device

### For Developers (Running the Backend)
1. Clone this repository
2. Set up environment variables - see [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)
3. Run locally with Docker or deploy to Google Cloud Run
4. See [Development](#development) for details

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         kin;D Ecosystem                          │
└──────────────────────────────────────────────────────────────────┘

    Designer UI (Web)          External APIs
         │                          │
         │                     ┌────┴─────┐
         ▼                     ▼          ▼
    ┌─────────────────────────────────────────┐
    │   FastAPI Backend (Cloud Run)           │
    │   • Layout rendering                    │
    │   • Content assembly                    │
    │   • Image generation                    │
    └─────────────┬───────────────────────────┘
                  │
                  ▼
         Google Cloud Storage
         (Layouts, Presets, Frames)
                  │
                  ▼
    ┌─────────────────────────────┐
    │  ESP32 Firmware             │
    │  • WiFi connectivity        │
    │  • RAW7 image decoding      │
    │  • E-ink display control    │
    │  • Deep sleep scheduling    │
    └─────────────┬───────────────┘
                  │
                  ▼
         7-Color E-Ink Display
         (800×480 Spectra-6)
```

### Data Flow

1. **Designer** creates layout JSON → stored in Google Cloud Storage
2. **Backend** fetches content from APIs (weather, artwork, jokes)
3. **Backend** renders HTML layout to PNG using Playwright
4. **Backend** applies 7-color dithering and encodes to RAW7 format
5. **ESP32** wakes up, fetches RAW7 image via HTTP
6. **ESP32** decodes and displays on e-ink screen
7. **ESP32** returns to deep sleep until next scheduled update

---

## Project Components

### 1. Backend Service (`/backend`)

FastAPI-powered cloud service that handles:

- Layout rendering with Playwright (Chromium)
- Content aggregation from external APIs
- Image processing and 7-color dithering
- RESTful API for devices and designer
- Google Cloud Storage integration

**Tech Stack:** Python, FastAPI, Playwright, Google Cloud Run, GCS

[Backend Documentation →](backend/README.md)

### 2. ESP32 Firmware (`/firmware`)

Embedded firmware for ESP32 e-ink development boards:

- WiFi configuration portal with QR code setup
- RAW7 image format decoder
- Spectra-6 (7-color) e-ink driver
- Deep sleep scheduling with RTC
- Physical button controls (factory reset, background reroll)
- OTA update support (optional)

**Tech Stack:** C++, PlatformIO, ESP32, SPI

[Firmware Documentation →](firmware/README.md)

### 3. Designer UI

Drag-and-drop web interface for creating custom layouts:

- Visual layout editor
- Widget library (weather, images, text, jokes)
- Preset themes
- Real-time preview
- Cloud sync via backend API

**Access:** `http://your-backend-url/designer/`

---

## Features

### Backend Features
- **Dynamic Content** - Fresh artwork, weather, and jokes from third-party APIs
- **Headless Rendering** - Playwright renders HTML to pixel-perfect PNGs
- **Designer Workflow** - Full integration with visual layout designer
- **Multi-User Support** - Optional email-based device organization
- **Cloud-Native** - Optimized for Google Cloud Run with horizontal scaling
- **Modular Providers** - Pluggable architecture for content sources

### Firmware Features
- **WiFi Portal** - Easy setup via phone/computer with QR code
- **7-Color Support** - Full Spectra-6 palette (white, black, red, yellow, blue, green, orange)
- **Ultra Low Power** - Deep sleep mode (~10-50 μA) for weeks of battery life
- **Scheduled Updates** - Automatic daily refresh (configurable)
- **Manual Controls** - Physical button for background reroll and factory reset
- **SD Card Caching** - Optional local storage for images
- **Robust Networking** - Retry logic and error handling

---

## Tech Stack

| Component | Technologies |
|-----------|-------------|
| **Backend** | Python 3.11+, FastAPI, Playwright, Chromium |
| **Cloud** | Google Cloud Run, Google Cloud Storage |
| **Firmware** | C++, PlatformIO, ESP32, FreeRTOS |
| **Display** | Spectra-6 E-Ink (7-color, SPI) |
| **APIs** | Unsplash, OpenWeather, icanhazdadjoke |
| **Designer** | HTML5, JavaScript, CSS3 |

---

## Development

### Prerequisites

**For Backend:**
- Python 3.11+
- Node.js (for Playwright)
- Google Cloud SDK
- Docker (optional)

**For Firmware:**
- PlatformIO or VS Code with PlatformIO extension
- USB-C cable for ESP32
- ESP32 e-ink development board

### Local Development

#### Backend Setup

```bash
# Clone repository
git clone https://github.com/snrmed/family-display-backend3.git
cd family-display-backend3

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Install Playwright browsers
playwright install chromium

# Set environment variables (see ENVIRONMENT_VARIABLES.md)
export GCS_BUCKET=your-bucket-name
export ADMIN_TOKEN=your-secret-token
# ... additional vars

# Run locally
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

Open `http://localhost:8080/docs` for API documentation.

#### Firmware Setup

```bash
# Navigate to firmware directory
cd firmware

# Build and upload (PlatformIO CLI)
pio run -t upload

# Monitor serial output
pio device monitor
```

Or use VS Code:
1. Open `firmware` folder in VS Code
2. Click PlatformIO icon
3. Click "Upload"
4. Click "Monitor"

See [Firmware Quick Start Guide](firmware/README.md#-quick-start-guide-for-beginners) for detailed instructions.

### Environment Variables

Key configuration variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `GCS_BUCKET` | Google Cloud Storage bucket name | Yes |
| `PUBLIC_BASE_URL` | Full URL of backend service | Yes |
| `ADMIN_TOKEN` | Admin authentication token | Yes |
| `OPENWEATHER_KEY` | OpenWeather API key | If weather enabled |
| `UNSPLASH_ACCESS_KEY` | Unsplash API key | If Unsplash enabled |
| `ENABLE_RENDERING` | Enable/disable Playwright rendering | No (default: true) |
| `RENDER_WIDTH` | PNG render width | No (default: 800) |
| `RENDER_HEIGHT` | PNG render height | No (default: 480) |

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete reference.

---

## Deployment

### Backend (Google Cloud Run)

```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/family-display-backend

# Deploy to Cloud Run
gcloud run deploy family-display-backend \
  --image gcr.io/PROJECT_ID/family-display-backend \
  --region australia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GCS_BUCKET=your-bucket,ADMIN_TOKEN=your-token
```

Or use the included `cloudbuild.yaml`:

```bash
gcloud builds submit --config cloudbuild.yaml
```

### Firmware (ESP32)

Flash firmware to ESP32 via USB:

```bash
cd firmware
pio run -t upload
```

For mass production, use esptool.py or PlatformIO's firmware export feature.

---

## Project Structure

```
family-display-backend3/
├── README.md                      # This file (unified overview)
├── ENVIRONMENT_VARIABLES.md       # Environment config reference
├── BUCKET_SETUP.md                # GCS bucket setup guide
├── BUCKET_STRUCTURE.txt           # GCS folder organization
├── Dockerfile                     # Backend container definition
├── cloudbuild.yaml                # Cloud Build configuration
├── overlay_designer_simple.html   # Standalone designer tool
│
├── backend/                       # Backend service
│   ├── main.py                    # FastAPI entrypoint
│   ├── requirements.txt           # Python dependencies
│   ├── web/                       # Static web assets
│   │   ├── designer/              # Designer UI
│   │   ├── layouts/               # HTML layout templates
│   │   ├── fonts/                 # Font files
│   │   └── svgs/                  # SVG assets
│   └── docs/                      # Backend documentation
│
└── firmware/                      # ESP32 firmware
    ├── README.md                  # Firmware documentation
    ├── platformio.ini             # PlatformIO configuration
    └── KindDisplay/               # Firmware source
        ├── KindDisplay.ino        # Main Arduino sketch
        ├── config.h               # Configuration settings
        ├── display_driver.cpp/h   # E-ink driver
        ├── wifi_manager.cpp/h     # WiFi setup portal
        ├── raw7_decoder.cpp/h     # Image decoder
        ├── button_handler.cpp/h   # Button controls
        ├── rtc_manager.cpp/h      # Sleep scheduling
        └── sd_manager.cpp/h       # SD card caching
```

---

## Hardware

### Recommended Components

- **Display:** Spectra-6 (E6) 7-Color E-Ink Display (800×480, P730010-MF1-A)
- **Microcontroller:** ESP32 E-Ink Development Board with built-in battery management
- **Connectivity:** WiFi 2.4GHz (ESP32 built-in)
- **Power:** LiPo battery (2000mAh+) or USB-C
- **Enclosure:** Custom 3D-printed or commercial photo frame

### Pin Connections

| EPD Pin | ESP32 GPIO | Function |
|---------|------------|----------|
| BUSY | GPIO 4 | Busy signal |
| RST | GPIO 16 | Reset |
| CS | GPIO 5 | Chip Select |
| DC | GPIO 17 | Data/Command |
| SCK | GPIO 18 | SPI Clock |
| DIN | GPIO 23 | SPI Data |

See [firmware/README.md](firmware/README.md#-hardware-connections) for complete wiring guide.

---

## API Reference

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/raw7` | GET | Fetch RAW7-encoded 7-color image |
| `/v1/frame_bg_reroll` | POST | Generate new background variant |
| `/v1/render` | POST | Trigger layout render |
| `/designer/` | GET | Open layout designer UI |
| `/docs` | GET | Interactive API documentation |

**Authentication:** Admin routes require `admin_token` query parameter.

Example:
```bash
curl "http://your-backend/v1/raw7?device=familydisplay"
```

See backend API docs at `http://your-backend/docs` for complete reference.

---

## Troubleshooting

### Backend Issues

**Playwright fails to launch:**
- Ensure `playwright install chromium` has been run
- Check system dependencies (see [Playwright docs](https://playwright.dev/python/docs/intro))
- Verify sufficient memory on Cloud Run (increase to 2GB+)

**Missing assets:**
- Confirm `GCS_BUCKET` environment variable is set
- Verify service account has Storage Object Admin role
- Check bucket permissions and CORS settings

**Slow rendering:**
- Increase Cloud Run CPU allocation
- Pre-render frames on a schedule
- Consider caching rendered frames in GCS

### Firmware Issues

**Upload failed:**
- Try different USB cable (some are power-only)
- Hold BOOT button during upload
- Install [USB drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) (Windows)

**WiFi connection failed:**
- Use 2.4GHz WiFi (ESP32 doesn't support 5GHz)
- Check password (case-sensitive)
- Ensure good signal strength
- Factory reset: hold button for 6+ seconds

**Display shows red screen:**
- Red indicates error
- Connect serial monitor: `pio device monitor`
- Check error logs for details

**Image not updating:**
- Verify backend URL in `config.h`
- Test endpoint in browser: `http://backend/v1/raw7?device=test`
- Check serial logs for HTTP errors

See component-specific documentation for more help:
- [Backend Troubleshooting](backend/README.md#troubleshooting)
- [Firmware Troubleshooting](firmware/README.md#-troubleshooting)

---

## Contributing

Contributions are welcome! Here's how to help:

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly (backend: `pytest`, firmware: build and flash)
5. Commit with clear messages
6. Push to your fork
7. Open a Pull Request

### Development Guidelines

- Follow existing code style (PEP 8 for Python, Arduino style for firmware)
- Add tests for new backend features
- Document new environment variables
- Update relevant README files
- Test on actual hardware when possible

---

## License

See [LICENSE](LICENSE) file for details.

---

## Support & Community

- **Issues:** [GitHub Issues](https://github.com/snrmed/family-display-backend3/issues)
- **Questions:** Open a discussion or file an issue
- **Pull Requests:** Contributions welcome!

---

## Roadmap

### Planned Features
- [ ] Mobile app for remote configuration
- [ ] Over-the-air (OTA) firmware updates
- [ ] Multi-device management dashboard
- [ ] Additional content providers (calendar, photos, RSS)
- [ ] Power consumption analytics
- [ ] Custom weather icon packs
- [ ] Voice control integration

### Known Limitations
- ESP32 only supports 2.4GHz WiFi networks
- E-ink refresh takes 30-60 seconds
- Rendering requires significant CPU/memory on backend
- 7-color dithering can affect fine details

---

## Acknowledgments

- Waveshare for e-ink display modules and documentation
- Unsplash API for beautiful free artwork
- OpenWeather for weather data
- icanhazdadjoke for bringing the laughs
- PlatformIO and Arduino community for ESP32 tools

---

## Fun Facts

- The "kin;D" name combines "kin" (family) with "kind" (thoughtful)
- Each frame refresh uses less power than a single LED blink
- The 7-color dithering algorithm processes 384,000 pixels per frame
- Your display can run for weeks on a single battery charge

---

> **kin;D — Make a Smile ;D**

Built with love for families who appreciate beautiful, low-tech moments in a high-tech world.
