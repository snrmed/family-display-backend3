#ifndef FLASH_CACHE_H
#define FLASH_CACHE_H

#include <Arduino.h>
#include <FS.h>
#include <SPIFFS.h>
#include "config.h"

// ============================================================
// Flash Cache Manager (using SPIFFS)
// ============================================================
// Handles flash-based image caching using SPIFFS
// - Stream downloads directly to flash
// - Stream reads from flash for display
// - No large RAM buffers needed (uses 4KB chunks)
// ============================================================

class FlashCache {
public:
    FlashCache();

    // Initialize flash filesystem
    bool begin();

    // Download RAW7 image directly to flash cache using streaming
    // Uses RAW7Decoder's streamImage() to avoid large allocations
    bool downloadRaw7ToCache(class RAW7Decoder& decoder,
                            const char* backendUrl,
                            const char* deviceName);

    // Download RAW7 via background reroll (uses cached data, new background only)
    // Uses RAW7Decoder's streamBackgroundReroll() to avoid external API calls
    bool downloadRaw7ViaReroll(class RAW7Decoder& decoder,
                               const char* backendUrl,
                               const char* deviceName);

    // Stream RAW7 data from cache file in chunks
    // Callback is called with chunks of data as they are read
    typedef void (*StreamCallback)(const uint8_t* chunk, size_t size, void* userData);
    bool streamRaw7FromCache(StreamCallback callback, void* userData);

    // Stream RAW7 data from specific file in chunks
    bool streamRaw7FromFile(const char* filepath, StreamCallback callback, void* userData);

    // Check if cached image exists
    bool hasCachedImage();

    // Check if flash cache is available
    bool isAvailable();

    // Get flash info
    void printFlashInfo();

private:
    bool _initialized;
};

#endif // FLASH_CACHE_H
