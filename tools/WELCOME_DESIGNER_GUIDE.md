# Welcome Screen Designer - Complete Guide

## Overview

This tool provides a seamless workflow for creating custom welcome screens and setting up your Kin:D display devices. The complete setup process now captures:

- **WiFi credentials** - Connect to your network
- **Device name** - Give your display a friendly name
- **Email address** - For future features (optional)
- **Admin token** - For QR code quick access (optional)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Welcome Screen Designer](#welcome-screen-designer)
3. [Complete Setup Workflow](#complete-setup-workflow)
4. [Advanced Features](#advanced-features)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start

### For Production (With Custom Welcome Screen)

1. Open `tools/welcome-screen-designer.html` in your browser
2. Design your welcome screen with instructions
3. Add your admin token and portal address
4. Generate QR code and add to design
5. Export RAW7 file
6. Copy `welcome.raw7` to SD card
7. Flash firmware and ship!

### For Testing (No Custom Screen Needed)

1. Flash firmware
2. Device shows automatic text-based welcome screen
3. Connect to KIND-Setup WiFi
4. Complete setup in browser
5. Done!

---

## Welcome Screen Designer

### Accessing the Tool

Open `tools/welcome-screen-designer.html` in any modern web browser. No server or installation needed!

### Features

#### 1. **Visual Canvas**
- 800×480 pixel canvas matching your e-ink display
- Live preview of your design
- Click and drag elements to reposition

#### 2. **Design Tools**

**Text Tool** (`📝 Add Text`)
- Add custom text with system fonts
- Adjustable font size
- Support for multiple fonts (Arial, Georgia, Courier, Times New Roman, Verdana)
- Multi-line text support

**Rectangle Tool** (`▭ Add Rectangle`)
- Create filled or outline rectangles
- Perfect for backgrounds and dividers
- Adjustable width and height

**Image Tool** (`🖼️ Add Image`)
- Upload your own images (PNG, JPG, etc.)
- Automatic scaling for large images
- Drag and resize after placing

**QR Code Tool** (`📱 Add QR Code`)
- Automatically generates QR code with admin token
- Creates URL: `http://192.168.4.1/?token=YOUR_TOKEN`
- Scans directly to setup page with pre-filled token
- Perfect for quick device access

#### 3. **7-Color E-Ink Palette**

The designer restricts colors to match your e-ink display:
- ⬜ **White** - Background
- ⬛ **Black** - Text and outlines
- 🟥 **Red** - Alerts and important info
- 🟨 **Yellow** - Highlights
- 🟦 **Blue** - Headers and branding
- 🟩 **Green** - Success states
- 🟧 **Orange** - Accents

Click any color to select it before adding elements.

#### 4. **Properties Panel**

Select any element to edit its properties:
- **Text**: Content, font size, font family
- **Rectangles**: Width, height, fill style
- **Images**: Width, height (maintains aspect ratio option coming soon)

#### 5. **Export Options**

**RAW7 Export** (`💾 Export RAW7 File`)
- Converts design to RAW7 format (192,000 bytes)
- Ready to copy to SD card
- Automatic color quantization to 7-color palette

**PNG Preview** (`📷 Export PNG Preview`)
- Export design as PNG for reference
- Useful for documentation
- Shows exactly how design will look

### Design Best Practices

#### Layout Recommendations

```
┌─────────────────────────────────────────────┐ (800×480px)
│  HEADER (Blue bar, 0-100px)                 │
│  - Brand name: Kin:D                        │
│  - Tagline: make a smile                    │
├─────────────────────────────────────────────┤
│                                             │
│  MAIN CONTENT (100-400px)                   │
│  - Setup instructions                       │
│  - QR code (optional)                       │
│  - WiFi credentials hint                    │
│                                             │
├─────────────────────────────────────────────┤
│  FOOTER (400-480px)                         │
│  - Additional info or branding              │
└─────────────────────────────────────────────┘
```

#### Text Sizing Guide

- **Headers**: 32-48px
- **Body text**: 20-28px
- **Small text**: 14-18px

#### Color Usage

- Use **blue** for headers and branding (matches web portal)
- Use **black** on **white** for best readability
- Use **red** sparingly for important warnings
- Use **orange/yellow** for highlights and call-to-actions

### Example Welcome Screen

Here's a recommended layout:

1. **Blue header bar** (full width, 100px high)
   - White text: "Kin:D" at 48px
   - White text: "make a smile" at 20px

2. **WiFi Instructions** (centered)
   - Text: "1. Connect to WiFi: KIND-Setup"
   - Text: "2. Password: kind1234"
   - Text: "3. Scan QR code or visit any website"

3. **QR Code** (center, 200×200px)
   - Generated with your admin token

4. **Footer text**
   - Text: "Your display will refresh daily with delightful content!"

---

## Complete Setup Workflow

### Phase 1: Design Welcome Screen (Pre-Production)

**Step 1: Open Designer**
```bash
# Open in browser
open tools/welcome-screen-designer.html
```

**Step 2: Create Your Design**
1. Add blue header rectangle (0, 0, 800, 100)
2. Add white "Kin:D" text (300, 60, 48px)
3. Add instruction text
4. Enter admin token in export panel
5. Click "Add QR Code" to generate QR
6. Position and arrange elements

**Step 3: Export**
1. Click "Export RAW7 File"
2. Save as `welcome.raw7`
3. Optionally export PNG for documentation

### Phase 2: Prepare Device (Manufacturing)

**Step 1: Prepare SD Card**
```bash
# Copy welcome screen to SD card root
cp welcome.raw7 /Volumes/SD_CARD/welcome.raw7

# Verify file size
ls -l /Volumes/SD_CARD/welcome.raw7
# Should show: 192000 bytes
```

**Step 2: Insert SD Card**
- Insert prepared SD card into device
- SD card slot on board

**Step 3: Flash Firmware**
```bash
cd firmware/KindDisplay
# Upload via Arduino IDE or platformio
```

**Step 4: First Boot**
- Device powers on
- Welcome screen loads from SD card
- E-ink displays your custom design
- WiFi portal starts automatically

**Result**: Device is ready to ship with welcome screen already visible!

### Phase 3: Customer Setup (End User)

**Step 1: Unbox**
- Customer sees custom welcome screen on e-ink display
- Instructions are immediately visible (no manual needed!)

**Step 2: Connect to WiFi**
- Customer connects phone/computer to "KIND-Setup" WiFi
- Password: `kind1234`

**Step 3: Open Setup Page**

**Option A: Scan QR Code** (if included on welcome screen)
- Scan QR code with phone camera
- Opens directly to setup page with admin token pre-filled

**Option B: Type Any Website**
- Open browser
- Type any URL (e.g., `google.com`, `makeasmile.com`)
- Captive portal redirects to setup page automatically

**Step 4: Complete Setup Form**

The setup page now collects:

```
┌─────────────────────────────────────────────┐
│  Display Name (optional)                    │
│  [Living Room Display    ]                  │
├─────────────────────────────────────────────┤
│  WiFi Network (required)                    │
│  [▼ Select Network       ]                  │
├─────────────────────────────────────────────┤
│  WiFi Password (if required)                │
│  [**************         ]                  │
├─────────────────────────────────────────────┤
│  Email Address (optional)                   │
│  [user@email.com         ]                  │
├─────────────────────────────────────────────┤
│  Admin Token (optional)                     │
│  [abc123def456           ]                  │
├─────────────────────────────────────────────┤
│         [Connect & Continue]                │
└─────────────────────────────────────────────┘
```

**Field Details:**

- **Display Name**: Friendly name (e.g., "Kitchen Display")
- **WiFi Network**: Auto-populated dropdown from scan
- **WiFi Password**: Password for selected network
- **Email**: For future features (notifications, account linking)
- **Admin Token**: For QR code quick access (can be pre-filled from QR scan)

**Step 5: Save and Connect**
- Click "Connect & Continue"
- Device connects to WiFi
- Fetches first frame from backend
- Display updates (30-60 seconds)
- Setup complete!

### Stored Data

All setup information is saved to NVS (Non-Volatile Storage):

```cpp
// In NVS "kindconfig" namespace:
{
  "wifi_ssid": "HomeNetwork",
  "wifi_pass": "password123",
  "backend_url": "https://your-backend.com",
  "device_name": "Living Room",
  "email": "user@email.com",           // NEW
  "admin_token": "abc123def456"        // NEW
}
```

---

## Advanced Features

### Admin Token Usage

The admin token enables several workflows:

#### 1. QR Code Quick Access
- Print/display QR code with embedded token
- Scan QR → immediately access device setup
- No need to remember IP address or token

#### 2. Backend Authentication (Future)
- Use token to authenticate API requests
- Secure device-specific operations
- Link device to user account

#### 3. Device Management (Future)
- Remote configuration changes
- OTA firmware updates
- Display content customization

### Accessing Stored Values in Firmware

```cpp
// In your firmware code:
WiFiManager wifiMgr;

// Get values
String deviceName = wifiMgr.getDeviceName();
String email = wifiMgr.getEmail();
String adminToken = wifiMgr.getAdminToken();
String backendUrl = wifiMgr.getBackendUrl();

// Use in API calls
String url = backendUrl + "/v1/raw7?device=" + deviceName + "&token=" + adminToken;
```

### Custom Backend Integration

Update backend to accept token:

```javascript
// Backend endpoint
app.get('/v1/raw7', (req, res) => {
  const device = req.query.device;
  const token = req.query.token;
  const email = req.query.email;

  // Authenticate with token
  if (token) {
    // Verify token, link to user account
  }

  // Return personalized RAW7 image
  // ...
});
```

---

## Troubleshooting

### Welcome Screen Issues

**Problem**: Welcome screen not displaying

**Solutions**:
1. Check SD card is inserted
2. Verify file is named exactly `welcome.raw7`
3. Check file size is exactly 192,000 bytes
4. SD card should be formatted as FAT32
5. Verify SD pins in config.h match hardware

**Problem**: Colors look wrong on e-ink

**Solution**: E-ink color reproduction is limited. Some colors may appear different than on screen. Use the PNG export to preview, but expect slight variations on actual hardware.

### Setup Portal Issues

**Problem**: Can't connect to KIND-Setup WiFi

**Solutions**:
1. Check WiFi is enabled on your device
2. Move closer to display
3. Restart display (power cycle)
4. Check for LED slow blink (indicates portal running)

**Problem**: Browser doesn't redirect to setup page

**Solutions**:
1. Try typing `192.168.4.1` directly
2. Disable mobile data (use WiFi only)
3. Try a different browser
4. Clear browser cache

**Problem**: Setup form won't submit

**Solutions**:
1. Ensure WiFi network is selected (required field)
2. Check serial debug output for errors
3. Try shorter device name (max 32 characters)
4. Try shorter email (max 64 characters)

### Data Storage Issues

**Problem**: Settings not saving

**Solutions**:
1. Check NVS partition is not corrupted
2. Try factory reset (hold boot button 6+ seconds)
3. Reflash firmware
4. Check serial output for NVS errors

**Problem**: Can't retrieve email or token

**Solutions**:
```cpp
// Debug in firmware:
String email = wifiMgr.getEmail();
DEBUG_PRINTF("Stored email: %s\n", email.c_str());

String token = wifiMgr.getAdminToken();
DEBUG_PRINTF("Stored token: %s\n", token.c_str());
```

---

## File Locations

```
family-display-backend3/
├── tools/
│   ├── welcome-screen-designer.html    # Main designer tool
│   └── WELCOME_DESIGNER_GUIDE.md       # This file
├── firmware/
│   ├── KindDisplay/
│   │   ├── config.h                    # Pin configuration
│   │   ├── wifi_manager.h/.cpp         # WiFi & setup portal
│   │   ├── text_welcome.h/.cpp         # Text-based fallback
│   │   └── sd_manager.h/.cpp           # SD card operations
│   ├── WELCOME_SCREEN.md               # Welcome screen tech docs
│   └── README.md                       # Firmware documentation
```

---

## API Reference

### WiFiManager Methods

```cpp
// Get stored configuration
String getDeviceName();     // Returns device name or "familydisplay"
String getEmail();          // Returns email or empty string
String getAdminToken();     // Returns token or empty string
String getBackendUrl();     // Returns backend URL

// Set configuration
void setBackendUrl(const String& url);
bool saveCredentials(const String& ssid, const String& password, const String& backendUrl);
void clearCredentials();    // Factory reset

// WiFi operations
bool hasCredentials();      // Check if WiFi configured
bool connect(LEDStatus* led = nullptr);
void startConfigPortal(LEDStatus* led = nullptr);
```

---

## Production Checklist

### Pre-Production
- [ ] Design welcome screen in designer tool
- [ ] Generate QR code with admin token
- [ ] Test design on actual hardware
- [ ] Export RAW7 file
- [ ] Export PNG for documentation
- [ ] Prepare SD cards with welcome.raw7

### Manufacturing
- [ ] Flash latest firmware
- [ ] Insert SD card with welcome screen
- [ ] Power on and verify welcome screen displays
- [ ] Verify WiFi portal starts
- [ ] Test setup process end-to-end
- [ ] Document admin token for this batch
- [ ] Package with quick start guide

### Quality Assurance
- [ ] Welcome screen displays correctly
- [ ] WiFi portal accessible
- [ ] All form fields save properly
- [ ] Email and token stored in NVS
- [ ] Device connects to WiFi after setup
- [ ] First frame loads successfully
- [ ] Display refreshes as expected

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review firmware serial output
3. Check GitHub issues
4. Consult hardware_pins.md for pin configuration

---

## Future Enhancements

Planned features:
- [ ] Font upload support (custom fonts)
- [ ] Element alignment guides
- [ ] Snap to grid
- [ ] Undo/redo
- [ ] Templates library
- [ ] Direct firmware integration (skip SD card step)
- [ ] Backend token validation
- [ ] Multi-device management dashboard
- [ ] Email-based notifications
- [ ] Device linking and grouping

---

## License

Part of the Kin:D Family Display project.
