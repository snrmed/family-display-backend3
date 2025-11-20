#include "flash_cache.h"
#include "raw7_decoder.h"
#include "http_task.h"

// Flash cache file path
#define FLASH_CACHE_FILE "/last.raw7"

FlashCache::FlashCache() : _initialized(false) {
}

bool FlashCache::begin() {
    DEBUG_PRINTLN("Flash: Initializing SPIFFS");

    if (!SPIFFS.begin(true)) {  // true = format on failure
        DEBUG_PRINTLN("Flash: SPIFFS mount failed");
        _initialized = false;
        return false;
    }

    _initialized = true;
    DEBUG_PRINTLN("Flash: SPIFFS initialized successfully");
    printFlashInfo();

    return true;
}

bool FlashCache::isAvailable() {
    return _initialized;
}

bool FlashCache::hasCachedImage() {
    if (!_initialized) {
        return false;
    }

    return SPIFFS.exists(FLASH_CACHE_FILE);
}

void FlashCache::printFlashInfo() {
    if (!_initialized) {
        return;
    }

    size_t totalBytes = SPIFFS.totalBytes();
    size_t usedBytes = SPIFFS.usedBytes();

    DEBUG_PRINTF("Flash: Total: %d bytes, Used: %d bytes, Free: %d bytes\n",
                 totalBytes, usedBytes, totalBytes - usedBytes);
}

// ============================================================
// Streaming Implementation - No Large RAM Buffers
// ============================================================

// Helper structure for download callback
struct DownloadContext {
    File* file;
    size_t totalWritten;
};

// Callback for RAW7Decoder::streamImage()
static void downloadChunkCallback(const uint8_t* chunk, size_t size, void* userData) {
    DownloadContext* ctx = (DownloadContext*)userData;
    if (ctx && ctx->file) {
        size_t written = ctx->file->write(chunk, size);
        ctx->totalWritten += written;

        if (ctx->totalWritten % 20000 == 0) {
            DEBUG_PRINTF("Flash: Downloaded %d bytes to cache\n", ctx->totalWritten);
        }
    }
}

bool FlashCache::downloadRaw7ToCache(RAW7Decoder& decoder,
                                    const char* backendUrl,
                                    const char* deviceName) {
    if (!_initialized) {
        DEBUG_PRINTLN("Flash: Not initialized");
        return false;
    }

    DEBUG_PRINTLN("Flash: Streaming RAW7 download directly to cache");
    DEBUG_PRINTLN("Flash: Running HTTPS in dedicated task with 64KB stack to avoid overflow");

    // Use temporary file for safe cache update
    const char* tempFile = "/last.raw7.tmp";

    // Remove temp file if it exists from previous failed attempt
    if (SPIFFS.exists(tempFile)) {
        SPIFFS.remove(tempFile);
    }

    // Run the HTTPS download in a dedicated task with large stack
    // This avoids stack overflow during TLS handshake on ESP32 without PSRAM
    bool downloadSuccess = HttpTask::runWithLargeStack([&]() -> bool {
        // Open temp file for writing
        File cacheFile = SPIFFS.open(tempFile, FILE_WRITE);
        if (!cacheFile) {
            DEBUG_PRINTLN("Flash: Failed to open temp file for writing");
            return false;
        }

        // Set up download context
        DownloadContext ctx;
        ctx.file = &cacheFile;
        ctx.totalWritten = 0;

        // Execute HTTPS download (TLS handshake happens here)
        bool success = decoder.streamImage(backendUrl, deviceName, downloadChunkCallback, &ctx);

        cacheFile.close();

        if (success && ctx.totalWritten == RAW7_SIZE) {
            DEBUG_PRINTF("Flash: Successfully downloaded %d bytes to temp file\n", ctx.totalWritten);
            return true;
        } else {
            DEBUG_PRINTF("Flash: Download incomplete - wrote %d of %d bytes\n",
                        ctx.totalWritten, RAW7_SIZE);
            SPIFFS.remove(tempFile);  // Remove incomplete temp file
            return false;
        }
    });

    if (!downloadSuccess) {
        DEBUG_PRINTLN("Flash: Download task failed");
        return false;
    }

    // Atomic replace: remove old cache and rename temp to cache
    if (SPIFFS.exists(FLASH_CACHE_FILE)) {
        SPIFFS.remove(FLASH_CACHE_FILE);
    }

    if (SPIFFS.rename(tempFile, FLASH_CACHE_FILE)) {
        DEBUG_PRINTLN("Flash: Cache updated successfully");
        return true;
    } else {
        DEBUG_PRINTLN("Flash: Failed to rename temp file to cache");
        SPIFFS.remove(tempFile);
        return false;
    }
}

bool FlashCache::downloadRaw7ViaReroll(RAW7Decoder& decoder,
                                       const char* backendUrl,
                                       const char* deviceName) {
    if (!_initialized) {
        DEBUG_PRINTLN("Flash: Not initialized");
        return false;
    }

    DEBUG_PRINTLN("Flash: Streaming background reroll download to cache");
    DEBUG_PRINTLN("Flash: Running HTTPS in dedicated task with 64KB stack to avoid overflow");

    // Use temporary file for safe cache update
    const char* tempFile = "/last.raw7.tmp";

    // Remove temp file if it exists from previous failed attempt
    if (SPIFFS.exists(tempFile)) {
        SPIFFS.remove(tempFile);
    }

    // Run the HTTPS download in a dedicated task with large stack
    // This avoids stack overflow during TLS handshake on ESP32 without PSRAM
    bool downloadSuccess = HttpTask::runWithLargeStack([&]() -> bool {
        // Open temp file for writing
        File cacheFile = SPIFFS.open(tempFile, FILE_WRITE);
        if (!cacheFile) {
            DEBUG_PRINTLN("Flash: Failed to open temp file for writing");
            return false;
        }

        // Set up download context
        DownloadContext ctx;
        ctx.file = &cacheFile;
        ctx.totalWritten = 0;

        // Execute HTTPS background reroll (TLS handshake happens here)
        bool success = decoder.streamBackgroundReroll(backendUrl, deviceName, downloadChunkCallback, &ctx);

        cacheFile.close();

        if (success && ctx.totalWritten == RAW7_SIZE) {
            DEBUG_PRINTF("Flash: Successfully downloaded %d bytes via reroll\n", ctx.totalWritten);
            return true;
        } else {
            DEBUG_PRINTF("Flash: Reroll incomplete - wrote %d of %d bytes\n",
                        ctx.totalWritten, RAW7_SIZE);
            SPIFFS.remove(tempFile);  // Remove incomplete temp file
            return false;
        }
    });

    if (!downloadSuccess) {
        DEBUG_PRINTLN("Flash: Reroll download task failed");
        return false;
    }

    // Atomic replace: remove old cache and rename temp to cache
    if (SPIFFS.exists(FLASH_CACHE_FILE)) {
        SPIFFS.remove(FLASH_CACHE_FILE);
    }

    if (SPIFFS.rename(tempFile, FLASH_CACHE_FILE)) {
        DEBUG_PRINTLN("Flash: Cache updated via reroll successfully");
        return true;
    } else {
        DEBUG_PRINTLN("Flash: Failed to rename temp file to cache");
        SPIFFS.remove(tempFile);
        return false;
    }
}

bool FlashCache::streamRaw7FromCache(StreamCallback callback, void* userData) {
    return streamRaw7FromFile(FLASH_CACHE_FILE, callback, userData);
}

bool FlashCache::streamRaw7FromFile(const char* filepath, StreamCallback callback, void* userData) {
    if (!_initialized) {
        DEBUG_PRINTLN("Flash: Not initialized");
        return false;
    }

    if (!callback) {
        DEBUG_PRINTLN("Flash: No callback provided");
        return false;
    }

    if (!SPIFFS.exists(filepath)) {
        DEBUG_PRINTF("Flash: File not found: %s\n", filepath);
        return false;
    }

    DEBUG_PRINTF("Flash: Streaming RAW7 from %s\n", filepath);

    File file = SPIFFS.open(filepath, FILE_READ);
    if (!file) {
        DEBUG_PRINTF("Flash: Failed to open file: %s\n", filepath);
        return false;
    }

    size_t fileSize = file.size();
    if (fileSize != RAW7_SIZE) {
        DEBUG_PRINTF("Flash: Invalid file size: %d (expected %d)\n", fileSize, RAW7_SIZE);
        file.close();
        return false;
    }

    // Stream file in chunks
    uint8_t buffer[HTTP_BUFFER_SIZE];
    size_t totalRead = 0;

    while (totalRead < fileSize) {
        size_t toRead = min((size_t)HTTP_BUFFER_SIZE, fileSize - totalRead);
        size_t bytesRead = file.read(buffer, toRead);

        if (bytesRead > 0) {
            callback(buffer, bytesRead, userData);
            totalRead += bytesRead;

            if (totalRead % 20000 == 0) {
                DEBUG_PRINTF("Flash: Streamed %d / %d bytes\n", totalRead, fileSize);
            }
        } else {
            DEBUG_PRINTLN("Flash: Read error during streaming");
            file.close();
            return false;
        }
    }

    file.close();
    DEBUG_PRINTF("Flash: Stream complete - %d bytes\n", totalRead);
    return (totalRead == fileSize);
}
