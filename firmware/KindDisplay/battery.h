#ifndef BATTERY_H
#define BATTERY_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// Battery Monitor
// ============================================================
// Functions:
// - Read battery voltage via ADC
// - Calculate battery percentage
// - Render "TIME TO CHARGE" overlay on RAW7 buffer
// - Determine if critical battery requires extended sleep
// ============================================================

class BatteryMonitor {
public:
    BatteryMonitor();

    // Initialize ADC for battery reading
    void begin();

    // Read current battery voltage
    float readVoltage();

    // Get battery percentage (0-100)
    uint8_t getPercentage();

    // Check if battery is low (below LOW_THRESHOLD)
    bool isLow();

    // Check if battery is critical (below CRITICAL_THRESHOLD)
    bool isCritical();

    // Overlay "TIME TO CHARGE" warning on RAW7 buffer
    // Adds a small red box with white text in bottom-right corner
    // Buffer must be 192000 bytes (800×480, 2 pixels per byte)
    void overlayLowBatteryWarning(uint8_t* raw7Buffer, size_t bufferSize);

private:
    bool _initialized;
    float _lastVoltage;
    uint8_t _lastPercentage;

    // Helper: Set a pixel in RAW7 buffer
    void setPixel(uint8_t* buffer, int x, int y, uint8_t color);

    // Helper: Draw a filled rectangle
    void fillRect(uint8_t* buffer, int x, int y, int width, int height, uint8_t color);

    // Helper: Draw simple text "TIME TO CHARGE" (bitmap-based)
    void drawWarningText(uint8_t* buffer, int x, int y);

    // Voltage to percentage conversion
    uint8_t voltageToPercentage(float voltage);
};

#endif // BATTERY_H
