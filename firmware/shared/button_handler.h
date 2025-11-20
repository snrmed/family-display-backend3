#ifndef BUTTON_HANDLER_H
#define BUTTON_HANDLER_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// Mode Switch Handler
// ============================================================
// Handles 3-position slide switch configuration:
// - NORMAL MODE (center): GPIO34 = HIGH, GPIO35 = LOW
// - SPECIAL MODE (up):    GPIO34 = LOW,  GPIO35 = HIGH
//
// SPECIAL mode triggers background reroll before fetching image
// ============================================================

enum SwitchMode {
    MODE_NORMAL = 0,   // Center position - normal operation
    MODE_SPECIAL = 1,  // Up position - trigger background reroll
    MODE_UNKNOWN = 2   // Invalid/transition state
};

class ButtonHandler {
public:
    ButtonHandler();

    // Initialize switch GPIOs
    void begin();

    // Read current switch position
    SwitchMode readMode();

    // Get string representation of mode
    const char* getModeString(SwitchMode mode);

    // Enable switch for wake from deep sleep (optional, if needed)
    void enableWakeup();

    // Check which GPIO caused wake from deep sleep
    static bool wasWakeSource();
    static uint8_t getWakePin();

private:
    SwitchMode _currentMode;
    unsigned long _lastReadTime;

    // Debounce helper
    SwitchMode readDebouncedMode();
};

#endif // BUTTON_HANDLER_H
