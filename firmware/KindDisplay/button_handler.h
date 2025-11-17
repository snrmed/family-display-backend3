#ifndef BUTTON_HANDLER_H
#define BUTTON_HANDLER_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// Button Handler
// ============================================================
// Handles dual button configuration:
// - Reroll button (GPIO 34): Trigger background reroll
// - Reset button (GPIO 0): Factory reset (long press 6s)
// ============================================================

enum ButtonEvent {
    BUTTON_NONE = 0,
    BUTTON_REROLL_PRESSED,  // GPIO 34 activated
    BUTTON_RESET_LONG_PRESS // GPIO 0 held for 6+ seconds
};

class ButtonHandler {
public:
    ButtonHandler();

    // Initialize button GPIOs
    void begin();

    // Check for button events (call from main loop)
    ButtonEvent checkButton();

    // Enable buttons for wake from deep sleep
    void enableWakeup();

    // Check which button caused wake from deep sleep
    static bool wasWakeSource();
    static uint8_t getWakePin();

private:
    // Reroll button (GPIO 34)
    bool _rerollState;
    bool _lastRerollState;
    unsigned long _rerollDebounceTime;

    // Reset button (GPIO 0)
    bool _resetState;
    bool _lastResetState;
    unsigned long _resetPressStart;
    unsigned long _resetDebounceTime;
    bool _resetLongPressTriggered;

    // Debounce helpers
    bool readDebouncedState(uint8_t pin, bool& lastState, unsigned long& debounceTime);
};

#endif // BUTTON_HANDLER_H
