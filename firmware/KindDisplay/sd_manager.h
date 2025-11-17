#ifndef SD_MANAGER_H
#define SD_MANAGER_H

#include <Arduino.h>
#include <SD.h>
#include <SPI.h>
#include "config.h"

// ============================================================
// SD Card Manager
// ============================================================
// Handles SD card operations:
// - Cache last RAW7 image
// - Fallback display if WiFi fails
// - Optional configuration storage
// ============================================================

class SDManager {
public:
    SDManager();

    // Initialize SD card
    bool begin();

    // Check if SD card is available
    bool isAvailable();

    // Save RAW7 image to SD card
    bool saveRAW7(const uint8_t* buffer, size_t size);

    // Load RAW7 image from SD card
    // Returns allocated buffer (caller must free)
    uint8_t* loadRAW7(size_t& size);

    // Check if cached image exists
    bool hasCachedImage();

    // Get SD card info
    void printCardInfo();

private:
    bool _initialized;
    uint8_t _csPin;
};

#endif // SD_MANAGER_H
