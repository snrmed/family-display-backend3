#include "display_driver.h"

// ============================================================
// EPD Command Definitions (common for ACeP displays)
// ============================================================
#define EPD_CMD_PANEL_SETTING           0x00
#define EPD_CMD_POWER_SETTING           0x01
#define EPD_CMD_POWER_OFF               0x02
#define EPD_CMD_POWER_ON                0x04
#define EPD_CMD_BOOSTER_SOFT_START      0x06
#define EPD_CMD_DEEP_SLEEP              0x07
#define EPD_CMD_DATA_START_TRANSMISSION 0x10
#define EPD_CMD_DISPLAY_REFRESH         0x12
#define EPD_CMD_VCOM_AND_DATA_SETTING   0x50
#define EPD_CMD_TCON_SETTING            0x60
#define EPD_CMD_RESOLUTION_SETTING      0x61
#define EPD_CMD_GET_STATUS              0x71

SpectraDisplay::SpectraDisplay() : _initialized(false) {
}

bool SpectraDisplay::begin() {
    DEBUG_PRINTLN("SpectraDisplay: Initializing...");

    // Configure GPIO pins
    pinMode(PIN_EPD_CS, OUTPUT);
    pinMode(PIN_EPD_RST, OUTPUT);
    pinMode(PIN_EPD_DC, OUTPUT);
    pinMode(PIN_EPD_BUSY, INPUT);

    digitalWrite(PIN_EPD_CS, HIGH);
    digitalWrite(PIN_EPD_DC, HIGH);

    // Initialize SPI bus (safe to call even if SD card already configured it)
    SPI.begin(PIN_EPD_SCK, PIN_SD_MISO, PIN_EPD_MOSI, -1);
    SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));

    // Hardware reset
    reset();

    // Initialize EPD
    initEPD();

    _initialized = true;
    DEBUG_PRINTLN("SpectraDisplay: Initialization complete");
    return true;
}

void SpectraDisplay::reset() {
    DEBUG_PRINTLN("SpectraDisplay: Hardware reset");
    digitalWrite(PIN_EPD_RST, HIGH);
    delay(20);
    digitalWrite(PIN_EPD_RST, LOW);
    delay(2);
    digitalWrite(PIN_EPD_RST, HIGH);
    delay(20);
    waitUntilIdle();
}

void SpectraDisplay::sendCommand(uint8_t command) {
    digitalWrite(PIN_EPD_DC, LOW);
    digitalWrite(PIN_EPD_CS, LOW);
    SPI.transfer(command);
    digitalWrite(PIN_EPD_CS, HIGH);
}

void SpectraDisplay::sendData(uint8_t data) {
    digitalWrite(PIN_EPD_DC, HIGH);
    digitalWrite(PIN_EPD_CS, LOW);
    SPI.transfer(data);
    digitalWrite(PIN_EPD_CS, HIGH);
}

void SpectraDisplay::sendData(const uint8_t* data, size_t len) {
    digitalWrite(PIN_EPD_DC, HIGH);
    digitalWrite(PIN_EPD_CS, LOW);

    // Transfer data in chunks for efficiency
    const size_t chunkSize = 4096;
    for (size_t i = 0; i < len; i += chunkSize) {
        size_t remaining = len - i;
        size_t toSend = (remaining > chunkSize) ? chunkSize : remaining;
        SPI.writeBytes(data + i, toSend);
    }

    digitalWrite(PIN_EPD_CS, HIGH);
}

bool SpectraDisplay::waitUntilIdle(uint32_t timeout_ms) {
    DEBUG_PRINT("SpectraDisplay: Waiting for idle...");
    unsigned long start = millis();

    // BUSY pin is HIGH when busy, LOW when idle
    while (digitalRead(PIN_EPD_BUSY) == HIGH) {
        if (millis() - start > timeout_ms) {
            DEBUG_PRINTLN(" TIMEOUT!");
            return false;
        }
        delay(10);
    }

    DEBUG_PRINTLN(" Ready");
    return true;
}

void SpectraDisplay::initEPD() {
    DEBUG_PRINTLN("SpectraDisplay: Configuring EPD registers");

    // Panel Setting - 7-color mode (ACeP)
    sendCommand(EPD_CMD_PANEL_SETTING);
    sendData(0x0F);  // 7-color mode

    // Resolution Setting (800×480)
    sendCommand(EPD_CMD_RESOLUTION_SETTING);
    sendData(0x03);  // Width high byte (800 = 0x0320)
    sendData(0x20);  // Width low byte
    sendData(0x01);  // Height high byte (480 = 0x01E0)
    sendData(0xE0);  // Height low byte

    // Power Setting
    sendCommand(EPD_CMD_POWER_SETTING);
    sendData(0x07);
    sendData(0x07);
    sendData(0x3F);
    sendData(0x3F);

    // VCOM and Data Interval Setting
    sendCommand(EPD_CMD_VCOM_AND_DATA_SETTING);
    sendData(0x17);  // Border color: white

    // TCON Setting
    sendCommand(EPD_CMD_TCON_SETTING);
    sendData(0x22);

    waitUntilIdle();
}

void SpectraDisplay::powerOn() {
    DEBUG_PRINTLN("SpectraDisplay: Power ON");
    sendCommand(EPD_CMD_POWER_ON);
    waitUntilIdle();
}

void SpectraDisplay::powerOff() {
    DEBUG_PRINTLN("SpectraDisplay: Power OFF");
    sendCommand(EPD_CMD_POWER_OFF);
    waitUntilIdle();
}

void SpectraDisplay::sleep() {
    DEBUG_PRINTLN("SpectraDisplay: Entering deep sleep");
    sendCommand(EPD_CMD_DEEP_SLEEP);
    sendData(0xA5);  // Deep sleep mode with RAM retention
}

bool SpectraDisplay::displayRAW7(const uint8_t* buffer, size_t bufferSize) {
    if (!_initialized) {
        DEBUG_PRINTLN("SpectraDisplay: ERROR - Not initialized");
        return false;
    }

    if (bufferSize != RAW7_SIZE) {
        DEBUG_PRINTF("SpectraDisplay: ERROR - Invalid buffer size: %d (expected %d)\n",
                     bufferSize, RAW7_SIZE);
        return false;
    }

    DEBUG_PRINTLN("SpectraDisplay: Starting image transmission");

    // Power on the display
    powerOn();

    // Prepare to send image data
    sendCommand(EPD_CMD_DATA_START_TRANSMISSION);

    // Unpack RAW7 format (2 pixels per byte) to EPD format on the fly
    // RAW7: high nibble = first pixel, low nibble = second pixel
    const size_t rawChunk = 2048;  // 4KB expanded chunk
    uint8_t expandedBuffer[rawChunk * 2];

    DEBUG_PRINTLN("SpectraDisplay: Unpacking RAW7 data");
    for (size_t offset = 0; offset < bufferSize; offset += rawChunk) {
        size_t chunkSize = min(rawChunk, bufferSize - offset);
        for (size_t i = 0; i < chunkSize; i++) {
            uint8_t packed = buffer[offset + i];
            expandedBuffer[i * 2] = (packed >> 4) & 0x0F;      // High nibble
            expandedBuffer[i * 2 + 1] = packed & 0x0F;         // Low nibble
        }
        sendData(expandedBuffer, chunkSize * 2);
    }

    DEBUG_PRINTLN("SpectraDisplay: Transmitting to EPD complete");

    // Refresh display
    refresh();

    DEBUG_PRINTLN("SpectraDisplay: Display update complete");
    return true;
}

void SpectraDisplay::refresh() {
    DEBUG_PRINTLN("SpectraDisplay: Refreshing display (this may take 30-60 seconds)");
    sendCommand(EPD_CMD_DISPLAY_REFRESH);
    delay(100);

    // Wait for refresh to complete (can take 30-60 seconds for 7-color)
    waitUntilIdle(120000);  // 2 minute timeout

    DEBUG_PRINTLN("SpectraDisplay: Refresh complete");
}

void SpectraDisplay::clear(uint8_t color) {
    DEBUG_PRINTF("SpectraDisplay: Clearing to color %d\n", color);

    if (!_initialized) {
        DEBUG_PRINTLN("SpectraDisplay: ERROR - Not initialized");
        return;
    }

    powerOn();

    sendCommand(EPD_CMD_DATA_START_TRANSMISSION);

    // Send uniform color data
    const size_t chunkSize = 4096;
    uint8_t clearBuffer[chunkSize];
    memset(clearBuffer, color & 0x0F, chunkSize);

    size_t totalPixels = DISPLAY_WIDTH * DISPLAY_HEIGHT;
    for (size_t i = 0; i < totalPixels; i += chunkSize) {
        size_t remaining = totalPixels - i;
        size_t toSend = (remaining > chunkSize) ? chunkSize : remaining;
        sendData(clearBuffer, toSend);
    }

    refresh();
}
