#include "sd_manager.h"
#include "memory_utils.h"
#include "raw7_decoder.h"

SDManager::SDManager() : _initialized(false), _csPin(PIN_SD_CS) {
}

bool SDManager::begin() {
    DEBUG_PRINTLN("SD: Initializing SD card");

    // Initialize SPI bus with all pins (SD needs MISO, display doesn't but shares bus)
    SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, -1);  // SS=-1, we control CS manually

    // Set up CS pin for SD card
    pinMode(_csPin, OUTPUT);
    digitalWrite(_csPin, HIGH);  // CS idle high

    // Small delay for SD card stabilization after SPI init
    delay(100);

    // Initialize SD card library with slower speed for better compatibility
    if (!SD.begin(_csPin, SPI, 400000)) {  // 400kHz for initialization (slower = more reliable)
        DEBUG_PRINTLN("SD: Card mount failed or not present");
        _initialized = false;
        return false;
    }

    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        DEBUG_PRINTLN("SD: No SD card attached");
        _initialized = false;
        return false;
    }

    _initialized = true;
    DEBUG_PRINTLN("SD: Card initialized successfully");
    printCardInfo();

    return true;
}

bool SDManager::isAvailable() {
    return _initialized;
}

bool SDManager::saveRAW7(const uint8_t* buffer, size_t size) {
    if (!_initialized) {
        DEBUG_PRINTLN("SD: Not initialized");
        return false;
    }

    if (size != RAW7_SIZE) {
        DEBUG_PRINTF("SD: Invalid size: %d (expected %d)\n", size, RAW7_SIZE);
        return false;
    }

    DEBUG_PRINTLN("SD: Saving RAW7 image to cache");

    SD.remove(SD_CACHE_FILE);
    File file = SD.open(SD_CACHE_FILE, FILE_WRITE);
    if (!file) {
        DEBUG_PRINTLN("SD: Failed to open file for writing");
        return false;
    }

    size_t written = file.write(buffer, size);
    file.close();

    if (written == size) {
        DEBUG_PRINTF("SD: Successfully saved %d bytes\n", written);
        return true;
    } else {
        DEBUG_PRINTF("SD: Write error - wrote %d of %d bytes\n", written, size);
        return false;
    }
}

uint8_t* SDManager::loadRAW7(size_t& size) {
    size = 0;

    if (!_initialized) {
        DEBUG_PRINTLN("SD: Not initialized");
        return nullptr;
    }

    if (!hasCachedImage()) {
        DEBUG_PRINTLN("SD: No cached image found");
        return nullptr;
    }

    DEBUG_PRINTLN("SD: Loading cached RAW7 image");

    File file = SD.open(SD_CACHE_FILE, FILE_READ);
    if (!file) {
        DEBUG_PRINTLN("SD: Failed to open cached file");
        return nullptr;
    }

    size_t fileSize = file.size();
    DEBUG_PRINTF("SD: Cached file size: %d bytes\n", fileSize);

    if (fileSize != RAW7_SIZE) {
        DEBUG_PRINTF("SD: Invalid cached file size (expected %d)\n", RAW7_SIZE);
        file.close();
        return nullptr;
    }

    // Allocate buffer
    uint8_t* buffer = allocateRaw7Buffer("SD cache load");
    if (!buffer) {
        DEBUG_PRINTLN("SD: Memory allocation failed");
        file.close();
        return nullptr;
    }

    // Read file
    size_t bytesRead = file.read(buffer, fileSize);
    file.close();

    if (bytesRead == fileSize) {
        size = bytesRead;
        DEBUG_PRINTF("SD: Successfully loaded %d bytes\n", bytesRead);
        return buffer;
    } else {
        DEBUG_PRINTF("SD: Read error - read %d of %d bytes\n", bytesRead, fileSize);
        free(buffer);
        return nullptr;
    }
}

bool SDManager::hasCachedImage() {
    if (!_initialized) {
        return false;
    }

    return SD.exists(SD_CACHE_FILE);
}

uint8_t* SDManager::loadRAW7FromFile(const char* filepath, size_t& size) {
    size = 0;

    if (!_initialized) {
        DEBUG_PRINTLN("SD: Not initialized");
        return nullptr;
    }

    if (!SD.exists(filepath)) {
        DEBUG_PRINTF("SD: File not found: %s\n", filepath);
        return nullptr;
    }

    DEBUG_PRINTF("SD: Loading RAW7 from %s\n", filepath);

    File file = SD.open(filepath, FILE_READ);
    if (!file) {
        DEBUG_PRINTF("SD: Failed to open file: %s\n", filepath);
        return nullptr;
    }

    size_t fileSize = file.size();
    DEBUG_PRINTF("SD: File size: %d bytes\n", fileSize);

    if (fileSize != RAW7_SIZE) {
        DEBUG_PRINTF("SD: Invalid file size (expected %d)\n", RAW7_SIZE);
        file.close();
        return nullptr;
    }

    // Allocate buffer
    uint8_t* buffer = allocateRaw7Buffer("SD file load");
    if (!buffer) {
        DEBUG_PRINTLN("SD: Memory allocation failed");
        file.close();
        return nullptr;
    }

    // Read file
    size_t bytesRead = file.read(buffer, fileSize);
    file.close();

    if (bytesRead == fileSize) {
        size = bytesRead;
        DEBUG_PRINTF("SD: Successfully loaded %d bytes\n", bytesRead);
        return buffer;
    } else {
        DEBUG_PRINTF("SD: Read error - read %d of %d bytes\n", bytesRead, fileSize);
        free(buffer);
        return nullptr;
    }
}

bool SDManager::fileExists(const char* filepath) {
    if (!_initialized) {
        return false;
    }

    return SD.exists(filepath);
}

void SDManager::printCardInfo() {
    if (!_initialized) {
        return;
    }

    uint8_t cardType = SD.cardType();
    DEBUG_PRINT("SD: Card Type: ");

    switch (cardType) {
        case CARD_MMC:
            DEBUG_PRINTLN("MMC");
            break;
        case CARD_SD:
            DEBUG_PRINTLN("SDSC");
            break;
        case CARD_SDHC:
            DEBUG_PRINTLN("SDHC");
            break;
        default:
            DEBUG_PRINTLN("UNKNOWN");
    }

    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    DEBUG_PRINTF("SD: Size: %llu MB\n", cardSize);

    uint64_t totalBytes = SD.totalBytes() / (1024 * 1024);
    uint64_t usedBytes = SD.usedBytes() / (1024 * 1024);
    DEBUG_PRINTF("SD: Total: %llu MB, Used: %llu MB\n", totalBytes, usedBytes);
}

// ============================================================
// NEW: Streaming Implementation - No Large RAM Buffers
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
            DEBUG_PRINTF("SD: Downloaded %d bytes to cache\n", ctx->totalWritten);
        }
    }
}

bool SDManager::downloadRaw7ToCache(RAW7Decoder& decoder,
                                   const char* backendUrl,
                                   const char* deviceName) {
    if (!_initialized) {
        DEBUG_PRINTLN("SD: Not initialized");
        return false;
    }

    DEBUG_PRINTLN("SD: Streaming RAW7 download directly to cache");
    DEBUG_PRINTF("SD: Note - using hardcoded device from RAW7_ENDPOINT, ignoring '%s'\n", deviceName);

    // Use temporary file for safe cache update
    const char* tempFile = "/last.raw7.tmp";

    // Remove temp file if it exists from previous failed attempt
    if (SD.exists(tempFile)) {
        SD.remove(tempFile);
    }

    // Open temp file for writing
    File cacheFile = SD.open(tempFile, FILE_WRITE);
    if (!cacheFile) {
        DEBUG_PRINTLN("SD: Failed to open temp file for writing");
        return false;
    }

    // Set up download context
    DownloadContext ctx;
    ctx.file = &cacheFile;
    ctx.totalWritten = 0;

    // FIX: Pass only base URL - streamImage() appends RAW7_ENDPOINT internally
    bool success = decoder.streamImage(backendUrl, downloadChunkCallback, &ctx);

    cacheFile.close();

    if (success && ctx.totalWritten == RAW7_SIZE) {
        DEBUG_PRINTF("SD: Successfully downloaded %d bytes to temp file\n", ctx.totalWritten);

        // Atomic replace: remove old cache and rename temp to cache
        if (SD.exists(SD_CACHE_FILE)) {
            SD.remove(SD_CACHE_FILE);
        }

        if (SD.rename(tempFile, SD_CACHE_FILE)) {
            DEBUG_PRINTLN("SD: Cache updated successfully");
            return true;
        } else {
            DEBUG_PRINTLN("SD: Failed to rename temp file to cache");
            SD.remove(tempFile);
            return false;
        }
    } else {
        DEBUG_PRINTF("SD: Download incomplete - wrote %d of %d bytes\n",
                    ctx.totalWritten, RAW7_SIZE);
        SD.remove(tempFile);  // Remove incomplete temp file
        return false;
    }
}

bool SDManager::streamRaw7FromCache(StreamCallback callback, void* userData) {
    return streamRaw7FromFile(SD_CACHE_FILE, callback, userData);
}

bool SDManager::streamRaw7FromFile(const char* filepath, StreamCallback callback, void* userData) {
    if (!_initialized) {
        DEBUG_PRINTLN("SD: Not initialized");
        return false;
    }

    if (!callback) {
        DEBUG_PRINTLN("SD: No callback provided");
        return false;
    }

    if (!SD.exists(filepath)) {
        DEBUG_PRINTF("SD: File not found: %s\n", filepath);
        return false;
    }

    DEBUG_PRINTF("SD: Streaming RAW7 from %s\n", filepath);

    File file = SD.open(filepath, FILE_READ);
    if (!file) {
        DEBUG_PRINTF("SD: Failed to open file: %s\n", filepath);
        return false;
    }

    size_t fileSize = file.size();
    if (fileSize != RAW7_SIZE) {
        DEBUG_PRINTF("SD: Invalid file size: %d (expected %d)\n", fileSize, RAW7_SIZE);
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
                DEBUG_PRINTF("SD: Streamed %d / %d bytes\n", totalRead, fileSize);
            }
        } else {
            DEBUG_PRINTLN("SD: Read error during streaming");
            file.close();
            return false;
        }
    }

    file.close();
    DEBUG_PRINTF("SD: Stream complete - %d bytes\n", totalRead);
    return (totalRead == fileSize);
}
