#include "sd_manager.h"
#include "memory_utils.h"

SDManager::SDManager() : _initialized(false), _csPin(PIN_SD_CS) {
}

bool SDManager::begin() {
    DEBUG_PRINTLN("SD: Initializing SD card");

    // Step 1: Hardware diagnostics - check pin connections
    if (!checkHardwareConnections()) {
        DEBUG_PRINTLN("SD: Hardware connection issues detected");
        DEBUG_PRINTLN("SD: Check wiring and power supply");
    }

    // Step 2: Initialize SPI bus with all pins
    SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, -1);  // SS=-1, we control CS manually

    // Step 3: Set up CS pin for SD card
    pinMode(_csPin, OUTPUT);
    digitalWrite(_csPin, HIGH);  // CS idle high initially

    // Step 4: Power-up sequence for SD card
    // SD cards need specific power-up timing and CS toggling
    DEBUG_PRINTLN("SD: Starting power-up sequence");

    // Keep CS high and send 80+ clock pulses for card power-up
    digitalWrite(_csPin, HIGH);
    delay(10);  // Minimum 1ms power-up time

    // Send 80 clock pulses with CS high (10 bytes @ 8 bits each)
    SPI.beginTransaction(SPISettings(400000, MSBFIRST, SPI_MODE0));
    for (int i = 0; i < 10; i++) {
        SPI.transfer(0xFF);
    }
    SPI.endTransaction();

    // Additional stabilization delay
    delay(100);

    // Step 5: Try multiple initialization strategies
    const int MAX_ATTEMPTS = 5;
    const uint32_t speeds[] = {200000, 250000, 300000, 400000, 400000}; // Start even slower
    const uint16_t delays[] = {500, 400, 300, 200, 100}; // Longer delays for earlier attempts

    for (int attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
        DEBUG_PRINTF("SD: Attempt %d/%d at %d Hz\n", attempt + 1, MAX_ATTEMPTS, speeds[attempt]);

        // Power cycle CS pin before each attempt
        digitalWrite(_csPin, LOW);
        delay(10);
        digitalWrite(_csPin, HIGH);
        delay(delays[attempt]);

        // Try to initialize SD card
        if (SD.begin(_csPin, SPI, speeds[attempt])) {
            // Check if card is actually present
            uint8_t cardType = SD.cardType();
            if (cardType != CARD_NONE) {
                _initialized = true;
                DEBUG_PRINTLN("SD: Card initialized successfully");
                printCardInfo();
                return true;
            } else {
                DEBUG_PRINTLN("SD: No card detected after init");
            }
        }

        // If not the last attempt, wait before retrying
        if (attempt < MAX_ATTEMPTS - 1) {
            DEBUG_PRINTLN("SD: Retrying with different settings...");
            delay(200);
        }
    }

    // All attempts failed
    DEBUG_PRINTLN("SD: Card mount failed after all attempts");
    DEBUG_PRINTLN("SD: Possible issues:");
    DEBUG_PRINTLN("SD:   - Card not inserted or defective");
    DEBUG_PRINTLN("SD:   - Poor wiring/connection (check breadboard)");
    DEBUG_PRINTLN("SD:   - Missing pull-up resistor on MISO");
    DEBUG_PRINTLN("SD:   - Insufficient power supply");
    DEBUG_PRINTLN("SD:   - Card needs reformatting");

    _initialized = false;
    return false;
}

bool SDManager::checkHardwareConnections() {
    // Test 1: Check if pins can be controlled
    DEBUG_PRINTLN("SD: Running hardware diagnostics...");

    // Test CS pin
    pinMode(_csPin, OUTPUT);
    digitalWrite(_csPin, HIGH);
    delay(1);
    int csHigh = digitalRead(_csPin);
    digitalWrite(_csPin, LOW);
    delay(1);
    int csLow = digitalRead(_csPin);
    digitalWrite(_csPin, HIGH);

    if (csHigh != HIGH || csLow != LOW) {
        DEBUG_PRINTF("SD: CS pin test failed (high=%d, low=%d)\n", csHigh, csLow);
        return false;
    }
    DEBUG_PRINTLN("SD: CS pin OK");

    // Test 2: Check MISO pin (should have pull-up or float high when no card)
    pinMode(PIN_SD_MISO, INPUT);
    delay(10);
    int misoState = digitalRead(PIN_SD_MISO);
    DEBUG_PRINTF("SD: MISO pin state: %d (should be HIGH if pull-up present)\n", misoState);

    if (misoState == LOW) {
        DEBUG_PRINTLN("SD: WARNING - MISO is LOW, may need external pull-up resistor");
        DEBUG_PRINTLN("SD:           Try adding 10K-47K resistor from MISO to 3.3V");
    }

    // Test 3: Verify SPI pins are not shorted
    pinMode(PIN_SD_MOSI, OUTPUT);
    pinMode(PIN_SD_SCK, OUTPUT);
    digitalWrite(PIN_SD_MOSI, HIGH);
    digitalWrite(PIN_SD_SCK, LOW);
    delay(1);

    int mosiState = digitalRead(PIN_SD_MOSI);
    int sckState = digitalRead(PIN_SD_SCK);

    if (mosiState != HIGH || sckState != LOW) {
        DEBUG_PRINTF("SD: SPI pin test failed (MOSI=%d, SCK=%d)\n", mosiState, sckState);
        return false;
    }
    DEBUG_PRINTLN("SD: SPI pins OK");

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
