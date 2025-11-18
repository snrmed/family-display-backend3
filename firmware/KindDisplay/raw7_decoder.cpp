#include "raw7_decoder.h"
#include "memory_utils.h"

RAW7Decoder::RAW7Decoder() {
}

RAW7Decoder::~RAW7Decoder() {
    _http.end();
}

uint8_t* RAW7Decoder::fetchImage(const char* backendUrl, const char* deviceName, size_t& actualSize) {
    actualSize = 0;

    // Build full URL with device name
    String url = String(backendUrl) + "/v1/raw7?device=" + String(deviceName);
    DEBUG_PRINTF("RAW7: Fetching from %s\n", url.c_str());

    // Check available heap before allocation
    DEBUG_PRINTF("RAW7: Free heap before allocation: %d bytes\n", ESP.getFreeHeap());
    DEBUG_PRINTF("RAW7: Largest free block: %d bytes\n", ESP.getMaxAllocHeap());
    DEBUG_PRINTF("RAW7: Need to allocate: %d bytes\n", RAW7_SIZE);

    // Allocate buffer for RAW7 image
    uint8_t* buffer = allocateRaw7Buffer("RAW7 download");
    if (!buffer) {
        DEBUG_PRINTLN("RAW7: ERROR - Memory allocation failed");
        DEBUG_PRINTF("RAW7: Free heap: %d bytes (insufficient for %d bytes)\n",
                     ESP.getFreeHeap(), RAW7_SIZE);
        return nullptr;
    }

    DEBUG_PRINTF("RAW7: Buffer allocated successfully at 0x%08X\n", (uint32_t)buffer);

    // Start HTTP connection
    _http.begin(url);
    _http.setTimeout(HTTP_TIMEOUT);

    int httpCode = _http.GET();

    if (httpCode != HTTP_CODE_OK) {
        DEBUG_PRINTF("RAW7: HTTP error: %d\n", httpCode);
        free(buffer);
        _http.end();
        return nullptr;
    }

    // Get content length
    int contentLength = _http.getSize();
    DEBUG_PRINTF("RAW7: Content length: %d bytes\n", contentLength);

    if (contentLength != RAW7_SIZE) {
        DEBUG_PRINTF("RAW7: WARNING - Unexpected size (expected %d)\n", RAW7_SIZE);
    }

    // Read response data
    WiFiClient* stream = _http.getStreamPtr();
    size_t bytesRead = 0;

    while (_http.connected() && bytesRead < RAW7_SIZE) {
        size_t available = stream->available();
        if (available) {
            size_t toRead = min(available, RAW7_SIZE - bytesRead);
            int read = stream->readBytes(buffer + bytesRead, toRead);
            if (read > 0) {
                bytesRead += read;
                if (bytesRead % 10000 == 0) {
                    DEBUG_PRINTF("RAW7: Downloaded %d / %d bytes\n", bytesRead, RAW7_SIZE);
                }
            }
        } else {
            delay(1);
        }
    }

    _http.end();

    actualSize = bytesRead;
    DEBUG_PRINTF("RAW7: Download complete - %d bytes\n", bytesRead);

    if (bytesRead == RAW7_SIZE) {
        return buffer;
    } else {
        DEBUG_PRINTLN("RAW7: ERROR - Incomplete download");
        free(buffer);
        return nullptr;
    }
}

bool RAW7Decoder::streamImage(const char* backendUrl, ChunkCallback callback, void* userData) {
    if (!callback) {
        DEBUG_PRINTLN("RAW7: ERROR - No callback provided");
        return false;
    }

    String url = String(backendUrl) + String(RAW7_ENDPOINT);
    DEBUG_PRINTF("RAW7: Streaming from %s\n", url.c_str());

    _http.begin(url);
    _http.setTimeout(HTTP_TIMEOUT);

    int httpCode = _http.GET();

    if (httpCode != HTTP_CODE_OK) {
        DEBUG_PRINTF("RAW7: HTTP error: %d\n", httpCode);
        _http.end();
        return false;
    }

    WiFiClient* stream = _http.getStreamPtr();
    uint8_t buffer[HTTP_BUFFER_SIZE];
    size_t totalRead = 0;

    while (_http.connected() && totalRead < RAW7_SIZE) {
        size_t available = stream->available();
        if (available) {
            size_t toRead = min(available, sizeof(buffer));
            toRead = min(toRead, RAW7_SIZE - totalRead);

            int read = stream->readBytes(buffer, toRead);
            if (read > 0) {
                callback(buffer, read, userData);
                totalRead += read;

                if (totalRead % 10000 == 0) {
                    DEBUG_PRINTF("RAW7: Streamed %d / %d bytes\n", totalRead, RAW7_SIZE);
                }
            }
        } else {
            delay(1);
        }
    }

    _http.end();

    DEBUG_PRINTF("RAW7: Stream complete - %d bytes\n", totalRead);
    return (totalRead == RAW7_SIZE);
}

bool RAW7Decoder::triggerBackgroundReroll(const char* backendUrl, const char* deviceName) {
    String url = String(backendUrl) + "/v1/frame_bg_reroll?device=" + String(deviceName);
    DEBUG_PRINTF("RAW7: Triggering background reroll at %s\n", url.c_str());

    _http.begin(url);
    _http.setTimeout(HTTP_TIMEOUT);

    int httpCode = _http.GET();
    _http.end();

    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_NO_CONTENT) {
        DEBUG_PRINTLN("RAW7: Background reroll successful");
        return true;
    } else {
        DEBUG_PRINTF("RAW7: Background reroll failed: %d\n", httpCode);
        return false;
    }
}
