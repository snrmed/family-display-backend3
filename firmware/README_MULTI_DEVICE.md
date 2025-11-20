# Multi-Device Firmware Structure

This firmware now supports **3 different devices**, each in its own folder with device-specific configurations.

## Supported Devices

### 1. 🏆 Seeed reTerminal E1002 (Recommended)
**Folder**: `firmware/reterminal-e1002/`

- **MCU**: ESP32-S3R8 (8MB PSRAM, 32MB Flash)
- **Display**: E Ink Spectra 6 (800×480, 7.3")  - **Included**
- **Battery**: 2000mAh built-in
- **Sensors**: Temperature/humidity (SHT40), microphone, buzzer
- **Enclosure**: Professional metal case
- **Best for**: Production deployments, sensor integration, all-in-one solution

[View reTerminal E1002 README →](reterminal-e1002/README.md)

### 2. 📦 Seeed XIAO ePaper Display Board EE04 (Compact)
**Folder**: `firmware/xiao-ee04/`

- **MCU**: ESP32-S3 Plus (8MB PSRAM, 32MB Flash)
- **Display**: Supports 7.3" Spectra 6 (800×480)  - **Separate purchase**
- **Battery**: User-provided via JST connector
- **Features**: Font chip (GT32L32S0140), 3 user buttons
- **Form factor**: Ultra-compact XIAO size
- **Best for**: DIY projects, custom enclosures, space-constrained builds

[View XIAO EE04 README →](xiao-ee04/README.md)

### 3. 🔧 Waveshare e-Paper ESP32 Driver Board REV3 (Universal)
**Folder**: `firmware/waveshare-esp32-rev3/`

- **MCU**: ESP32 Classic (no PSRAM typically)
- **Display**: Universal - works with various Waveshare panels
- **Battery**: User-provided
- **Features**: 24-pin FFC connector for flexibility
- **Best for**: Existing Waveshare display owners, DIY builds, display experimentation

[View Waveshare ESP32 REV3 README →](waveshare-esp32-rev3/README.md)

## Quick Start by Device

### reTerminal E1002
```bash
cd firmware/reterminal-e1002
pio run -t upload
pio device monitor
```

### XIAO EE04
```bash
cd firmware/xiao-ee04
pio run -t upload
pio device monitor
```

### Waveshare ESP32 REV3
```bash
cd firmware/waveshare-esp32-rev3
pio run -t upload
pio device monitor
```

## Folder Structure

```
firmware/
├── reterminal-e1002/          # reTerminal E1002 firmware
│   ├── platformio.ini
│   ├── src/                   # Symlinks to shared/
│   └── README.md
│
├── xiao-ee04/                 # XIAO EE04 firmware
│   ├── platformio.ini
│   ├── src/                   # Symlinks to shared/
│   └── README.md
│
├── waveshare-esp32-rev3/      # Waveshare ESP32 REV3 firmware
│   ├── platformio.ini
│   ├── src/                   # Symlinks to shared/
│   └── README.md
│
├── shared/                    # Shared code for all devices
│   ├── KindDisplay.ino        # Main firmware
│   ├── display_driver.cpp/h   # Spectra-6 display driver
│   ├── wifi_manager.cpp/h     # WiFi setup
│   ├── raw7_decoder.cpp/h     # Image decoder
│   ├── hardware_config.h      # Multi-device pin mappings
│   └── ...                    # Other modules
│
├── ARCHITECTURE_DECISIONS.md  # Design rationale
├── SEEED_DEVICES.md           # Original migration guide
└── README_MULTI_DEVICE.md     # This file
```

## Common Code (Shared)

All devices share the same core firmware code located in `firmware/shared/`:

### Core Modules
- **display_driver** - Spectra-6 e-paper display controller
- **wifi_manager** - Captive portal WiFi configuration
- **raw7_decoder** - Streaming RAW7 image decoder
- **flash_cache** - SPIFFS-based persistent cache
- **rtc_manager** - Deep sleep and wake scheduling
- **battery** - Battery monitoring and management
- **button_handler** - Button/switch input handling
- **led_status** - Status LED patterns

### Device Selection
Each device folder has its own `platformio.ini` that defines:
```ini
build_flags =
    -D DEVICE_RETERMINAL_E1002  # Or DEVICE_XIAO_EE04, DEVICE_WAVESHARE_ESP32_REV3
```

This automatically selects the correct pin mappings from `hardware_config.h`.

## Feature Comparison

| Feature | reTerminal E1002 | XIAO EE04 | Waveshare REV3 |
|---------|------------------|-----------|----------------|
| **MCU** | ESP32-S3 (8MB PSRAM) | ESP32-S3 Plus (8MB PSRAM) | ESP32 Classic |
| **Display Included** | ✅ Yes | ❌ Separate | ❌ Separate |
| **Battery Included** | ✅ 2000mAh | ❌ User-provided | ❌ User-provided |
| **Temp/Humidity** | ✅ SHT40 | ❌ | ❌ |
| **Microphone** | ✅ I2S | ❌ | ❌ |
| **Buzzer** | ✅ GPIO45 | ❌ | ❌ |
| **Font Chip** | ❌ | ✅ GT32L32S0140 | ❌ |
| **Enclosure** | ✅ Metal case | ❌ DIY | ❌ DIY |
| **Form Factor** | All-in-one 7.3" | Compact board | Driver board |
| **PSRAM/No SD** | ✅ 8MB | ✅ 8MB | ⚠️ Limited RAM |
| **Price Range** | $$$ | $$ | $ |

## Key Architectural Decisions

### 1. Separate Folders per Device
Each device has its own standalone project for:
- Clear separation of concerns
- Independent evolution
- Easier contribution
- Simpler builds (no complex #ifdef chains)

### 2. PSRAM-Only (No SD Card) for ESP32-S3 Devices
**reTerminal E1002** and **XIAO EE04** both have 8MB PSRAM:
- Stores active image + working buffers
- Faster than SD card access
- More reliable (no SD corruption)
- Simpler hardware (one less component)
- SPIFFS still provides persistent cache

**Waveshare REV3** (ESP32 classic):
- No PSRAM, uses SPIFFS only
- Can add SD card if needed
- Smaller stack size for HTTPS

### 3. Keep RAW7 Format
All devices use RAW7 (not PNG) for:
- Smaller file size (192KB vs 300-500KB)
- Less WiFi power consumption
- Backend does color quantization (better quality)
- Device just unpacks (faster, less CPU)
- Predictable memory usage

### 4. Sensor Integration (reTerminal E1002 only)
- **Temperature/Humidity**: Sent to backend, displayed on image
- **Buzzer**: Notifications, reminders, alerts
- **Microphone**: Future voice commands (optional)

See [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) for full rationale.

## Pin Mappings Summary

### reTerminal E1002 (ESP32-S3)
```
EPD: CLK=7, MOSI=9, CS=10, DC=11, RST=12, BUSY=13
I2C: SDA=19, SCL=20 (SHT40 temp/humidity)
Buttons: Green=3, White=4
Battery: ADC=1, Enable=21
Buzzer: 45
```

### XIAO EE04 (ESP32-S3 Plus)
```
EPD: CLK=7, MOSI=9, CS=44, DC=10, RST=38, BUSY=4
Buttons: KEY0=2, KEY1=3, KEY2=5
Battery: ADC=1, Enable=6
```

### Waveshare ESP32 REV3 (ESP32 Classic)
```
EPD: CLK=13, MOSI=14, CS=15, DC=27, RST=26, BUSY=25
(Note: CS=15 differs from original dev board CS=33)
```

## Sensor Features (reTerminal E1002 Only)

### Temperature & Humidity
Firmware reads SHT40 sensor and sends to backend:
```http
GET /v1/raw7?device=xxx&temp=72.5&humidity=45
```

Backend can overlay climate data on family photo display.

### Buzzer Notifications
Backend can trigger buzzer via HTTP response header:
```http
X-Buzzer-Pattern: 3,100,200  # 3 beeps, 100ms on, 200ms off
```

Perfect for:
- Medication reminders
- Appointment alerts
- Weather warnings
- Smart home notifications

## Getting Started

### 1. Choose Your Device
Select based on your needs:
- **All-in-one simplicity**: reTerminal E1002
- **Compact/custom**: XIAO EE04
- **Existing Waveshare display**: Waveshare ESP32 REV3

### 2. Install PlatformIO
```bash
# Install PlatformIO Core
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py
python3 get-platformio.py

# Or use VS Code extension
# https://platformio.org/install/ide?install=vscode
```

### 3. Build & Upload
```bash
cd firmware/{device-folder}
pio run -t upload
pio device monitor
```

### 4. Configure WiFi
1. Connect to `KIND-Setup` network (password: `kind1234`)
2. Navigate to `http://192.168.4.1`
3. Enter WiFi credentials and backend URL
4. Device reboots and fetches first image

## Troubleshooting

### Build Errors
Check that you're in the correct device folder:
```bash
pwd  # Should show firmware/reterminal-e1002 (or xiao-ee04, waveshare-esp32-rev3)
```

### Display Issues
Verify correct device selected in platformio.ini:
```ini
build_flags =
    -D DEVICE_RETERMINAL_E1002  # Must match your hardware!
```

### Memory Issues (Waveshare ESP32 REV3 only)
ESP32 classic has no PSRAM - may need to:
- Reduce HTTP buffer size in config.h
- Disable debug logging
- Use SD card for caching (optional)

## Migration from Old Structure

If you were using the old unified `firmware/KindDisplay/` folder:

1. **Identify your device** (reTerminal, XIAO, or Waveshare)
2. **Navigate to new folder**: `cd firmware/{device-folder}/`
3. **Build as normal**: `pio run -t upload`
4. **Old folder still works** for original ESP32 dev board

## Contributing

When contributing device-specific fixes:
- Make changes in the specific device folder if it's device-specific
- Make changes in `firmware/shared/` if it affects all devices
- Test on multiple devices when modifying shared code

## Resources

- [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) - Design decisions and rationale
- [SEEED_DEVICES.md](SEEED_DEVICES.md) - Original Seeed devices migration guide
- [reTerminal E1002 README](reterminal-e1002/README.md) - Device-specific documentation
- [XIAO EE04 README](xiao-ee04/README.md) - Device-specific documentation
- [Waveshare ESP32 REV3 README](waveshare-esp32-rev3/README.md) - Device-specific documentation

## Hardware Purchase Links

- [reTerminal E1002](https://www.seeedstudio.com/reTerminal-E1002-p-6533.html) - Seeed Studio
- [XIAO EE04](https://www.seeedstudio.com/XIAO-ePaper-Board-ESP32-S3-EE04-with-7-3-spectratm-6-ePaper-Display-Bundle-Kit.html) - Seeed Studio
- [Waveshare ESP32 Driver Board](https://www.waveshare.com/e-paper-esp32-driver-board.htm) - Waveshare

## License

Same as main project.
