#ifndef DISPLAY_DRIVER_H
#define DISPLAY_DRIVER_H

#include <Arduino.h>
#include <SPI.h>
#include "config.h"

// ============================================================
// Spectra-6 (E6) 7-Color E-Ink Display Driver
// ============================================================
// Panel: P730010-MF1-A
// Resolution: 800×480
// Colors: 7 (White, Black, Red, Yellow, Blue, Green, Orange)
// ============================================================

class SpectraDisplay {
public:
    SpectraDisplay();

    // Initialize the display hardware
    bool begin();

    // Display a RAW7 image buffer
    // Buffer must be 192000 bytes (800×480 pixels, 2 pixels per byte)
    bool displayRAW7(const uint8_t* buffer, size_t bufferSize);

    // Streaming RAW7 display - eliminates need for 192KB buffer
    // Call beginRAW7Stream() once, then streamRAW7Chunk() for each chunk,
    // finally endRAW7Stream() to refresh
    bool beginRAW7Stream();
    bool streamRAW7Chunk(const uint8_t* chunk, size_t chunkSize);
    bool endRAW7Stream();

    // Clear display to a single color
    void clear(uint8_t color = EPD_WHITE);

    // Power management
    void powerOn();
    void powerOff();
    void sleep();

    // Hardware reset
    void reset();

private:
    // Low-level EPD commands
    void sendCommand(uint8_t command);
    void sendData(uint8_t data);
    void sendData(const uint8_t* data, size_t len);

    // Wait for display to be ready
    bool waitUntilIdle(uint32_t timeout_ms = 30000);

    // EPD initialization sequence for Spectra-6
    void initEPD();

    // Refresh/update the display
    void refresh();

    // Flag to track initialization state
    bool _initialized;

    // Streaming state tracking
    bool _streaming;
    size_t _streamBytesReceived;
};

#endif // DISPLAY_DRIVER_H
