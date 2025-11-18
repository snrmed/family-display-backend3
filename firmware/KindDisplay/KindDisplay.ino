/*
 * KIND / Family Display - ESP32 Firmware
 * ============================================================
 * 7-Color E-Ink Display (Spectra-6 / ACeP)
 * Resolution: 800×480
 * Panel: P730010-MF1-A
 * ============================================================
 *
 * Features:
 * - WiFi setup portal (AP mode on first boot)
 * - Daily wake at 01:00 to refresh display
 * - RAW7 image format from backend
 * - Switch modes:
 *   - NORMAL MODE (center): Standard operation
 *   - SPECIAL MODE (up): Background reroll before fetch
 * - SD card caching for offline fallback
 * - Deep sleep for power efficiency
 * - Status LED feedback (GPIO2)
 * - Battery monitoring with low-battery overlay
 * - Auto-recovery from WiFi failures
 * - Panel protection (refresh throttling)
 *
 * ============================================================
 */

#include "config.h"
#include "display_driver.h"
#include "wifi_manager.h"
#include "raw7_decoder.h"
#include "button_handler.h"
#include "rtc_manager.h"
#include "sd_manager.h"
#include "qr_display.h"
#include "text_welcome.h"   // NEW: Text-based welcome screen
#include "led_status.h"     // NEW: LED status feedback
#include "battery.h"        // NEW: Battery monitoring

// ============================================================
// Global Objects
// ============================================================
SpectraDisplay display;
WiFiManager wifiMgr;
RAW7Decoder imageDecoder;
ButtonHandler button;      // NEW: Manages slide switch (GPIO 34/35) for mode detection
RTCManager rtcMgr;
SDManager sdCard;
LEDStatus statusLED;       // NEW: Status LED (GPIO2)
BatteryMonitor battery;    // NEW: Battery monitoring

// ============================================================
// State Flags
// ============================================================
bool firstBoot = false;
SwitchMode currentMode = MODE_UNKNOWN;  // NEW: Current switch position

// ============================================================
// Function Prototypes
// ============================================================
void handleFirstBoot();
void handleNormalMode();          // NEW: Normal operation
void handleSpecialMode();         // NEW: Special mode (background reroll)
void updateDisplay(bool triggerReroll = false);  // Updated signature
void enterDeepSleep();
void showErrorScreen(const char* message);
void checkBatteryAndSleep();      // NEW: Battery check before operations
void handleFactoryReset();        // NEW: Factory reset handler

// ============================================================
// Setup - Runs once on boot
// ============================================================
void setup() {
    // Initialize serial
    #if DEBUG_SERIAL
    Serial.begin(SERIAL_BAUD);
    delay(1000);  // Wait for serial to stabilize
    #endif

    DEBUG_PRINTLN("\n\n");
    DEBUG_PRINTLN("========================================");
    DEBUG_PRINTLN("  KIND Display - Firmware v2.0");
    DEBUG_PRINTLN("  7-Color E-Ink Display + Extensions");
    DEBUG_PRINTLN("========================================");

    // NEW: Initialize LED status
    statusLED.begin();

    // NEW: Initialize battery monitor
    battery.begin();

    // Determine wake reason
    esp_sleep_wakeup_cause_t wakeReason = RTCManager::getWakeupCause();
    DEBUG_PRINT("Wake Reason: ");
    DEBUG_PRINTLN(RTCManager::getWakeupReasonString());

    // Initialize switch handler
    button.begin();

    // Determine mode based on wake source
    // Rotary switch springs back to position 0, so we check which GPIO triggered wake
    if (ButtonHandler::wasWakeSource()) {
        uint8_t wakePin = ButtonHandler::getWakePin();
        DEBUG_PRINTF("Switch: Woken by rotary switch - GPIO%d\n", wakePin);

        // Map wake pin to mode
        if (wakePin == PIN_SWITCH_34) {
            currentMode = MODE_NORMAL;
            DEBUG_PRINTLN("Switch: Rotated DOWN → NORMAL mode");
        } else if (wakePin == PIN_SWITCH_35) {
            currentMode = MODE_SPECIAL;
            DEBUG_PRINTLN("Switch: Rotated CENTER → SPECIAL mode");
        } else {
            currentMode = MODE_UNKNOWN;
        }
    } else {
        // Timer wake or other - default to normal mode
        currentMode = MODE_NORMAL;
        DEBUG_PRINTLN("Switch: Timer wake → NORMAL mode (default)");
    }

    // Initialize display
    if (!display.begin()) {
        DEBUG_PRINTLN("FATAL: Display initialization failed");
        statusLED.show(LED_FIVE_QUICK_BLINKS);  // Error indication
        showErrorScreen("Display Init Failed");
        delay(5000);
        ESP.restart();
    }

    // NEW: Check battery before any heavy operations
    checkBatteryAndSleep();

    // NEW: Check WiFi failure count for auto-recovery (Part 5)
    uint8_t wifiFailures = rtcMgr.getWiFiFailureCount();
    if (wifiFailures >= WIFI_MAX_FAILURES_BEFORE_RESET) {
        DEBUG_PRINTF("WiFi: Auto-recovery triggered (%d failures)\n", wifiFailures);
        DEBUG_PRINTLN("WiFi: Clearing credentials and entering setup mode");

        // Clear credentials and reset failure count
        wifiMgr.clearCredentials();
        rtcMgr.resetWiFiFailureCount();

        // Enter setup mode
        handleFirstBoot();
        return;  // Will restart after setup
    }

    // Check if WiFi credentials exist
    if (!wifiMgr.hasCredentials()) {
        DEBUG_PRINTLN("No WiFi credentials found - entering setup mode");
        firstBoot = true;
        handleFirstBoot();
        return;  // Will restart after setup
    }

    // Handle operation based on switch mode
    switch (currentMode) {
        case MODE_NORMAL:
            DEBUG_PRINTLN("=== NORMAL MODE ===");
            handleNormalMode();
            break;

        case MODE_SPECIAL:
            DEBUG_PRINTLN("=== SPECIAL MODE (Background Reroll) ===");
            handleSpecialMode();
            break;

        default:
            DEBUG_PRINTLN("=== UNKNOWN MODE - defaulting to NORMAL ===");
            handleNormalMode();
            break;
    }

    // Enter deep sleep
    enterDeepSleep();
}

// ============================================================
// Loop - Not used (device sleeps after setup)
// ============================================================
void loop() {
    // Should never reach here in normal operation
    delay(1000);
}

// ============================================================
// First Boot - WiFi Setup Portal (Part 4)
// ============================================================
void handleFirstBoot() {
    DEBUG_PRINTLN("\n=== FIRST BOOT / SETUP MODE ===");

    // Generate text-based welcome screen
    DEBUG_PRINTLN("Generating text-based welcome screen...");
    if (!TextWelcome::showWelcomeScreen(display)) {
        DEBUG_PRINTLN("Failed to generate text-based welcome screen");
    }

    // Show setup instructions
    DEBUG_PRINTLN("Connect to WiFi: KIND-Setup (password: kind1234)");
    DEBUG_PRINTLN("Visit: http://192.168.4.1 or any website");

    // Start WiFi configuration portal with LED slow blink
    wifiMgr.startConfigPortal(&statusLED);  // NEW: Pass LED for slow blink

    // Configuration saved, restart
    DEBUG_PRINTLN("Configuration saved. Restarting...");
    delay(1000);
    ESP.restart();
}

// ============================================================
// NORMAL MODE Handler (Part 2)
// ============================================================
void handleNormalMode() {
    DEBUG_PRINTLN("\n=== NORMAL MODE - Standard Operation ===");

    // Standard operation: fetch and display
    updateDisplay(false);  // No background reroll
}

// ============================================================
// SPECIAL MODE Handler (Part 2)
// ============================================================
void handleSpecialMode() {
    DEBUG_PRINTLN("\n=== SPECIAL MODE - Background Reroll ===");

    // Special operation: trigger background reroll, then fetch and display
    updateDisplay(true);  // Trigger background reroll
}

// ============================================================
// Update Display - Fetch and show new image (EXTENDED)
// ============================================================
void updateDisplay(bool triggerReroll) {
    DEBUG_PRINTLN("\n--- Updating Display ---");

    // Connect to WiFi with LED fast blink feedback
    if (!wifiMgr.connect(&statusLED)) {  // NEW: Pass LED for feedback
        DEBUG_PRINTLN("WiFi connection failed");

        // NEW: Record WiFi failure for auto-recovery (Part 5)
        rtcMgr.recordWiFiFailure();

        showErrorScreen("WiFi Failed");
        delay(3000);
        return;
    }

    // NEW: Record successful WiFi connection (Part 5)
    rtcMgr.recordWiFiSuccess();

    // Get timezone offset from WiFi settings
    long timezoneOffset = wifiMgr.getTimezoneOffset();
    DEBUG_PRINTF("Timezone: UTC%+ld hours (%ld seconds)\n", timezoneOffset / 3600, timezoneOffset);

    // Initialize RTC and sync time with user's timezone
    rtcMgr.begin("pool.ntp.org", timezoneOffset, 0);

    // NEW: Check refresh throttling AFTER WiFi/NTP sync (Part 7)
    // This ensures we have accurate time for throttling checks
    if (!rtcMgr.canRefreshNow()) {
        DEBUG_PRINTLN("Refresh throttled - skipping update and returning to sleep");
        WiFi.disconnect(true);
        return;
    }

    // Get backend URL and device name
    String backendUrl = wifiMgr.getBackendUrl();
    String deviceName = wifiMgr.getDeviceName();
    DEBUG_PRINTF("Backend URL: %s\n", backendUrl.c_str());
    DEBUG_PRINTF("Device Name: %s\n", deviceName.c_str());

    // NEW: If in SPECIAL mode, trigger background reroll first (Part 2)
    if (triggerReroll) {
        DEBUG_PRINTLN("Triggering background reroll...");
        if (imageDecoder.triggerBackgroundReroll(backendUrl.c_str(), deviceName.c_str())) {
            DEBUG_PRINTLN("Background reroll successful");
            statusLED.show(LED_TRIPLE_BLINK);  // NEW: Triple blink feedback
            delay(2000);  // Give backend time to regenerate
        } else {
            DEBUG_PRINTLN("Background reroll failed - continuing with fetch");
        }
    }

    // Fetch RAW7 image
    size_t imageSize = 0;
    uint8_t* imageBuffer = imageDecoder.fetchImage(backendUrl.c_str(), deviceName.c_str(), imageSize);

    if (!imageBuffer || imageSize != RAW7_SIZE) {
        DEBUG_PRINTLN("Image fetch failed");

        showErrorScreen("Image Fetch Failed");
        WiFi.disconnect(true);
        delay(3000);
        return;
    }

    DEBUG_PRINTLN("Image fetched successfully");

    // NEW: Apply low battery overlay if needed (Part 8)
    battery.overlayLowBatteryWarning(imageBuffer, imageSize);

    // Display image
    display.displayRAW7(imageBuffer, imageSize);

    // Clean up
    free(imageBuffer);
    display.powerOff();

    // NEW: Show solid LED for 3 seconds after successful display (Part 1)
    statusLED.show(LED_SOLID_3S);

    // NEW: Record this refresh for throttling (Part 6 & 7)
    rtcMgr.recordRefresh();

    // Disconnect WiFi
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);

    DEBUG_PRINTLN("Display update complete");
}

// ============================================================
// Enter Deep Sleep (UPDATED)
// ============================================================
void enterDeepSleep() {
    DEBUG_PRINTLN("\n--- Preparing for Deep Sleep ---");

    // Put display to sleep
    display.sleep();

    // NEW: Turn off LED before sleep (Part 1)
    statusLED.off();

    // Enable rotary switch wake from deep sleep
    // Momentary rotary switch triggers briefly on rotation
    // EXT1 wake on ANY_HIGH will detect rotation to position 34 or 35
    button.enableWakeup();

    // Calculate and enter deep sleep
    rtcMgr.sleepUntilWake();

    // Never reaches here
}

// ============================================================
// Show Error Screen
// ============================================================
void showErrorScreen(const char* message) {
    DEBUG_PRINTF("ERROR: %s\n", message);

    // Clear display to red to indicate error
    display.clear(EPD_RED);
    display.powerOff();

    // Could add text rendering here if font library available
}

// ============================================================
// NEW: Check Battery and Enter Extended Sleep if Critical (Part 8)
// ============================================================
void checkBatteryAndSleep() {
    if (!BATTERY_ENABLED) {
        return;  // Skip if battery monitoring is disabled
    }

    uint8_t batteryPercent = battery.getPercentage();
    DEBUG_PRINTF("Battery: %d%%\n", batteryPercent);

    if (battery.isCritical()) {
        DEBUG_PRINTF("Battery: CRITICAL (%d%%) - entering extended sleep\n", batteryPercent);

        // Show minimal low-battery indicator on display
        display.clear(EPD_RED);
        display.powerOff();

        // Show 5 blinks to indicate critical battery
        statusLED.show(LED_FIVE_QUICK_BLINKS);

        // Turn off LED
        statusLED.off();

        // Enter extended deep sleep (6 hours)
        DEBUG_PRINTF("Battery: Sleeping for %d hours to protect battery\n", BATTERY_CRITICAL_SLEEP_HOURS);
        rtcMgr.sleepForSeconds(BATTERY_CRITICAL_SLEEP_HOURS * 3600ULL);

        // Never reaches here
    }

    // If battery is low (but not critical), continue normally
    // The low battery overlay will be applied during updateDisplay()
}

// ============================================================
// NEW: Factory Reset Handler (Part 3)
// ============================================================
void handleFactoryReset() {
    DEBUG_PRINTLN("\n!!! FACTORY RESET TRIGGERED !!!");

    // Show 5 quick blinks
    statusLED.show(LED_FIVE_QUICK_BLINKS);

    // Clear all WiFi and app config
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    prefs.clear();
    prefs.end();

    DEBUG_PRINTLN("Factory reset: All settings cleared");

    // Clear RTC data as well
    rtcMgr.resetWiFiFailureCount();

    // Show reset message on display
    display.clear(EPD_BLACK);
    display.powerOff();

    DEBUG_PRINTLN("Factory reset complete. Restarting into setup mode...");
    delay(2000);
    ESP.restart();
}
