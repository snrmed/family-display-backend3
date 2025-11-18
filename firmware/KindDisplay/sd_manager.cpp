#include "sd_manager.h"
#include "memory_utils.h"

static const char* SD_CACHE_TEMP_FILE = "/last.raw7.tmp";

SDManager::SDManager()
    : _initialized(false),
      _csPin(PIN_SD_CS),
      _cacheBytes(0) {
}

bool SDManager::begin() {
    DEBUG_PRINTLN("SD: Initializing SD card");

    // Initialize SPI bus with all pins (SD needs MISO, display doesn't but shares bus)
    SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, -1);  // SS=-1, we control CS manually

    // Set up CS pin for SD card
    pinMode(_csPin, OUTPUT);
    digitalWrite(_csPin, HIGH);  // CS idle high

    // Initialize SD card library with retries at lower clock speeds
    const uint32_t frequencies[] = {8000000, 4000000, 2000000, 1000000};
    bool mounted = false;
    for (uint32_t freq : frequencies) {
        if (SD.begin(_csPin, SPI, freq)) {
            mounted = true;
            DEBUG_PRINTF("SD: Initialized at %u Hz\n", freq);
            break;
        }
        DEBUG_PRINTF("SD: Init failed at %u Hz - retrying slower\n", freq);
        delay(20);
    }

    if (!mounted) {
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

bool SDManager::streamCachedRAW7(StreamCallback callback, void* userData) {
    if (!_initialized || !callback) {
        return false;
    }

    if (!hasCachedImage()) {
        DEBUG_PRINTLN("SD: No cached RAW7 image to stream");
        return false;
    }

    File file = SD.open(SD_CACHE_FILE, FILE_READ);
    if (!file) {
        DEBUG_PRINTLN("SD: Failed to open cached file for streaming");
        return false;
    }

    uint8_t buffer[HTTP_BUFFER_SIZE];
    size_t totalRead = 0;
    bool ok = true;

    while (totalRead < RAW7_SIZE && ok) {
        size_t toRead = min(sizeof(buffer), RAW7_SIZE - totalRead);
        int bytes = file.read(buffer, toRead);
        if (bytes <= 0) {
            ok = false;
            break;
        }

        totalRead += bytes;
        if (!callback(buffer, bytes, userData)) {
            ok = false;
            break;
        }
    }

    file.close();

    if (!ok || totalRead != RAW7_SIZE) {
        DEBUG_PRINTLN("SD: Streaming cached RAW7 failed");
        return false;
    }

    DEBUG_PRINTLN("SD: Cached RAW7 streamed successfully");
    return true;
}

bool SDManager::beginCacheStream() {
    if (!_initialized) {
        return false;
    }

    if (_cacheStream) {
        _cacheStream.close();
    }

    SD.remove(SD_CACHE_TEMP_FILE);
    _cacheStream = SD.open(SD_CACHE_TEMP_FILE, FILE_WRITE);
    _cacheBytes = 0;

    if (!_cacheStream) {
        DEBUG_PRINTLN("SD: Failed to open temp cache file for streaming write");
        return false;
    }

    DEBUG_PRINTLN("SD: Began streaming write to cache");
    return true;
}

bool SDManager::appendCacheStream(const uint8_t* data, size_t size) {
    if (!_cacheStream || data == nullptr || size == 0) {
        return false;
    }

    size_t written = _cacheStream.write(data, size);
    if (written != size) {
        DEBUG_PRINTF("SD: Stream write error - wrote %d of %d bytes\n",
                     written, size);
        _cacheStream.close();
        return false;
    }

    _cacheBytes += written;
    return true;
}

void SDManager::finishCacheStream(bool success) {
    if (_cacheStream) {
        _cacheStream.close();
    }

    if (!success || _cacheBytes != RAW7_SIZE) {
        DEBUG_PRINTLN("SD: Stream cache incomplete - removing temp file");
        SD.remove(SD_CACHE_TEMP_FILE);
    } else {
        DEBUG_PRINTF("SD: Stream cache saved (%d bytes)\n",
                     static_cast<int>(_cacheBytes));
        SD.remove(SD_CACHE_FILE);
        SD.rename(SD_CACHE_TEMP_FILE, SD_CACHE_FILE);
    }

    _cacheBytes = 0;
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
