#include "battery.h"

BatteryMonitor::BatteryMonitor()
    : _initialized(false),
      _lastVoltage(0.0f),
      _lastPercentage(100) {
}

void BatteryMonitor::begin() {
    if (!BATTERY_ENABLED) {
        DEBUG_PRINTLN("Battery: Monitoring disabled in config");
        return;
    }

    // Configure ADC for battery reading
    pinMode(PIN_BATTERY_ADC, INPUT);

    // ESP32 ADC configuration for better accuracy
    analogSetAttenuation(ADC_11db);  // 0-3.3V range

    _initialized = true;
    DEBUG_PRINTF("Battery: Monitoring enabled on GPIO%d\n", PIN_BATTERY_ADC);

    // Take initial reading
    _lastVoltage = readVoltage();
    _lastPercentage = getPercentage();
    DEBUG_PRINTF("Battery: Initial reading: %.2fV (%d%%)\n", _lastVoltage, _lastPercentage);
}

float BatteryMonitor::readVoltage() {
    if (!_initialized || !BATTERY_ENABLED) {
        return BATTERY_VOLTAGE_MAX;  // Assume full if not enabled
    }

    // Read ADC (12-bit, 0-4095)
    int adcValue = analogRead(PIN_BATTERY_ADC);

    // Convert ADC to voltage at the pin
    float pinVoltage = (adcValue / 4095.0f) * BATTERY_ADC_REFERENCE;

    // Apply voltage divider ratio to get actual battery voltage
    float batteryVoltage = pinVoltage * BATTERY_DIVIDER_RATIO;

    _lastVoltage = batteryVoltage;

    DEBUG_PRINTF("Battery: ADC=%d, Pin=%.2fV, Battery=%.2fV\n",
                 adcValue, pinVoltage, batteryVoltage);

    return batteryVoltage;
}

uint8_t BatteryMonitor::voltageToPercentage(float voltage) {
    // Simple linear interpolation between min and max voltage
    if (voltage >= BATTERY_VOLTAGE_MAX) return 100;
    if (voltage <= BATTERY_VOLTAGE_MIN) return 0;

    float range = BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN;
    float percentage = ((voltage - BATTERY_VOLTAGE_MIN) / range) * 100.0f;

    return (uint8_t)constrain(percentage, 0, 100);
}

uint8_t BatteryMonitor::getPercentage() {
    if (!_initialized || !BATTERY_ENABLED) {
        return 100;  // Assume full if not enabled
    }

    float voltage = readVoltage();
    _lastPercentage = voltageToPercentage(voltage);

    return _lastPercentage;
}

bool BatteryMonitor::isLow() {
    return (_lastPercentage < BATTERY_LOW_THRESHOLD);
}

bool BatteryMonitor::isCritical() {
    return (_lastPercentage < BATTERY_CRITICAL_THRESHOLD);
}

void BatteryMonitor::setPixel(uint8_t* buffer, int x, int y, uint8_t color) {
    // RAW7 format: 2 pixels per byte (high nibble = left pixel, low nibble = right pixel)
    // Bounds check
    if (x < 0 || x >= DISPLAY_WIDTH || y < 0 || y >= DISPLAY_HEIGHT) {
        return;
    }

    int pixelIndex = y * DISPLAY_WIDTH + x;
    int byteIndex = pixelIndex / 2;
    bool isHighNibble = (pixelIndex % 2 == 0);

    if (byteIndex >= RAW7_SIZE) return;

    if (isHighNibble) {
        // High nibble (left pixel)
        buffer[byteIndex] = (buffer[byteIndex] & 0x0F) | ((color & 0x0F) << 4);
    } else {
        // Low nibble (right pixel)
        buffer[byteIndex] = (buffer[byteIndex] & 0xF0) | (color & 0x0F);
    }
}

void BatteryMonitor::fillRect(uint8_t* buffer, int x, int y, int width, int height, uint8_t color) {
    for (int dy = 0; dy < height; dy++) {
        for (int dx = 0; dx < width; dx++) {
            setPixel(buffer, x + dx, y + dy, color);
        }
    }
}

void BatteryMonitor::drawWarningText(uint8_t* buffer, int x, int y) {
    // Simple 5x7 bitmap font for "TIME TO CHARGE"
    // For simplicity, we'll draw a simplified message
    // You can replace this with a proper font library if needed

    // For now, just draw "LOW BATTERY" as a simple pattern
    // This is a placeholder - you can enhance with actual text rendering

    // Draw "!" symbol as a simple indicator
    const uint8_t exclamation[7] = {
        0b01110,  // .###.
        0b01110,  // .###.
        0b01110,  // .###.
        0b01110,  // .###.
        0b00000,  // .....
        0b01110,  // .###.
        0b01110   // .###.
    };

    // Draw the exclamation mark pattern (scaled 2x)
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (exclamation[row] & (1 << (4 - col))) {
                // Draw 2x2 pixels for each bit
                setPixel(buffer, x + col*2, y + row*2, EPD_WHITE);
                setPixel(buffer, x + col*2 + 1, y + row*2, EPD_WHITE);
                setPixel(buffer, x + col*2, y + row*2 + 1, EPD_WHITE);
                setPixel(buffer, x + col*2 + 1, y + row*2 + 1, EPD_WHITE);
            }
        }
    }
}

void BatteryMonitor::overlayLowBatteryWarning(uint8_t* raw7Buffer, size_t bufferSize) {
    if (bufferSize != RAW7_SIZE) {
        DEBUG_PRINTLN("Battery: Invalid RAW7 buffer size for overlay");
        return;
    }

    if (!isLow()) {
        return;  // Battery is fine, no overlay needed
    }

    DEBUG_PRINTF("Battery: Overlaying low battery warning (%d%%)\n", _lastPercentage);

    // Warning box dimensions and position (bottom-right corner)
    const int boxWidth = 80;
    const int boxHeight = 40;
    const int boxX = DISPLAY_WIDTH - boxWidth - 10;   // 10px margin from right
    const int boxY = DISPLAY_HEIGHT - boxHeight - 10;  // 10px margin from bottom

    // Draw red background box
    fillRect(raw7Buffer, boxX, boxY, boxWidth, boxHeight, EPD_RED);

    // Draw white border (2px thick)
    for (int i = 0; i < 2; i++) {
        // Top border
        fillRect(raw7Buffer, boxX + i, boxY + i, boxWidth - 2*i, 1, EPD_WHITE);
        // Bottom border
        fillRect(raw7Buffer, boxX + i, boxY + boxHeight - 1 - i, boxWidth - 2*i, 1, EPD_WHITE);
        // Left border
        fillRect(raw7Buffer, boxX + i, boxY + i, 1, boxHeight - 2*i, EPD_WHITE);
        // Right border
        fillRect(raw7Buffer, boxX + boxWidth - 1 - i, boxY + i, 1, boxHeight - 2*i, EPD_WHITE);
    }

    // Draw warning symbol (white "!" in the center)
    int symbolX = boxX + boxWidth / 2 - 5;
    int symbolY = boxY + boxHeight / 2 - 7;
    drawWarningText(raw7Buffer, symbolX, symbolY);

    DEBUG_PRINTLN("Battery: Low battery overlay applied");
}
