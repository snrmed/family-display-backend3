# Kin:D Display Tools

This directory contains development and production tools for the Kin:D family display project.

## Available Tools

### 🎨 Welcome Screen Designer (`welcome-screen-designer.html`)

A browser-based visual editor for creating custom welcome screens for your e-ink displays.

**Features:**
- Drag-and-drop visual editor
- 7-color e-ink palette
- Text, shapes, and image support
- QR code generation with admin tokens
- RAW7 export for direct SD card use
- PNG preview export

**Quick Start:**
```bash
# Open in browser (no server needed!)
open welcome-screen-designer.html
```

**Documentation:** See [WELCOME_DESIGNER_GUIDE.md](WELCOME_DESIGNER_GUIDE.md) for complete guide.

---

## Usage Workflows

### 1. Production Workflow (Custom Welcome Screen)

```bash
# Step 1: Design welcome screen
open welcome-screen-designer.html

# Step 2: Export RAW7 file
# (Use export button in tool)

# Step 3: Copy to SD card
cp welcome.raw7 /path/to/sd/card/

# Step 4: Insert SD card and flash firmware
cd ../firmware/KindDisplay
# Flash via Arduino IDE or PlatformIO
```

### 2. Development Workflow (Quick Testing)

```bash
# Just flash firmware - no SD card needed!
cd ../firmware/KindDisplay
# Flash via Arduino IDE or PlatformIO

# Device will show automatic text-based welcome screen
```

---

## Tool Requirements

### Welcome Screen Designer

**Browser Requirements:**
- Modern browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- No internet connection required (works offline)

**System Requirements:**
- Any OS (Windows, macOS, Linux)
- No installation needed
- Runs entirely in browser

**Dependencies (Loaded from CDN):**
- QRCode.js (for QR code generation)

---

## Output Files

### RAW7 Format

**Specification:**
- File size: Exactly 192,000 bytes
- Encoding: 2 pixels per byte (nibble-packed)
- Resolution: 800×480 pixels
- Color depth: 3-bit (8 colors, only 7 used)

**Color Mapping:**
```
0 = White  (255,255,255)
1 = Black  (0,0,0)
2 = Red    (220,0,0)
3 = Yellow (255,216,0)
4 = Blue   (0,0,200)
5 = Green  (0,160,0)
6 = Orange (255,128,0)
```

**File Structure:**
```
Byte 0: [Pixel 0 (high nibble)][Pixel 1 (low nibble)]
Byte 1: [Pixel 2][Pixel 3]
...
Byte 191999: [Pixel 383998][Pixel 383999]
```

### PNG Preview

Standard PNG format for reference and documentation.

---

## Examples

### Example 1: Basic Welcome Screen

```
Tools needed:
- welcome-screen-designer.html

Steps:
1. Add blue rectangle (header bar)
2. Add white text "Kin:D"
3. Add instruction text
4. Add WiFi credentials
5. Export RAW7
```

### Example 2: Welcome Screen with QR Code

```
Tools needed:
- welcome-screen-designer.html

Steps:
1. Enter admin token in export panel
2. Click "Add QR Code"
3. Add surrounding instructions
4. Add branding elements
5. Export RAW7
```

---

## Tips & Best Practices

### Design Tips

1. **High Contrast**: Use black on white or white on colored backgrounds
2. **Large Text**: Minimum 20px for body text, 32px+ for headers
3. **Simple Layouts**: E-ink has limited color, keep it clean
4. **Test on Hardware**: Colors look different on e-ink vs screen
5. **Include QR Code**: Makes setup seamless for customers

### Production Tips

1. **Batch Processing**: Use same design for product batches
2. **Version Control**: Keep PNG exports for reference
3. **Token Management**: Document admin tokens used
4. **SD Card Quality**: Use reliable SD cards (Class 10+)
5. **Verify File Size**: Always check RAW7 is exactly 192,000 bytes

### Troubleshooting

Common issues:

**Wrong file size:**
- Export from designer always creates correct size
- If manually editing, ensure exactly 192,000 bytes

**Colors look wrong:**
- E-ink color reproduction is approximate
- Some colors blend/dither
- Test on actual hardware

**QR code won't scan:**
- Ensure adequate size (min 150×150px)
- Use high contrast (black on white)
- Test with multiple scanner apps

---

## Future Tools (Planned)

- **Batch RAW7 Converter**: Convert multiple images
- **Template Library**: Pre-made welcome screen templates
- **Font Manager**: Add custom fonts to designer
- **Device Provisioning Tool**: Flash multiple devices
- **Analytics Dashboard**: Track device setup completion

---

## Contributing

To add new tools:

1. Create tool in this directory
2. Update this README
3. Add documentation if needed
4. Submit PR

---

## Support

For tool-specific help:
- See individual tool documentation
- Check GitHub issues
- Review examples above

For firmware-related help:
- See `../firmware/README.md`
- Check firmware documentation

---

## License

Part of the Kin:D Family Display project.
