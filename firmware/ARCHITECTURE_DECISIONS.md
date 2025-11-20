# Firmware Architecture Decisions

This document outlines key architectural decisions for the multi-device firmware.

## 1. Folder Structure: Separate Projects Per Device

### Decision
Create **3 separate firmware projects**, one per device:
- `firmware/reterminal-e1002/` - Seeed reTerminal E1002
- `firmware/xiao-ee04/` - Seeed XIAO ePaper Display Board EE04
- `firmware/waveshare-esp32-rev3/` - Waveshare e-Paper ESP32 Driver Board Universal REV3

### Rationale
- **Clarity**: Each device has its own complete, buildable project
- **Independence**: Devices can evolve separately without conflicts
- **Simplicity**: No complex #ifdef chains, each project is self-contained
- **Contribution**: Easier for contributors to work on specific devices
- **Documentation**: Each device has its own README and build instructions

### Shared Code
Common modules (display driver, WiFi manager, etc.) live in `firmware/shared/` and are referenced via PlatformIO's `lib_extra_dirs`.

---

## 2. Memory Strategy: PSRAM-Only (No SD Card)

### Decision
**Use PSRAM as primary storage**, eliminate SD card dependency.

### Rationale

#### ESP32-S3 Capabilities
- **8MB PSRAM**: Enough for 40+ RAW7 images (192KB each)
- **32MB Flash/SPIFFS**: Can cache multiple images
- **Fast access**: PSRAM is faster than SD card
- **Reliability**: No SD card failure modes

#### Storage Layout (ESP32-S3)
```
┌─────────────────────────────────────┐
│ PSRAM (8MB)                         │
│  - Active image buffer (192KB)     │
│  - Decompression buffer            │
│  - HTTP receive buffer             │
│  - Fallback image cache (optional) │
│  └─ 7.5MB+ available               │
├─────────────────────────────────────┤
│ Flash/SPIFFS (4-8MB)                │
│  - Last successful image (192KB)   │
│  - Welcome screen (192KB)          │
│  - Configuration                    │
│  └─ 3.5MB+ available               │
└─────────────────────────────────────┘
```

#### Benefits
- **Simpler hardware**: No SD card slot needed (XIAO EE04, reTerminal)
- **Lower power**: No SD card power consumption
- **Faster**: PSRAM access is much faster than SD SPI
- **More reliable**: No SD card corruption issues
- **Cost**: Cheaper without SD card components

#### Trade-offs
- ❌ Can't cache unlimited images
- ✅ Don't need to - one daily render is sufficient
- ✅ SPIFFS still provides persistent fallback

### Implementation
1. Store latest image in SPIFFS (persistent across reboots)
2. Use PSRAM for working buffers during HTTP fetch and display
3. Keep welcome screen in SPIFFS for first boot
4. No SD card code in new device builds

---

## 3. Image Format: Keep RAW7 (Don't Switch to PNG)

### Decision
**Continue using RAW7 format** from backend to device.

### Comparison

| Aspect | RAW7 (Current) | PNG (Alternative) |
|--------|----------------|-------------------|
| **File Size** | 192KB (exact) | 200-800KB (variable) |
| **Backend Complexity** | Color quantization required | Simple PNG encoding |
| **Device Processing** | Unpack only (fast) | Decode + quantize (slow) |
| **Network Transfer** | Fast (smaller) | Slower (larger) |
| **Battery Impact** | Minimal | Higher (more CPU) |
| **Memory Usage** | Fixed, predictable | Variable, unpredictable |
| **Color Accuracy** | Pre-optimized for 7 colors | Needs dithering on device |
| **Debugging** | Harder (binary format) | Easier (standard format) |

### Rationale

#### Why RAW7 Wins
1. **Optimized for E-Paper**: RAW7 is specifically designed for 7-color displays
2. **Bandwidth**: 192KB vs 300-500KB average for PNG - saves WiFi power
3. **Processing**: Backend does heavy color quantization, device just unpacks
4. **Battery Life**: Less CPU time = better battery life
5. **Predictable**: Fixed size makes memory management trivial
6. **Already Works**: Backend RAW7 generation is mature and tested

#### When PNG Makes Sense
- Debugging (can view in standard tools)
- Generic image displays (not e-paper specific)
- Backend can't do color quantization

#### Hybrid Option (Future)
Could support **both**:
- RAW7 for production (optimized)
- PNG for debugging/development (easier to inspect)
- Device detects format by header magic bytes

### Implementation
- Keep RAW7 as primary format
- Backend continues color quantization with Floyd-Steinberg dithering
- Device unpacks RAW7 (2 pixels/byte → 1 nibble/pixel)
- No changes needed!

---

## 4. Sensor Integration for reTerminal E1002

### Available Sensors
1. **SHT40 Temperature & Humidity** (I2C 0x44)
2. **Microphone** (I2S - GPIO41/42)
3. **Buzzer** (GPIO45)

### Proposed Features

#### 🌡️ Temperature & Humidity Display
**Use Case**: Indoor climate monitoring on family display

**Implementation**:
```cpp
// Read sensor every wake cycle
float temp = sht40.readTemperature();
float humidity = sht40.readHumidity();

// Send to backend as URL params
String url = BACKEND_URL + "/v1/raw7?device=" + deviceId +
             "&temp=" + String(temp, 1) +
             "&humidity=" + String(humidity, 0);
```

**Backend Integration**:
- Backend receives temp/humidity in query params
- Generates image with climate overlay
- Could show "Feels like 72°F, 45% humidity" in corner
- Historical graphing over time

**Benefits**:
- No extra screen - reuses main display
- Contextual information with family photos
- Can trigger alerts if out of range

#### 🔊 Buzzer Notifications
**Use Cases**:
- **Reminders**: Medication, appointments
- **Weather alerts**: Storm warnings
- **Smart home**: Doorbell pressed, motion detected
- **Button feedback**: Beep on button press
- **Error alerts**: Low battery, WiFi failed

**Implementation**:
```cpp
// Backend sends buzzer pattern in response header
X-Buzzer-Pattern: 3,100,200  // 3 beeps, 100ms on, 200ms off

// Device plays pattern
void playBuzzerPattern(int count, int onMs, int offMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(onMs);
    digitalWrite(BUZZER_PIN, LOW);
    if (i < count - 1) delay(offMs);
  }
}
```

**Integration Options**:
1. **Calendar reminders**: Beep at specific times
2. **Weather warnings**: Beep if severe weather in forecast
3. **Smart home events**: Beep when someone arrives home
4. **Photo mode**: Beep before capturing family photo (countdown)

#### 🎤 Microphone Features (Future)

**Note**: More complex, requires audio processing

**Potential Use Cases**:
1. **Voice Commands**:
   - "Update display" - triggers refresh
   - "Show weather" - switches to weather view
   - "Goodnight" - enters low-power mode until morning

2. **Voice Notes**:
   - Record 10s voice memo
   - Upload to backend
   - Backend transcribes and adds to display as text overlay
   - "Reminder: Pick up milk"

3. **Sound Level Monitoring**:
   - Measure ambient noise
   - Display "Room is quiet" or "Noisy" on screen
   - Baby monitor - alert if sudden loud noise

4. **Music Recognition** (Advanced):
   - Detect if music playing
   - Show "Now playing" on display

**Implementation Complexity**: HIGH
- Requires I2S audio processing
- Speech recognition (cloud API needed)
- More power consumption
- Privacy concerns

**Recommendation**: **Start with temp/humidity + buzzer** (easy wins), add microphone features later if desired.

---

## 5. Recommended Sensor Implementation Priority

### Phase 1: Essential (Do First)
✅ **Temperature & Humidity Display**
- Easy to implement (I2C read)
- Low power impact
- High user value
- Backend can show climate data

✅ **Buzzer Notifications**
- Simple GPIO control
- Useful for reminders/alerts
- Good user feedback

### Phase 2: Enhanced (Do Later)
🔵 **Smart Home Integration**
- HomeAssistant MQTT
- Receive events, trigger buzzer
- Show smart home status on display

🔵 **Advanced Climate Features**
- Historical graphs (temp over week)
- Comfort level indicators
- Weather correlation

### Phase 3: Advanced (Future)
⚪ **Microphone Voice Commands**
- Complex audio processing
- Privacy implications
- Higher power usage
- Consider carefully before implementing

---

## 6. Device Comparison Matrix

| Feature | reTerminal E1002 | XIAO EE04 | Waveshare ESP32 REV3 |
|---------|------------------|-----------|----------------------|
| **MCU** | ESP32-S3 (8MB PSRAM) | ESP32-S3 Plus (8MB PSRAM) | ESP32 (No PSRAM) |
| **Display** | Spectra 6 (built-in) | Spectra 6 (separate) | Universal (any Waveshare) |
| **Battery** | 2000mAh (built-in) | User-provided | User-provided |
| **Temp Sensor** | ✅ SHT40 | ❌ | ❌ |
| **Microphone** | ✅ I2S | ❌ | ❌ |
| **Buzzer** | ✅ GPIO45 | ❌ | ❌ |
| **Font Chip** | ❌ | ✅ GT32L32S0140 | ❌ |
| **Enclosure** | ✅ Metal case | ❌ DIY | ❌ DIY |
| **SD Card** | ⚠️ Can add | ⚠️ Can add | ✅ Built-in |
| **Form Factor** | All-in-one | Compact + display | Driver board + display |
| **Use Case** | Premium display | Compact/custom | DIY/existing displays |

### Recommendation by Use Case
- **Best all-around**: **reTerminal E1002** (sensors, battery, enclosure)
- **Most compact**: **XIAO EE04** (smallest footprint)
- **Existing displays**: **Waveshare ESP32 REV3** (universal compatibility)
- **DIY projects**: **XIAO EE04** (most hackable)

---

## 7. Pin Mappings Summary

### reTerminal E1002 (ESP32-S3)
```cpp
EPD: CLK=7, MOSI=9, CS=10, DC=11, RST=12, BUSY=13
I2C: SDA=19, SCL=20 (SHT40 @ 0x44)
Buttons: Green=3, White=4
Battery: ADC=1, Enable=21
Buzzer: 45
Microphone: Power=38, BCLK=42, Data=41
```

### XIAO EE04 (ESP32-S3 Plus)
```cpp
EPD: CLK=7, MOSI=9, CS=44, DC=10, RST=38, BUSY=4
Buttons: KEY0=2, KEY1=3, KEY2=5
Battery: ADC=1, Enable=6
Font Chip: SPI (CS=TBD)
```

### Waveshare ESP32 REV3 (ESP32 Classic)
```cpp
EPD: CLK=13, MOSI=14, CS=15, DC=27, RST=26, BUSY=25
(Almost identical to original dev board except CS=15 vs 33)
```

---

## 8. Build Commands

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

---

## Summary

✅ **Separate folders** - Clear, maintainable structure
✅ **PSRAM-only** - No SD card dependency, simpler and more reliable
✅ **Keep RAW7** - Optimized for bandwidth and battery life
✅ **Sensor integration** - Start with temp/humidity + buzzer
✅ **Device-specific builds** - Each project standalone

This architecture provides maximum flexibility while keeping complexity manageable.
