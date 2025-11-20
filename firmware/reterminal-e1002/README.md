# Seeed reTerminal E1002 Firmware

Firmware for the Seeed reTerminal E1002 - ESP32-S3 powered e-paper family display with environmental sensors.

## Hardware Specifications

- **MCU**: ESP32-S3R8 (Dual-core 240MHz, 8MB PSRAM, 32MB Flash)
- **Display**: E Ink Spectra 6 (800×480, 7.3", 7-color)
- **Battery**: 2000mAh built-in (3+ months runtime)
- **Sensors**: SHT40 temperature & humidity (I2C)
- **Audio**: Microphone (I2S), Buzzer
- **Connectivity**: WiFi 2.4GHz, Bluetooth 5.0
- **Storage**: PSRAM-only (no SD card required)
- **Enclosure**: Professional metal case with mounting holes

## Pin Mapping

```cpp
// Display (Spectra 6) - SPI
EPD_CLK  = 7
EPD_MOSI = 9
EPD_CS   = 10
EPD_DC   = 11
EPD_RST  = 12
EPD_BUSY = 13

// Temperature & Humidity Sensor (SHT40) - I2C
I2C_SDA = 19
I2C_SCL = 20
SHT40_ADDR = 0x44

// Buttons
BUTTON_GREEN = 3   // Wake/Center button
BUTTON_WHITE = 4   // User button

// Battery Monitoring
BATTERY_ADC = 1
BATTERY_EN  = 21

// Audio
BUZZER      = 45
MIC_POWER   = 38
MIC_BCLK    = 42
MIC_DATA    = 41
```

## Features

### Core Features
- ✅ WiFi captive portal for easy setup
- ✅ Daily automatic image refresh from backend
- ✅ Multi-tier caching (SPIFFS, PSRAM)
- ✅ Deep sleep power management (50μA)
- ✅ Battery monitoring with low-battery alerts
- ✅ Button controls (refresh, factory reset)
- ✅ OTA firmware updates

### Sensor Features
- 🌡️ **Temperature & Humidity**: Display climate data on screen
- 🔊 **Buzzer**: Reminders, alerts, notifications
- 🎤 **Microphone**: Future voice command support (optional)

### Power Management
- **Active**: ~150mA during WiFi + display refresh
- **Deep Sleep**: <100μA (ESP32-S3 optimized)
- **Battery Life**: 3+ months on 2000mAh battery (1 refresh/day)

## Quick Start

### 1. Install PlatformIO
```bash
# Install PlatformIO Core
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py
python3 get-platformio.py

# Or use VS Code extension
# https://platformio.org/install/ide?install=vscode
```

### 2. Build Firmware
```bash
cd firmware/reterminal-e1002
pio run
```

### 3. Upload to Device
```bash
# Connect reTerminal E1002 via USB-C
pio run -t upload
```

### 4. Monitor Serial Output
```bash
pio device monitor
# Press Ctrl+] to exit
```

## First Boot Setup

1. Power on reTerminal E1002
2. Look for WiFi network `KIND-Setup` (password: `kind1234`)
3. Connect and navigate to `http://192.168.4.1`
4. Enter your WiFi credentials and backend URL
5. Device will reboot and fetch first image

## Configuration

Edit `src/config.h` for customization:

```cpp
// Wake time (daily refresh)
#define WAKE_HOUR   1    // 1 AM
#define WAKE_MINUTE 0

// Backend API
#define BACKEND_URL "https://your-backend.app"

// Battery thresholds
#define BATTERY_LOW_THRESHOLD 20  // Show warning
#define BATTERY_CRITICAL_THRESHOLD 10  // Extended sleep
```

## Sensor Integration

### Temperature & Humidity Display

The firmware reads SHT40 sensor and sends data to backend:

```http
GET /v1/raw7?device=xxx&temp=72.5&humidity=45
```

Backend can overlay climate data on generated image.

### Buzzer Notifications

Backend can trigger buzzer via HTTP header:

```http
X-Buzzer-Pattern: 3,100,200  # 3 beeps, 100ms on, 200ms off
```

Firmware plays pattern after displaying image.

## Memory Layout (PSRAM-Only)

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

**No SD card required** - PSRAM and SPIFFS provide ample storage for daily refreshes.

## Troubleshooting

### Display shows nothing
- Check USB-C power is connected
- Verify display connector is fully seated
- Press green button to wake from sleep
- Check serial monitor for errors

### WiFi not connecting
- Long press center button (6s) for factory reset
- Reconnect to `KIND-Setup` network
- Re-enter WiFi credentials

### Battery not charging
- Use 5V/1A USB-C power adapter
- Check battery connector is plugged in
- Monitor charging LED (if present)

### Sensor readings incorrect
- Verify I2C connections (SDA=19, SCL=20)
- Check SHT40 is detected: `Wire.beginTransmission(0x44)`
- Sensor may need calibration after first use

## Advanced Features

### Custom Buzzer Patterns

```cpp
// In button_handler.cpp
void playCustomAlert() {
  // Short beep
  digitalWrite(BUZZER_PIN, HIGH);
  delay(100);
  digitalWrite(BUZZER_PIN, LOW);
}
```

### Temperature Threshold Alerts

```cpp
// In KindDisplay.ino
if (temp > 80.0) {
  playBuzzerPattern(5, 50, 100);  // Urgent beeping
  Serial.println("High temperature alert!");
}
```

### Voice Command Integration (Future)

Microphone support planned for future releases:
- Wake word detection
- Voice command recognition
- Sound level monitoring

## Build Variants

### Debug Build (Verbose Logging)
```bash
pio run -e reterminal-e1002 --verbose
```

### Release Build (Optimized)
```bash
pio run -e reterminal-e1002 --release
```

## OTA Updates

Over-the-air firmware updates supported:

```cpp
// Enable OTA in config.h
#define ENABLE_OTA true
#define OTA_PASSWORD "your-secure-password"
```

Upload via network:
```bash
pio run -t upload --upload-port reterminal-e1002.local
```

## Hardware Resources

- [Official Wiki](https://wiki.seeedstudio.com/getting_started_with_reterminal_e1002/)
- [Schematic](https://files.seeedstudio.com/wiki/reTerminal-E1002/reTerminal-E1002-Schematic.pdf)
- [3D Models](https://www.seeedstudio.com/reTerminal-E1002-p-6533.html)

## Support

For issues specific to this firmware:
- Check serial monitor output at 115200 baud
- Enable debug logging in `config.h`
- Review `ARCHITECTURE_DECISIONS.md` for design rationale

For hardware issues:
- Contact Seeed Studio support
- Check official forums

## License

Same as main project.
