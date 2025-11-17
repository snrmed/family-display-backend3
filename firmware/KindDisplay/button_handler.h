#ifndef BUTTON_HANDLER_H
#define BUTTON_HANDLER_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// Button Handler
// ============================================================
// Handles button debouncing and press detection
// - Short press: Trigger background reroll
// - Long press (6s): Factory reset
// ============================================================

enum ButtonEvent {
    BUTTON_NONE = 0,
    BUTTON_SHORT_PRESS,
    BUTTON_LONG_PRESS
};

class ButtonHandler {
public:
    ButtonHandler(uint8_t pin);

    // Initialize button GPIO and interrupts
    void begin();

    // Check for button events (call from main loop)
    ButtonEvent checkButton();

    // Enable/disable button wake from deep sleep
    void enableWakeup();

    // Check if button caused wake from deep sleep
    static bool wasWakeSource();

private:
    uint8_t _pin;
    bool _buttonState;
    bool _lastButtonState;
    unsigned long _pressStartTime;
    unsigned long _lastDebounceTime;
    bool _longPressTriggered;

    // Debounce the button state
    bool readDebouncedState();
};

#endif // BUTTON_HANDLER_H
