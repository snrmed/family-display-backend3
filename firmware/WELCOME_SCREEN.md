# Welcome Screen Setup Guide

## Overview

The firmware now supports displaying a custom welcome screen from the SD card during first boot / WiFi setup mode. This is perfect for shipping devices with pre-loaded setup instructions on the e-ink display.

## How It Works

When the device boots without WiFi credentials, it will:
1. Check if SD card is available
2. Look for `/welcome.raw7` on the SD card
3. Display the image if found (the e-ink will retain it even when powered off!)
4. Start the WiFi configuration portal

The welcome screen persists on the e-ink display because of its memory retention properties - perfect for shipping!

## Creating a Welcome Screen

### Image Requirements

- **Resolution**: 800×480 pixels
- **Color Palette**: 7 colors only
  - White (RGB: 255,255,255)
  - Black (RGB: 0,0,0)
  - Red (RGB: 220,0,0)
  - Yellow (RGB: 255,216,0)
  - Blue (RGB: 0,0,200)
  - Green (RGB: 0,160,0)
  - Orange (RGB: 255,128,0)
- **Format**: RAW7 (192,000 bytes - 2 pixels per nibble)

### Suggested Content

Include clear setup instructions, for example:

```
┌──────────────────────────────────────────────┐
│           Welcome to Kin:D Display           │
│              make a smile 😊                 │
│                                              │
│  Setup Instructions:                         │
│                                              │
│  1. Connect to WiFi Network:                 │
│     SSID: KIND-Setup                         │
│     Password: kind1234                       │
│                                              │
│  2. Open any website in your browser         │
│     (e.g., makeasmile.com, google.com)       │
│                                              │
│  3. You'll be redirected to the setup page   │
│                                              │
│  4. Enter your WiFi credentials and          │
│     give your display a name                 │
│                                              │
│  5. Your display will fetch its first        │
│     frame and refresh daily!                 │
│                                              │
└──────────────────────────────────────────────┘
```

### Creating the RAW7 File

#### Option 1: Use the Backend Image Processor

If you have the backend running, you can use its image processing pipeline:

```bash
# Convert PNG to RAW7
curl -X POST "http://your-backend/convert-image" \
  -F "image=@welcome.png" \
  -o welcome.raw7
```

#### Option 2: Python Script (Create Your Own)

Create a simple converter that:
1. Loads an 800×480 image
2. Quantizes to the 7-color palette
3. Packs pixels into nibbles (2 per byte)
4. Saves as 192,000-byte binary file

Example structure:
```python
# Pseudo-code
for each pixel pair:
    byte = (pixel1_index << 4) | pixel2_index
    write byte to file
```

## Installing the Welcome Screen

### Method 1: Pre-load Before Shipping

1. Create your `welcome.raw7` file
2. Insert SD card into computer
3. Copy `welcome.raw7` to the root of the SD card
4. Insert SD card into the device
5. Flash firmware
6. The welcome screen will display on first boot!

### Method 2: Update After Manufacturing

1. Boot device and complete WiFi setup
2. Access SD card via serial/USB or remove and use card reader
3. Copy `welcome.raw7` to the root
4. Factory reset the device (it will show the welcome screen on next setup)

## SD Card File Structure

```
/
├── welcome.raw7    (192,000 bytes - your custom welcome screen)
└── last.raw7       (192,000 bytes - cached last frame, auto-generated)
```

## Hardware Setup

### Pin Configuration (Updated)

The SD card now works with the corrected pin configuration:

**Display:**
- CS: GPIO5
- DC: GPIO23
- MOSI: GPIO19
- SCK: GPIO18
- BUSY: GPIO4
- RST: GPIO16

**SD Card:**
- CS: GPIO13 (separate from display!)
- MOSI: GPIO19 (shared with display)
- MISO: GPIO27
- SCK: GPIO18 (shared with display)

The CS pins are now separate, so both devices work together on the shared SPI bus.

## Troubleshooting

### SD Card Not Initializing

Check serial output for:
```
SD: Initializing SD card
SD: Card initialized successfully
```

If you see "Card mount failed", check:
1. SD card is properly inserted
2. SD card is formatted as FAT32
3. Pin connections match the configuration above

### Welcome Screen Not Displaying

Check serial output for:
```
Loading welcome screen from SD card...
Displaying welcome screen
```

If you see "No welcome screen found":
1. Ensure file is named exactly `welcome.raw7`
2. Ensure file is in root directory (not in a folder)
3. Ensure file is exactly 192,000 bytes

### File Size Verification

```bash
# On Linux/Mac
ls -l welcome.raw7
# Should show: 192000 bytes

# On Windows (PowerShell)
(Get-Item welcome.raw7).length
# Should show: 192000
```

## Configuration

### Enable/Disable SD Card

In `config.h`:
```cpp
#define SD_CARD_ENABLED  true  // Set to false to disable SD card completely
```

### Custom Welcome File Path

In `config.h`:
```cpp
#define SD_WELCOME_FILE  "/welcome.raw7"  // Change path if needed
```

## Benefits for Shipping

1. **Professional unboxing**: Customers see branded setup instructions immediately
2. **No manual needed**: All instructions on the display itself
3. **E-ink retention**: Image stays on screen even when device is off - no power needed!
4. **Easy updates**: Just update the SD card file before shipping batches
5. **Works offline**: No WiFi needed to show welcome screen

## Next Steps

1. Design your welcome screen image (800×480, 7 colors)
2. Convert to RAW7 format
3. Copy to SD card
4. Test on device
5. Mass-produce and ship! 🚀
