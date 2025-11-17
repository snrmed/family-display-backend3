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
 * - Button controls:
 *   - Short press: Trigger background reroll
 *   - Long press (6s): Factory reset
 * - SD card caching for offline fallback
 * - Deep sleep for power efficiency
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

// ============================================================
// Global Objects
// ============================================================
SpectraDisplay display;
WiFiManager wifiMgr;
RAW7Decoder imageDecoder;
ButtonHandler button(PIN_BUTTON);
RTCManager rtcMgr;
SDManager sdCard;

// ============================================================
// State Flags
// ============================================================
bool firstBoot = false;
bool buttonPressed = false;
bool isFactoryReset = false;

// ============================================================
// Function Prototypes
// ============================================================
void handleFirstBoot();
void handleButtonWake();
void handleScheduledWake();
void updateDisplay();
void enterDeepSleep();
void showErrorScreen(const char* message);

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
    DEBUG_PRINTLN("  KIND Display - Firmware v1.0");
    DEBUG_PRINTLN("  7-Color E-Ink Display");
    DEBUG_PRINTLN("========================================");

    // Determine wake reason
    esp_sleep_wakeup_cause_t wakeReason = RTCManager::getWakeupCause();
    DEBUG_PRINT("Wake Reason: ");
    DEBUG_PRINTLN(RTCManager::getWakeupReasonString());

    // Initialize button handler
    button.begin();

    // Initialize display
    if (!display.begin()) {
        DEBUG_PRINTLN("FATAL: Display initialization failed");
        showErrorScreen("Display Init Failed");
        delay(5000);
        ESP.restart();
    }

    // Initialize SD card (optional)
    if (sdCard.begin()) {
        DEBUG_PRINTLN("SD card available");
    } else {
        DEBUG_PRINTLN("SD card not available (optional)");
    }

    // Check if WiFi credentials exist
    if (!wifiMgr.hasCredentials()) {
        DEBUG_PRINTLN("No WiFi credentials found - entering setup mode");
        firstBoot = true;
        handleFirstBoot();
        return;  // Will restart after setup
    }

    // Handle different wake scenarios
    switch (wakeReason) {
        case ESP_SLEEP_WAKEUP_EXT0:
            // Button wake
            DEBUG_PRINTLN("Mode: Button Wake");
            handleButtonWake();
            break;

        case ESP_SLEEP_WAKEUP_TIMER:
            // Scheduled wake (01:00 daily)
            DEBUG_PRINTLN("Mode: Scheduled Wake");
            handleScheduledWake();
            break;

        default:
            // Power on / reset
            DEBUG_PRINTLN("Mode: Power On / Reset");
            handleScheduledWake();  // Treat as normal update
            break;
    }

    // Enter deep sleep (won't reach here if factory reset)
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
// First Boot - WiFi Setup Portal
// ============================================================
void handleFirstBoot() {
    DEBUG_PRINTLN("\n=== FIRST BOOT SETUP ===");

    // Show QR code setup screen on display
    QRDisplay::showSetupScreen(display);
    display.powerOff();

    // Start WiFi configuration portal
    wifiMgr.startConfigPortal();

    // Configuration saved, restart
    DEBUG_PRINTLN("Configuration saved. Restarting...");
    delay(1000);
    ESP.restart();
}

// ============================================================
// Button Wake Handler
// ============================================================
void handleButtonWake() {
    DEBUG_PRINTLN("\n=== BUTTON WAKE ===");

    // Wait a bit for user to release button
    delay(500);

    // Check for long press (factory reset)
    unsigned long checkStart = millis();
    while (millis() - checkStart < BUTTON_LONG_PRESS_MS + 1000) {
        ButtonEvent event = button.checkButton();

        if (event == BUTTON_LONG_PRESS) {
            DEBUG_PRINTLN("\n!!! FACTORY RESET TRIGGERED !!!");

            // Clear credentials
            wifiMgr.clearCredentials();

            // Show reset message
            display.clear(EPD_BLACK);
            display.powerOff();

            DEBUG_PRINTLN("Factory reset complete. Restarting...");
            delay(2000);
            ESP.restart();
            return;
        }

        if (event == BUTTON_SHORT_PRESS) {
            DEBUG_PRINTLN("Short press detected - Background reroll");

            // Connect to WiFi
            if (!wifiMgr.connect()) {
                DEBUG_PRINTLN("WiFi connection failed");
                showErrorScreen("WiFi Failed");
                delay(3000);
                return;
            }

            // Get backend URL and device name
            String backendUrl = wifiMgr.getBackendUrl();
            String deviceName = wifiMgr.getDeviceName();

            // Trigger background reroll
            if (imageDecoder.triggerBackgroundReroll(backendUrl.c_str(), deviceName.c_str())) {
                DEBUG_PRINTLN("Background reroll successful");
                delay(2000);  // Give backend time to regenerate

                // Fetch and display new image
                updateDisplay();
            } else {
                DEBUG_PRINTLN("Background reroll failed");
                showErrorScreen("Reroll Failed");
                delay(3000);
            }

            WiFi.disconnect(true);
            return;
        }

        delay(50);
    }

    DEBUG_PRINTLN("No button action detected");
}

// ============================================================
// Scheduled Wake Handler (Daily 01:00)
// ============================================================
void handleScheduledWake() {
    DEBUG_PRINTLN("\n=== SCHEDULED WAKE ===");
    updateDisplay();
}

// ============================================================
// Update Display - Fetch and show new image
// ============================================================
void updateDisplay() {
    DEBUG_PRINTLN("\n--- Updating Display ---");

    // Connect to WiFi
    if (!wifiMgr.connect()) {
        DEBUG_PRINTLN("WiFi connection failed");

        // Try to load cached image from SD card
        if (sdCard.isAvailable() && sdCard.hasCachedImage()) {
            DEBUG_PRINTLN("Loading cached image from SD card");
            size_t size = 0;
            uint8_t* cachedImage = sdCard.loadRAW7(size);

            if (cachedImage && size == RAW7_SIZE) {
                display.displayRAW7(cachedImage, size);
                free(cachedImage);
                display.powerOff();
                DEBUG_PRINTLN("Displayed cached image");
                return;
            }

            if (cachedImage) free(cachedImage);
        }

        showErrorScreen("WiFi Failed");
        delay(3000);
        return;
    }

    // Initialize RTC and sync time
    rtcMgr.begin("pool.ntp.org", 0, 0);  // UTC, adjust gmtOffset as needed

    // Get backend URL and device name
    String backendUrl = wifiMgr.getBackendUrl();
    String deviceName = wifiMgr.getDeviceName();
    DEBUG_PRINTF("Backend URL: %s\n", backendUrl.c_str());
    DEBUG_PRINTF("Device Name: %s\n", deviceName.c_str());

    // Fetch RAW7 image
    size_t imageSize = 0;
    uint8_t* imageBuffer = imageDecoder.fetchImage(backendUrl.c_str(), deviceName.c_str(), imageSize);

    if (!imageBuffer || imageSize != RAW7_SIZE) {
        DEBUG_PRINTLN("Image fetch failed");

        // Try cached image
        if (sdCard.isAvailable() && sdCard.hasCachedImage()) {
            DEBUG_PRINTLN("Falling back to cached image");
            size_t size = 0;
            uint8_t* cachedImage = sdCard.loadRAW7(size);

            if (cachedImage && size == RAW7_SIZE) {
                display.displayRAW7(cachedImage, size);
                free(cachedImage);
                display.powerOff();
                WiFi.disconnect(true);
                return;
            }

            if (cachedImage) free(cachedImage);
        }

        showErrorScreen("Image Fetch Failed");
        WiFi.disconnect(true);
        delay(3000);
        return;
    }

    DEBUG_PRINTLN("Image fetched successfully");

    // Cache image to SD card
    if (sdCard.isAvailable()) {
        if (sdCard.saveRAW7(imageBuffer, imageSize)) {
            DEBUG_PRINTLN("Image cached to SD card");
        }
    }

    // Display image
    display.displayRAW7(imageBuffer, imageSize);

    // Clean up
    free(imageBuffer);
    display.powerOff();

    // Disconnect WiFi
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);

    DEBUG_PRINTLN("Display update complete");
}

// ============================================================
// Enter Deep Sleep
// ============================================================
void enterDeepSleep() {
    DEBUG_PRINTLN("\n--- Preparing for Deep Sleep ---");

    // Put display to sleep
    display.sleep();

    // Enable button wake
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
