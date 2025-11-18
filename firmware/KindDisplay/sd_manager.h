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

    // Load RAW7 image from SD card (cached file)
    // Returns allocated buffer (caller must free)
    uint8_t* loadRAW7(size_t& size);

    // Load RAW7 image from specific file path
    // Returns allocated buffer (caller must free)
    uint8_t* loadRAW7FromFile(const char* filepath, size_t& size);

    // Check if cached image exists
    bool hasCachedImage();

    // Stream cached RAW7 image without allocating
    typedef bool (*StreamCallback)(const uint8_t* chunk, size_t size, void* userData);
    bool streamCachedRAW7(StreamCallback callback, void* userData);

    // Incrementally save a RAW7 download to cache (used for streaming)
    bool beginCacheStream();
    bool appendCacheStream(const uint8_t* data, size_t size);
    void finishCacheStream(bool success);

    // Check if a specific file exists
    bool fileExists(const char* filepath);

    // Get SD card info
    void printCardInfo();

private:
    bool _initialized;
    uint8_t _csPin;
    File _cacheStream;
    size_t _cacheBytes;
};

#endif // SD_MANAGER_H
