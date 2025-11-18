#ifndef RAW7_DECODER_H
#define RAW7_DECODER_H

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include "config.h"

// ============================================================
// RAW7 Image Fetcher and Decoder
// ============================================================
// Handles downloading RAW7 format images from backend
// RAW7 format: 2 pixels per byte (high nibble, low nibble)
// Total size: 800×480 / 2 = 192000 bytes
// ============================================================

class RAW7Decoder {
public:
    RAW7Decoder();
    ~RAW7Decoder();

    // Fetch RAW7 image from backend
    // Returns buffer containing RAW7 data (must be freed by caller)
    // Sets actualSize to the number of bytes received
    uint8_t* fetchImage(const char* backendUrl, const char* deviceName, size_t& actualSize);

    // Fetch a new background (triggers backend reroll)
    bool triggerBackgroundReroll(const char* backendUrl, const char* deviceName);

    // Stream RAW7 directly to callback function (memory efficient)
    // Callback is called with chunks of data as they arrive
    typedef void (*ChunkCallback)(const uint8_t* chunk, size_t size, void* userData);
    bool streamImage(const char* backendUrl,
                     const char* deviceName,
                     ChunkCallback callback,
                     void* userData);

private:
    HTTPClient _http;
};

#endif // RAW7_DECODER_H
