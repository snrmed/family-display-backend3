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

    // Check if a specific file exists
    bool fileExists(const char* filepath);

    // Get SD card info
    void printCardInfo();

    // ============================================================
    // NEW: Streaming API - No large RAM buffers needed
    // ============================================================

    // Download RAW7 image directly to SD cache using streaming
    // Uses RAW7Decoder's streamImage() to avoid large allocations
    bool downloadRaw7ToCache(class RAW7Decoder& decoder,
                            const char* backendUrl,
                            const char* deviceName);

    // Stream RAW7 data from cache file in chunks
    // Callback is called with chunks of data as they are read
    typedef void (*StreamCallback)(const uint8_t* chunk, size_t size, void* userData);
    bool streamRaw7FromCache(StreamCallback callback, void* userData);

    // Stream RAW7 data from specific file in chunks
    bool streamRaw7FromFile(const char* filepath, StreamCallback callback, void* userData);

private:
    bool _initialized;
    uint8_t _csPin;
};

#endif // SD_MANAGER_H
