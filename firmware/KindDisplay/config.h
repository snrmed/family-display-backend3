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
#define PIN_EPD_DC    23
#define PIN_EPD_SCK   18
#define PIN_EPD_MOSI  19

// ============================================================
// NEW: Mode Switch pins (3-position slide switch)
// ============================================================
// Switch position detection:
// - NORMAL MODE (center): GPIO34 = HIGH, GPIO35 = LOW
// - SPECIAL MODE (up):    GPIO34 = LOW,  GPIO35 = HIGH
#define PIN_SWITCH_34      34  // Switch position detector A
#define PIN_SWITCH_35      35  // Switch position detector B

// Status LED (used for firmware feedback)
#define PIN_STATUS_LED     2   // GPIO2 - Built-in LED on most ESP32 boards

// Battery monitoring (ADC input via voltage divider)
// IMPORTANT: Set this to your actual battery sense pin!
// Common options: GPIO36 (VP), GPIO39 (VN), GPIO34, GPIO35
// If not using battery, this feature will be skipped
#define PIN_BATTERY_ADC    36  // Change this to your actual battery sense pin
#define BATTERY_ENABLED    true  // Set to false to disable battery monitoring

// SD Card pins (sharing VSPI with display)
// CS pins are separate: Display=GPIO5, SD=GPIO13
#define SD_CARD_ENABLED   false   // SD card disabled - using text-only mode
#define PIN_SD_CS     13  // CS pin (separate from display CS)
#define PIN_SD_MOSI   19  // CMD on board (VSPI MOSI, shared with display)
#define PIN_SD_MISO   27  // DAT on board (VSPI MISO)
#define PIN_SD_SCK    18  // CLK on board (VSPI SCK, shared with display)

// ============================================================
// NETWORK CONFIGURATION
// ============================================================

// Access Point for WiFi setup
#define AP_SSID       "KIND-Setup"
#define AP_PASSWORD   "kind1234"
#define AP_IP         "192.168.4.1"

// Backend API configuration
#define BACKEND_URL   "https://family-display-backend-867804884116.australia-southeast1.run.app"
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

// Button/Switch timing
#define BUTTON_DEBOUNCE_MS    50
#define BUTTON_LONG_PRESS_MS  6000  // 6 seconds for factory reset

// WiFi connection timeout
#define WIFI_CONNECT_TIMEOUT  20000  // 20 seconds

// ============================================================
// NEW: Panel Protection & Throttling
// ============================================================
#define MIN_REFRESH_INTERVAL_MS     (5 * 60 * 1000)  // 5 minutes minimum between refreshes
#define RATE_LIMIT_WINDOW_MS        (2 * 60 * 1000)  // 2 minute window for rate limiting
#define RATE_LIMIT_MAX_REFRESHES    3                // Max 3 refreshes within window

// ============================================================
// NEW: Battery Configuration
// ============================================================
#define BATTERY_LOW_THRESHOLD       20   // Percentage - show "TIME TO CHARGE" warning
#define BATTERY_CRITICAL_THRESHOLD  10   // Percentage - enter extended sleep
#define BATTERY_CRITICAL_SLEEP_HOURS 6   // Hours to sleep when critically low

// Battery voltage calibration (adjust for your voltage divider)
// Default assumes 2:1 divider (e.g., 8.4V max -> 4.2V at ADC input)
#define BATTERY_VOLTAGE_MIN         6.0f  // Empty battery voltage
#define BATTERY_VOLTAGE_MAX         8.4f  // Full battery voltage (2S LiPo)
#define BATTERY_ADC_REFERENCE       3.3f  // ESP32 ADC reference voltage
#define BATTERY_DIVIDER_RATIO       2.0f  // Voltage divider ratio

// ============================================================
// NEW: WiFi Auto-Recovery Configuration
// ============================================================
#define WIFI_MAX_FAILURES_BEFORE_RESET  3  // Enter setup mode after 3 failed boots

// ============================================================
// STORAGE CONFIGURATION
// ============================================================

// NVS (Non-Volatile Storage) keys
#define NVS_NAMESPACE  "kindconfig"
#define NVS_WIFI_SSID  "wifi_ssid"
#define NVS_WIFI_PASS  "wifi_pass"
#define NVS_BACKEND    "backend_url"

// SD Card paths
#define SD_CACHE_FILE     "/last.raw7"
#define SD_WELCOME_FILE   "/welcome.raw7"  // Welcome screen for first boot

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
