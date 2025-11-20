#ifndef LED_STATUS_H
#define LED_STATUS_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// LED Status Indicator
// ============================================================
// Provides visual feedback via GPIO2 status LED
// Patterns:
// - Fast blink: WiFi connecting
// - Slow blink: WiFi setup AP mode
// - Triple blink: Background reroll sent
// - Solid ON (3s): New frame applied successfully
// - 5 quick blinks: Factory reset complete
// - OFF: Before deep sleep
// ============================================================

enum LEDPattern {
    LED_OFF = 0,
    LED_FAST_BLINK,        // ~200ms ON/OFF - WiFi connecting
    LED_SLOW_BLINK,        // ~1s ON/OFF - WiFi setup AP
    LED_TRIPLE_BLINK,      // 3 short blinks - BG reroll sent
    LED_SOLID_3S,          // Solid ON for 3s - Frame applied
    LED_FIVE_QUICK_BLINKS, // 5 quick blinks - Factory reset
    LED_ON                 // Solid ON
};

class LEDStatus {
public:
    LEDStatus();

    // Initialize LED GPIO
    void begin();

    // Execute a specific LED pattern (blocking)
    void show(LEDPattern pattern);

    // Simple on/off control
    void on();
    void off();

    // Non-blocking pattern update (call in loop if needed)
    void update();

    // Start a non-blocking pattern
    void startPattern(LEDPattern pattern);

private:
    bool _initialized;
    LEDPattern _currentPattern;
    unsigned long _patternStartTime;
    unsigned long _lastToggleTime;
    bool _ledState;
    uint8_t _blinkCount;

    void executePattern(LEDPattern pattern);
};

#endif // LED_STATUS_H
