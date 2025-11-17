#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// HARDWARE CONFIGURATION - ESP32 + Spectra-6 E-Ink
// ============================================================

// Display specifications
#define DISPLAY_WIDTH  800
#define DISPLAY_HEIGHT 480
#define DISPLAY_COLORS 7

// SPI Pin mapping (ESP32 to EPD adapter)
#define PIN_EPD_BUSY  4
#define PIN_EPD_RST   16
#define PIN_EPD_CS    5
#define PIN_EPD_DC    17
#define PIN_EPD_SCK   18
#define PIN_EPD_MOSI  23

// Button pin (adjust based on your hardware)
#define PIN_BUTTON    0  // GPIO0 (BOOT button) - change if using external button

// SD Card pins (using default VSPI)
#define PIN_SD_CS     13  // Adjust based on your hardware
#define PIN_SD_MOSI   15
#define PIN_SD_MISO   2
#define PIN_SD_SCK    14

// ============================================================
// NETWORK CONFIGURATION
// ============================================================

// Access Point for WiFi setup
#define AP_SSID       "KIND-Setup"
#define AP_PASSWORD   "kind1234"
#define AP_IP         "192.168.4.1"

// Backend API configuration
// NOTE: User should modify this to match their backend URL
#define BACKEND_URL   "http://YOUR_BACKEND_IP_OR_DOMAIN"  // e.g., "http://192.168.1.100:8080"
#define RAW7_ENDPOINT "/v1/raw7?device=familydisplay"
#define REROLL_ENDPOINT "/v1/frame_bg_reroll"

// HTTP timeout
#define HTTP_TIMEOUT  30000  // 30 seconds

// ============================================================
// TIMING CONFIGURATION
// ============================================================

// Daily wake time (HH:MM in 24-hour format)
#define WAKE_HOUR     1
#define WAKE_MINUTE   0

// Button timing
#define BUTTON_DEBOUNCE_MS    50
#define BUTTON_LONG_PRESS_MS  6000  // 6 seconds for factory reset

// WiFi connection timeout
#define WIFI_CONNECT_TIMEOUT  20000  // 20 seconds

// ============================================================
// STORAGE CONFIGURATION
// ============================================================

// NVS (Non-Volatile Storage) keys
#define NVS_NAMESPACE  "kindconfig"
#define NVS_WIFI_SSID  "wifi_ssid"
#define NVS_WIFI_PASS  "wifi_pass"
#define NVS_BACKEND    "backend_url"

// SD Card paths
#define SD_CACHE_FILE  "/last.raw7"

// ============================================================
// DISPLAY PALETTE (Spectra-6 E-Ink)
// ============================================================

// Color indices (matches backend RAW7 format)
enum EPDColor {
    EPD_WHITE  = 0,  // RGB: 255,255,255
    EPD_BLACK  = 1,  // RGB: 0,0,0
    EPD_RED    = 2,  // RGB: 220,0,0
    EPD_YELLOW = 3,  // RGB: 255,216,0
    EPD_BLUE   = 4,  // RGB: 0,0,200
    EPD_GREEN  = 5,  // RGB: 0,160,0
    EPD_ORANGE = 6   // RGB: 255,128,0
};

// ============================================================
// DEBUG CONFIGURATION
// ============================================================

// Enable serial debug output
#define DEBUG_SERIAL  true
#define SERIAL_BAUD   115200

// Debug macros
#if DEBUG_SERIAL
  #define DEBUG_PRINT(x)    Serial.print(x)
  #define DEBUG_PRINTLN(x)  Serial.println(x)
  #define DEBUG_PRINTF(...) Serial.printf(__VA_ARGS__)
#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
  #define DEBUG_PRINTF(...)
#endif

// ============================================================
// MEMORY CONFIGURATION
// ============================================================

// RAW7 image size (800×480 pixels, 2 pixels per byte)
#define RAW7_SIZE (DISPLAY_WIDTH * DISPLAY_HEIGHT / 2)  // 192000 bytes

// HTTP buffer size for chunked reading
#define HTTP_BUFFER_SIZE 4096

#endif // CONFIG_H
