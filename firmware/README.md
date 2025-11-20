# Kin:D Family Display - Firmware

Complete firmware for 7-color e-ink family displays. Supports multiple hardware platforms with shared codebase.

---

## Supported Devices

This firmware supports **4 different hardware platforms**:

### 1. Seeed reTerminal E1002 (Recommended)

**All-in-one professional solution**

- **MCU**: ESP32-S3R8 (Dual-core 240MHz, 8MB PSRAM, 32MB Flash)
- **Display**: E Ink Spectra 6 (800×480, 7.3") - **Included**
- **Battery**: 2000mAh built-in (3+ months runtime)
- **Sensors**: SHT40 temperature & humidity (I2C), Microphone (I2S), Buzzer
- **Enclosure**: Professional metal case with mounting holes
- **Best for**: Production deployments, sensor integration, medication reminders

[📘 View reTerminal E1002 Documentation →](reterminal-e1002/README.md)

### 2. Seeed XIAO ePaper Display Board EE04

**Ultra-compact DIY solution**

- **MCU**: ESP32-S3 Plus (8MB PSRAM, 32MB Flash)
- **Display**: Supports 7.3" Spectra 6 (800×480) - **Separate purchase**
- **Battery**: User-provided via JST connector
- **Features**: Font chip (GT32L32S0140), 3 user buttons
- **Form factor**: Ultra-compact XIAO size
- **Best for**: DIY projects, custom enclosures, space-constrained builds

[📘 View XIAO EE04 Documentation →](xiao-ee04/README.md)

### 3. Waveshare e-Paper ESP32 Driver Board REV3

**Universal driver board**

- **MCU**: ESP32 Classic (no PSRAM typically)
- **Display**: Universal - works with various Waveshare panels
- **Battery**: User-provided
- **Features**: 24-pin FFC connector for flexibility
- **Best for**: Existing Waveshare display owners, DIY builds

[📘 View Waveshare ESP32 REV3 Documentation →](waveshare-esp32-rev3/README.md)

### 4. Original ESP32 Development Board

**Legacy support**

- **MCU**: ESP32 Classic
- **Display**: Spectra 6 (800×480)
- **Features**: SD card, RTC with CR2032, LiPo charger
- **Best for**: Existing builds, backwards compatibility

[📘 View Original ESP32 Documentation →](KindDisplay/README.md)

---

## Quick Comparison

| Feature | reTerminal E1002 | XIAO EE04 | Waveshare REV3 | Original ESP32 |
|---------|------------------|-----------|----------------|----------------|
| **MCU** | ESP32-S3 (8MB PSRAM) | ESP32-S3 Plus (8MB PSRAM) | ESP32 Classic | ESP32 Classic |
| **Display Included** | ✅ Yes | ❌ Separate | ❌ Separate | ❌ Separate |
| **Battery Included** | ✅ 2000mAh | ❌ User-provided | ❌ User-provided | ❌ User-provided |
| **Temp/Humidity** | ✅ SHT40 | ❌ | ❌ | ❌ |
| **Microphone** | ✅ I2S | ❌ | ❌ | ❌ |
| **Buzzer Reminders** | ✅ GPIO45 | ❌ | ❌ | ❌ |
| **Font Chip** | ❌ | ✅ GT32L32S0140 | ❌ | ❌ |
| **Enclosure** | ✅ Metal case | ❌ DIY | ❌ DIY | ❌ DIY |
| **Form Factor** | All-in-one 7.3" | Compact board | Driver board | Dev board |
| **PSRAM** | ✅ 8MB | ✅ 8MB | ❌ Limited | ❌ Limited |
| **SD Card** | ❌ Not needed | ❌ Not needed | ⚠️ Optional | ✅ Supported |
| **Price Range** | $$$ | $$ | $ | $ |

---

## 🚀 Quick Start

### Step 1: Choose Your Device

Select your hardware from the table above and navigate to its specific README:

- **reTerminal E1002**: [reterminal-e1002/README.md](reterminal-e1002/README.md)
- **XIAO EE04**: [xiao-ee04/README.md](xiao-ee04/README.md)
- **Waveshare ESP32 REV3**: [waveshare-esp32-rev3/README.md](waveshare-esp32-rev3/README.md)
- **Original ESP32**: [KindDisplay/README.md](KindDisplay/README.md)

### Step 2: Install PlatformIO

```bash
# Install PlatformIO Core
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py
python3 get-platformio.py

# Or use VS Code extension
# https://platformio.org/install/ide?install=vscode
```

### Step 3: Build & Upload

Navigate to your device's folder and build:

```bash
# For reTerminal E1002
cd firmware/reterminal-e1002
pio run -t upload
pio device monitor

# For XIAO EE04
cd firmware/xiao-ee04
pio run -t upload
pio device monitor

# For Waveshare ESP32 REV3
cd firmware/waveshare-esp32-rev3
pio run -t upload
pio device monitor

# For Original ESP32
cd firmware/KindDisplay
pio run -t upload
pio device monitor
```

### Step 4: WiFi Setup

1. Power on device - it starts in AP mode
2. Connect to WiFi network `KIND-Setup` (password: `kind1234`)
3. Navigate to `http://192.168.4.1`
4. Enter your WiFi credentials and backend URL
5. Device reboots and fetches first image

---

## Common Features

All devices share these core features:

### Display
- **Panel**: E Ink Spectra 6 (800×480 pixels, 7.3")
- **Colors**: 7 (White, Black, Red, Yellow, Blue, Green, Orange)
- **Refresh**: ~30-60 seconds for full color update

### Power Management
- **Deep Sleep**: <100μA between updates
- **Daily Wake**: Configurable (default 1:00 AM)
- **Button Wake**: Manual refresh via button press
- **Battery Life**: 3+ months on 2000mAh (reTerminal E1002, 1 update/day)

### WiFi Configuration
- **Captive Portal**: Easy setup via phone/browser
- **Factory Reset**: Long press button to reset credentials
- **OTA Updates**: Firmware updates via network (planned)

### Image Delivery
- **Format**: RAW7 (192KB compressed, 2 pixels per byte)
- **Caching**: SPIFFS + PSRAM for reliability
- **Backend**: Connects to Kin:D backend for daily images

---

## Architecture Decisions

### PSRAM-Only (No SD Card) - ESP32-S3 Devices

**reTerminal E1002** and **XIAO EE04** use PSRAM instead of SD card:

**Benefits:**
- ✅ Faster access than SD card
- ✅ More reliable (no SD corruption)
- ✅ Simpler hardware (one less component)
- ✅ 8MB PSRAM stores active image + working buffers
- ✅ SPIFFS provides persistent cache

**Memory Layout:**
```
┌─────────────────────────────────┐
│ PSRAM (8MB)                     │
│  - HTTP receive buffer          │
│  - Image decompression          │
│  - Temporary working buffers    │
│  └─ ~7.8MB available            │
├─────────────────────────────────┤
│ SPIFFS (6-8MB)                  │
│  - Last successful image (192KB)│
│  - Welcome screen (192KB)       │
│  - WiFi credentials (NVS)       │
│  └─ ~7.5MB available            │
└─────────────────────────────────┘
```

### RAW7 Format (Not PNG)

All devices use RAW7 for image delivery:

**Why RAW7?**
- ✅ Smaller file size: 192KB vs 300-500KB PNG
- ✅ Less WiFi power consumption
- ✅ Backend does color quantization (better quality)
- ✅ Device just unpacks (faster, less CPU)
- ✅ Predictable memory usage

**RAW7 Encoding:**
- 2 pixels per byte (4 bits each)
- High nibble = first pixel, low nibble = second pixel
- Values 0-6 map to 7 colors

**Color Palette:**

| Index | Color  | RGB         |
|-------|--------|-------------|
| 0     | White  | 255,255,255 |
| 1     | Black  | 0,0,0       |
| 2     | Red    | 220,0,0     |
| 3     | Yellow | 255,216,0   |
| 4     | Blue   | 0,0,200     |
| 5     | Green  | 0,160,0     |
| 6     | Orange | 255,128,0   |

---

## Sensor Integration (reTerminal E1002 Only)

The reTerminal E1002 includes environmental sensors and a buzzer for advanced features.

### Temperature & Humidity (SHT40)

**Hardware:**
- I2C sensor on SDA=19, SCL=20
- Automatic reading on daily wake
- Sent to backend for display overlay

**Data Flow:**
```http
GET /v1/raw7?device=xxx&temp=72.5&humidity=45
```

Backend can overlay climate data on family photo display.

### Buzzer Reminders - Todo Integration

The reTerminal E1002 supports **audio reminders for todo items** created in the designer.

#### How It Works

1. **In Designer**: Toggle buzzer on/off for each todo item (🔔/🔕 icon)
2. **Backend**: Generates daily buzzer schedule from enabled todos
3. **Device**: Sets RTC alarms and wakes to beep 5 minutes before task time
4. **Battery Impact**: Negligible (~4% reduction for 3 daily reminders)

#### Example Todo with Buzzer

```json
{
  "emoji": "💊",
  "time": "8:00am",
  "task": "Morning medication",
  "days": ["mon", "tue", "wed", "thu", "fri"],
  "buzzer": true
}
```

#### Backend Response

Backend sends schedule via HTTP header:

```http
HTTP/1.1 200 OK
Content-Type: application/octet-stream
X-Buzzer-Schedule: 07:55:3:100:200,13:55:3:100:200,19:55:3:100:200

[RAW7 binary data...]
```

**Header Format:** `HH:MM:beeps:on_ms:off_ms`
- `07:55` - Time (24-hour format)
- `3` - Number of beeps
- `100` - Beep on duration (milliseconds)
- `200` - Beep off duration (milliseconds)

#### Firmware Behavior

1. Parses buzzer schedule on daily wake
2. Programs ESP32 RTC alarms for each todo time
3. Wakes at alarm time, beeps, returns to sleep
4. No WiFi needed for buzzer wakes (works offline)

#### Perfect For

- 💊 Medication reminders (2-3x daily)
- 📅 Appointment alerts
- 🏫 School/work schedules
- 🍽️ Meal time prompts
- 🏠 Smart home notifications

#### Battery Impact

**Without buzzer reminders:** ~303 days (10 months) on 2000mAh battery

**With 3 daily buzzer reminders:** ~291 days (9.7 months) on 2000mAh battery

**Difference:** Only 12 days - totally acceptable!

#### Documentation

- [Todo Buzzer Integration Guide](TODO_BUZZER_INTEGRATION.md) - Complete implementation details
- [JSON Format Specification](../JSON_FORMAT_TODO_BUZZER.md) - Todo JSON format with buzzer
- [reTerminal E1002 README](reterminal-e1002/README.md) - Device-specific documentation

---

## Project Structure

```
firmware/
├── README.md                      # This file (unified documentation)
│
├── reterminal-e1002/              # Seeed reTerminal E1002 (ESP32-S3, sensors)
│   ├── platformio.ini
│   ├── src/ (copies from shared/)
│   └── README.md
│
├── xiao-ee04/                     # Seeed XIAO ePaper EE04 (ESP32-S3 Plus, compact)
│   ├── platformio.ini
│   ├── src/ (copies from shared/)
│   └── README.md
│
├── waveshare-esp32-rev3/          # Waveshare ESP32 Driver Board REV3
│   ├── platformio.ini
│   ├── src/ (copies from shared/)
│   └── README.md
│
├── KindDisplay/                   # Original ESP32 dev board (legacy)
│   ├── KindDisplay.ino
│   ├── config.h
│   └── *.cpp/h
│
├── shared/                        # Shared code for all devices
│   ├── KindDisplay.ino            # Main firmware
│   ├── display_driver.cpp/h       # Spectra-6 display controller
│   ├── wifi_manager.cpp/h         # Captive portal WiFi configuration
│   ├── raw7_decoder.cpp/h         # Streaming RAW7 image decoder
│   ├── flash_cache.cpp/h          # SPIFFS-based persistent cache
│   ├── rtc_manager.cpp/h          # Deep sleep and wake scheduling
│   ├── battery.cpp/h              # Battery monitoring and management
│   ├── button_handler.cpp/h       # Button/switch input handling
│   ├── hardware_config.h          # Multi-device pin mappings
│   └── ...
│
├── ARCHITECTURE_DECISIONS.md      # Design rationale and decisions
├── TODO_BUZZER_INTEGRATION.md     # Buzzer reminder implementation guide
├── README_MULTI_DEVICE.md         # Multi-device migration guide (legacy)
└── SEEED_DEVICES.md               # Seeed device migration notes (legacy)
```

### Device Selection

Each device folder has its own `platformio.ini` that defines:

```ini
build_flags =
    -D DEVICE_RETERMINAL_E1002  # Or DEVICE_XIAO_EE04, DEVICE_WAVESHARE_ESP32_REV3
```

This automatically selects the correct pin mappings from `hardware_config.h`.

---

## How It Works

### Image Pipeline

1. **Backend** generates display content (weather, photos, todos, etc.)
2. **Backend** applies Floyd-Steinberg dithering for 7 colors
3. **Backend** encodes to RAW7 format (2 pixels per byte)
4. **Device** fetches RAW7 via HTTP GET `/v1/raw7?device=familydisplay`
5. **Device** unpacks nibbles to pixel indices (0-6)
6. **Device** sends to Spectra-6 display via SPI
7. **Display** refreshes (takes ~30-60 seconds for 7-color)

### Daily Operation

1. Device wakes at scheduled time (default 1:00 AM)
2. Connects to WiFi
3. Fetches RAW7 image from backend
4. Updates e-ink display
5. Returns to deep sleep
6. (reTerminal E1002 only) Wakes for buzzer reminders

### Button Controls

**Original ESP32 / Waveshare:**
- **Single press**: Background reroll (get new variant)
- **6 rapid presses**: Factory reset

**reTerminal E1002:**
- **Green button**: Wake/refresh
- **White button**: User-defined action

**XIAO EE04:**
- **KEY0/KEY1/KEY2**: User-defined actions

---

## Configuration

Each device has its own `config.h` in the `src/` folder. Common settings:

### Wake Schedule

```cpp
#define WAKE_HOUR     1   // Hour (0-23)
#define WAKE_MINUTE   0   // Minute (0-59)
```

### Backend URL

```cpp
#define BACKEND_URL   "https://your-backend.app"
```

### Battery Thresholds (if supported)

```cpp
#define BATTERY_LOW_THRESHOLD 20       // Show warning
#define BATTERY_CRITICAL_THRESHOLD 10  // Extended sleep
```

### Debug Output

```cpp
#define DEBUG_SERIAL  true   // Set to false to disable debug output
```

---

## Troubleshooting

### Device-Specific Issues

See individual device READMEs:
- [reTerminal E1002 Troubleshooting](reterminal-e1002/README.md#troubleshooting)
- [XIAO EE04 Troubleshooting](xiao-ee04/README.md#troubleshooting)
- [Waveshare ESP32 REV3 Troubleshooting](waveshare-esp32-rev3/README.md#troubleshooting)

### Common Issues

**Build Errors**

Check that you're in the correct device folder:
```bash
pwd  # Should show firmware/reterminal-e1002 (or xiao-ee04, waveshare-esp32-rev3)
```

**Wrong Device Selected**

Verify correct device in platformio.ini:
```ini
build_flags =
    -D DEVICE_RETERMINAL_E1002  # Must match your hardware!
```

**Display Not Updating**

1. Check backend URL in `config.h`
2. Verify backend is accessible from device's network
3. Check serial monitor for HTTP errors
4. Test endpoint in browser: `http://YOUR_BACKEND/v1/raw7?device=familydisplay`

**WiFi Connection Failed**

1. Check signal strength
2. Verify credentials (case-sensitive!)
3. Use 2.4GHz WiFi (ESP32 doesn't support 5GHz)
4. Factory reset and try again

**Memory Issues (ESP32 Classic only)**

If using Waveshare ESP32 REV3 or Original ESP32:
- Reduce HTTP buffer size in config.h
- Disable debug logging
- Use SD card for caching (original ESP32 only)

---

## Hardware Purchase Links

- [Seeed reTerminal E1002](https://www.seeedstudio.com/reTerminal-E1002-p-6533.html) - All-in-one solution
- [Seeed XIAO EE04](https://www.seeedstudio.com/XIAO-ePaper-Board-ESP32-S3-EE04-with-7-3-spectratm-6-ePaper-Display-Bundle-Kit.html) - Compact board
- [Waveshare ESP32 Driver Board](https://www.waveshare.com/e-paper-esp32-driver-board.htm) - Universal driver

---

## Contributing

When contributing device-specific fixes:
- Make changes in the specific device folder if it's device-specific
- Make changes in `firmware/shared/` if it affects all devices
- Test on multiple devices when modifying shared code

---

## Additional Resources

- [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) - Design decisions and rationale
- [TODO_BUZZER_INTEGRATION.md](TODO_BUZZER_INTEGRATION.md) - Buzzer implementation guide
- [JSON_FORMAT_TODO_BUZZER.md](../JSON_FORMAT_TODO_BUZZER.md) - Todo JSON specification
- [SEEED_DEVICES.md](SEEED_DEVICES.md) - Seeed device migration notes

---

## Support

For issues or questions:
1. Check device-specific README
2. Review serial debug output at 115200 baud
3. Check backend logs
4. Review [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)
5. Open an issue in the repository

---

## License

Same as main project.

---

**Enjoy your Kin:D Family Display! 🎨✨**
