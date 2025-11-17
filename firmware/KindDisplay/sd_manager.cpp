#include "sd_manager.h"

SDManager::SDManager() : _initialized(false), _csPin(PIN_SD_CS) {
}

bool SDManager::begin() {
    DEBUG_PRINTLN("SD: Initializing SD card");

    // Re-initialize SPI with SD card parameters
    // Even though display uses same pins, SD.begin() needs SPI configured
    SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, PIN_SD_CS);

    if (!SD.begin(_csPin, SPI, 4000000)) {  // 4MHz for compatibility
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
    uint8_t* buffer = (uint8_t*)malloc(fileSize);
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
