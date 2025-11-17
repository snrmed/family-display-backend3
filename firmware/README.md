# KIND Display - ESP32 Firmware

Complete firmware for the Kin:D / Family Display 7-color e-ink device.

## 📋 Hardware Specifications

### Display
- **Panel**: Spectra-6 (E6) 7-Color E-Ink Display
- **Resolution**: 800×480 pixels
- **Ribbon Code**: P730010-MF1-A
- **Colors**: 7 (White, Black, Red, Yellow, Blue, Green, Orange)

### Microcontroller
- **Board**: ESP32 E-Ink Development Board (节电版)
- **Module**: ESP-32S
- **Features**: WiFi, Bluetooth, SD Card, RTC with CR2032, LiPo charger, USB-C

## 🔌 Hardware Connections

### EPD Adapter to ESP32 Pin Mapping

| EPD Adapter Pin | ESP32 GPIO | Function |
|----------------|------------|----------|
| BUSY           | GPIO 4     | Busy signal |
| RST            | GPIO 16    | Reset |
| CS             | GPIO 5     | Chip Select |
| DC             | GPIO 17    | Data/Command |
| SCK            | GPIO 18    | SPI Clock |
| DIN (MOSI)     | GPIO 23    | SPI Data |
| 5V             | 5V         | Power |
| GND            | GND        | Ground |

### Optional: External Button

| Button Pin | ESP32 GPIO |
|------------|------------|
| Button     | GPIO 0 (or configure in `config.h`) |
| GND        | GND |

> **Note**: By default, the firmware uses GPIO 0 (BOOT button). You can add an external button for easier access.

### SD Card (Optional)

Default VSPI pins for SD card:
- **CS**: GPIO 13
- **MOSI**: GPIO 15
- **MISO**: GPIO 2
- **SCK**: GPIO 14

> These can be adjusted in `config.h` if your board uses different pins.

## 🚀 Getting Started

### Prerequisites

1. **PlatformIO** - Install via:
   - [VS Code Extension](https://platformio.org/install/ide?install=vscode)
   - Or standalone: `pip install platformio`

2. **USB Cable** - USB-C cable for programming

3. **Backend Server** - Your KIND backend must be running and accessible on your network

### Installation Steps

#### 1. Clone and Configure

```bash
cd firmware/KindDisplay
```

#### 2. Configure Backend URL

Edit `config.h` and set your backend URL:

```cpp
#define BACKEND_URL   "http://192.168.1.100:8080"  // Change to your backend IP/domain
```

#### 3. Build and Upload

**Using PlatformIO CLI:**
```bash
cd firmware
pio run -t upload
```

**Using VS Code:**
1. Open the `firmware` folder in VS Code
2. Click the PlatformIO icon in the sidebar
3. Under "PROJECT TASKS", click "Upload"

#### 4. Monitor Serial Output

```bash
pio device monitor
```

Or in VS Code: Click "Monitor" in PlatformIO tasks.

## 📱 First-Time Setup

### WiFi Configuration

On first boot (or after factory reset):

1. **Device starts in AP mode**
   - SSID: `KIND-Setup`
   - Password: `kind1234`

2. **Connect to the AP**
   - Use your phone or computer to connect to `KIND-Setup`

3. **Open Setup Page**
   - Navigate to: `http://192.168.4.1`
   - Or wait for captive portal to appear

4. **Configure WiFi**
   - Select your WiFi network
   - Enter password
   - Enter backend URL (if different from default)
   - Click "Save & Connect"

5. **Device Reboots**
   - Device will connect to your WiFi
   - Fetch first image from backend
   - Display it on the e-ink screen

## 🎮 Usage

### Normal Operation

The device operates in deep sleep most of the time and wakes:

1. **Daily at 01:00** (configurable in `config.h`)
   - Connects to WiFi
   - Fetches latest image from backend
   - Updates display
   - Returns to deep sleep

2. **When button is pressed**
   - See button controls below

### Button Controls

#### Short Press (< 6 seconds)
- **Function**: Trigger background reroll
- **What happens**:
  1. Wake from sleep
  2. Connect to WiFi
  3. Call `/v1/frame_bg_reroll` endpoint
  4. Fetch new RAW7 image
  5. Update display
  6. Return to sleep

#### Long Press (> 6 seconds)
- **Function**: Factory reset
- **What happens**:
  1. Clear WiFi credentials
  2. Clear backend URL
  3. Reboot into setup mode (AP mode)

### LED Indicators

- **Serial output**: Connect via USB to see detailed debug logs at 115200 baud

## ⚙️ Configuration

### Modify Settings

Edit `firmware/KindDisplay/config.h` to customize:

#### Wake Schedule
```cpp
#define WAKE_HOUR     1   // Hour (0-23)
#define WAKE_MINUTE   0   // Minute (0-59)
```

#### Backend URL
```cpp
#define BACKEND_URL   "http://your-backend-url:port"
```

#### Button Pin
```cpp
#define PIN_BUTTON    0   // GPIO number
```

#### Long Press Duration
```cpp
#define BUTTON_LONG_PRESS_MS  6000  // Milliseconds
```

#### Debug Output
```cpp
#define DEBUG_SERIAL  true   // Set to false to disable debug output
```

## 🔧 Troubleshooting

### Display Not Working

1. **Check wiring**: Verify all EPD connections match the pin mapping
2. **Check power**: Ensure 5V and GND are connected
3. **Serial logs**: Connect to serial monitor to see error messages

### WiFi Connection Fails

1. **Signal strength**: Ensure good WiFi signal
2. **Credentials**: Verify SSID and password in setup portal
3. **Factory reset**: Hold button for 6+ seconds to reset WiFi

### Image Not Updating

1. **Backend URL**: Verify backend is accessible from ESP32's network
2. **Test endpoint**: Try accessing `http://YOUR_BACKEND/v1/raw7?device=familydisplay` in browser
3. **Serial logs**: Check for HTTP errors in serial output

### SD Card Not Detected

1. **Wiring**: Verify SD card SPI pins match `config.h`
2. **Card format**: Format SD card as FAT32
3. **Optional feature**: SD card is optional; device works without it

### Display Shows Red Screen

- **Meaning**: Error occurred
- **Check**: Connect to serial monitor to see error message
- **Common causes**:
  - WiFi connection failed
  - Backend unreachable
  - Image fetch failed

## 📊 Power Consumption

- **Deep Sleep**: ~10-50 μA
- **WiFi Active**: ~80-150 mA
- **Display Update**: ~100-200 mA
- **Typical Battery Life**: Several weeks on 2000mAh LiPo (with daily updates)

## 🔄 Firmware Updates

### Over USB

1. Connect ESP32 via USB
2. Rebuild and upload:
   ```bash
   pio run -t upload
   ```

### OTA (Optional - Not Implemented)

OTA updates can be added in future firmware versions.

## 📁 Project Structure

```
firmware/
├── platformio.ini              # PlatformIO configuration
├── README.md                   # This file
└── KindDisplay/
    ├── KindDisplay.ino         # Main firmware
    ├── config.h                # Configuration settings
    ├── display_driver.h/cpp    # Spectra-6 E-ink driver
    ├── wifi_manager.h/cpp      # WiFi setup portal
    ├── raw7_decoder.h/cpp      # Image fetcher
    ├── button_handler.h/cpp    # Button controls
    ├── rtc_manager.h/cpp       # Sleep & wake scheduling
    └── sd_manager.h/cpp        # SD card caching
```

## 🎨 How It Works

### Image Pipeline

1. **Backend** generates display content
2. **Backend** applies Floyd-Steinberg dithering for 7 colors
3. **Backend** encodes to RAW7 format (2 pixels per byte)
4. **ESP32** fetches RAW7 via HTTP GET `/v1/raw7?device=familydisplay`
5. **ESP32** unpacks nibbles to pixel indices (0-6)
6. **ESP32** sends to Spectra-6 display via SPI
7. **Display** refreshes (takes ~30-60 seconds for 7-color)

### RAW7 Format

- **Size**: 192,000 bytes (800×480 ÷ 2)
- **Encoding**: High nibble = first pixel, low nibble = second pixel
- **Values**: 0-6 (maps to 7 colors)

Example:
```
Byte: 0x12
  High nibble: 0x1 → Black
  Low nibble:  0x2 → Red
```

### Color Palette

| Index | Color  | RGB         |
|-------|--------|-------------|
| 0     | White  | 255,255,255 |
| 1     | Black  | 0,0,0       |
| 2     | Red    | 220,0,0     |
| 3     | Yellow | 255,216,0   |
| 4     | Blue   | 0,0,200     |
| 5     | Green  | 0,160,0     |
| 6     | Orange | 255,128,0   |

## 🐛 Debug Tips

### Enable Verbose Logging

In `config.h`:
```cpp
#define DEBUG_SERIAL  true
```

### Monitor Serial Output

```bash
pio device monitor
```

### Common Serial Messages

- `WiFi: Connected! IP: ...` - WiFi connected successfully
- `RAW7: Downloaded ... bytes` - Image download progress
- `SpectraDisplay: Refreshing...` - Display update in progress
- `RTC: Sleep duration: ... seconds` - Time until next wake

## 📝 License

See main project LICENSE file.

## 🙏 Support

For issues or questions:
1. Check this README
2. Review serial debug output
3. Check backend logs
4. Open an issue in the main project repository

---

**Enjoy your KIND Display! 🎨✨**
