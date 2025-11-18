#ifndef DISPLAY_DRIVER_H
#define DISPLAY_DRIVER_H

#include <Arduino.h>
#include <SPI.h>
#include "config.h"

// ============================================================
// Spectra-6 (E6) 7-Color E-Ink Display Driver
// ============================================================
// Panel: P730010-MF1-A
// Resolution: 800×480
// Colors: 7 (White, Black, Red, Yellow, Blue, Green, Orange)
// ============================================================

class SpectraDisplay {
public:
    SpectraDisplay();

    // Initialize the display hardware
    bool begin();

    // Display a RAW7 image buffer
    // Buffer must be 192000 bytes (800×480 pixels, 2 pixels per byte)
    bool displayRAW7(const uint8_t* buffer, size_t bufferSize);

    // Display RAW7 image from SD cache (memory efficient - no large buffer)
    bool displayRAW7FromSDCache(class SDManager& sdCard);

    // Display RAW7 image from SD file (memory efficient - no large buffer)
    bool displayRAW7FromSDFile(class SDManager& sdCard, const char* filepath);

    // Display RAW7 image from flash cache (memory efficient - no large buffer)
    bool displayRAW7FromFlashCache(class FlashCache& flashCache);

    // Display RAW7 image from flash file (memory efficient - no large buffer)
    bool displayRAW7FromFlashFile(class FlashCache& flashCache, const char* filepath);

    // Clear display to a single color
    void clear(uint8_t color = EPD_WHITE);

    // Power management
    void powerOn();
    void powerOff();
    void sleep();

    // Hardware reset
    void reset();

private:
    // Low-level EPD commands
    void sendCommand(uint8_t command);
    void sendData(uint8_t data);
    void sendData(const uint8_t* data, size_t len);

    // Wait for display to be ready
    bool waitUntilIdle(uint32_t timeout_ms = 30000);

    // EPD initialization sequence for Spectra-6
    void initEPD();

    // Refresh/update the display
    void refresh();

    // Flag to track initialization state
    bool _initialized;
};

#endif // DISPLAY_DRIVER_H
