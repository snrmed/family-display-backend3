#ifndef CONFIG_H
#define CONFIG_H

// Multi-device hardware configuration system
// Automatically selects correct pin mappings based on device type
// Supports: ESP32 Dev Board, reTerminal E1002, XIAO ePaper EE04
#include "hardware_config.h"

// ============================================================
// HARDWARE CONFIGURATION - Multi-Device Support
// ============================================================

// Display specifications (same for all devices using Spectra-6)
#define DISPLAY_WIDTH  EPD_WIDTH
#define DISPLAY_HEIGHT EPD_HEIGHT
#define DISPLAY_COLORS EPD_COLOR_MODE

// SPI Pin mapping - auto-configured based on device type
#define PIN_EPD_BUSY  EPD_BUSY
#define PIN_EPD_RST   EPD_RST
#define PIN_EPD_CS    EPD_CS
#define PIN_EPD_DC    EPD_DC
#define PIN_EPD_SCK   EPD_CLK
#define PIN_EPD_MOSI  EPD_MOSI

// ============================================================
// Button/Switch pins - auto-configured based on device type
// ============================================================
#if defined(DEVICE_ORIGINAL_ESP32)
// Original ESP32 dev board has rotary switch
#define PIN_SWITCH_34      34  // Rotary position detector A
#define PIN_SWITCH_35      35  // Rotary position detector B
#define PIN_BUTTON_CENTER  BUTTON_CENTER
#else
// New devices (reTerminal, XIAO) use regular buttons
#define PIN_BUTTON_CENTER  BUTTON_CENTER
#endif

// Status LED (used for firmware feedback)
#define PIN_STATUS_LED     2   // GPIO2 - Built-in LED on most ESP32 boards

// Battery monitoring - auto-configured based on device type
#if BATTERY_ADC_PIN >= 0
#define BATTERY_ENABLED    true
#define PIN_BATTERY_ADC    BATTERY_ADC_PIN
#define PIN_BATTERY_ENABLE BATTERY_ENABLE_PIN
#else
#define BATTERY_ENABLED    false
#define PIN_BATTERY_ADC    36  // Fallback (not used)
#define PIN_BATTERY_ENABLE -1
#endif

// SD Card pins - auto-configured based on device type
// Note: Some devices share SPI bus with display
#if SD_CS >= 0
#define SD_CARD_ENABLED   true
#define PIN_SD_CS     SD_CS
#define PIN_SD_MOSI   SD_MOSI
#define PIN_SD_MISO   SD_MISO
#define PIN_SD_SCK    SD_CLK
#else
#define SD_CARD_ENABLED   false
#define PIN_SD_CS     5   // Fallback (not used)
#define PIN_SD_MOSI   23
#define PIN_SD_MISO   19
#define PIN_SD_SCK    18
#endif

// ============================================================
// NETWORK CONFIGURATION
// ============================================================

// Access Point for WiFi setup
#define AP_SSID       "KIND-Setup"
#define AP_PASSWORD   "kind1234"
#define AP_IP         "192.168.4.1"

// Backend API configuration
#define BACKEND_URL   "https://family-display-backend-867804884116.australia-southeast1.run.app"
#define RAW7_ENDPOINT "/v1/raw7?device="
#define REROLL_ENDPOINT "/v1/frame_bg_reroll"

// HTTP timeout - increased for slow server-side RAW7 generation
#define HTTP_TIMEOUT  120000  // 120 seconds (2 minutes)

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
