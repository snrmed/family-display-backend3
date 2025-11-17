#include "button_handler.h"

ButtonHandler::ButtonHandler()
    : _rerollState(HIGH),
      _lastRerollState(HIGH),
      _rerollDebounceTime(0),
      _resetState(HIGH),
      _lastResetState(HIGH),
      _resetPressStart(0),
      _resetDebounceTime(0),
      _resetLongPressTriggered(false) {
}

void ButtonHandler::begin() {
    // Configure reroll button (GPIO 34)
    // Note: GPIO 34 is input-only, no internal pull-up available
    // External pull-down or switch to VCC makes it HIGH when active
    pinMode(PIN_BUTTON_REROLL, INPUT);
    _rerollState = digitalRead(PIN_BUTTON_REROLL);
    _lastRerollState = _rerollState;

    // Configure reset button (GPIO 0)
    pinMode(PIN_BUTTON_RESET, INPUT_PULLUP);
    _resetState = digitalRead(PIN_BUTTON_RESET);
    _lastResetState = _resetState;

    DEBUG_PRINTF("Button: Initialized - Reroll:GPIO%d, Reset:GPIO%d\n",
                 PIN_BUTTON_REROLL, PIN_BUTTON_RESET);
}

bool ButtonHandler::readDebouncedState(uint8_t pin, bool& lastState, unsigned long& debounceTime) {
    bool reading = digitalRead(pin);

    // If the button state changed, reset debounce timer
    if (reading != lastState) {
        debounceTime = millis();
    }

    lastState = reading;

    // Only accept state change if it's been stable for debounce period
    if ((millis() - debounceTime) > BUTTON_DEBOUNCE_MS) {
        return reading;
    }

    // Return current stable state
    if (pin == PIN_BUTTON_REROLL) {
        return _rerollState;
    } else {
        return _resetState;
    }
}

ButtonEvent ButtonHandler::checkButton() {
    // Check reroll button (GPIO 34)
    // This is active HIGH (switch connects to VCC when down)
    bool currentReroll = readDebouncedState(PIN_BUTTON_REROLL, _lastRerollState, _rerollDebounceTime);

    if (currentReroll == HIGH && _rerollState == LOW) {
        // Reroll button activated (LOW -> HIGH transition)
        DEBUG_PRINTLN("Button: Reroll button activated (switch DOWN to GPIO 34)");
        _rerollState = currentReroll;
        return BUTTON_REROLL_PRESSED;
    }
    _rerollState = currentReroll;

    // Check reset button (GPIO 0)
    // This is active LOW (pulled down when pressed)
    bool currentReset = readDebouncedState(PIN_BUTTON_RESET, _lastResetState, _resetDebounceTime);

    // Reset button pressed (HIGH -> LOW)
    if (currentReset == LOW && _resetState == HIGH) {
        _resetPressStart = millis();
        _resetLongPressTriggered = false;
        DEBUG_PRINTLN("Button: Reset button pressed (switch UP to GPIO 0)");
    }

    // Reset button being held
    if (currentReset == LOW && _resetState == LOW) {
        unsigned long pressDuration = millis() - _resetPressStart;

        // Long press detected
        if (!_resetLongPressTriggered && pressDuration >= BUTTON_LONG_PRESS_MS) {
            _resetLongPressTriggered = true;
            DEBUG_PRINTLN("Button: Long press detected - FACTORY RESET");
            _resetState = currentReset;
            return BUTTON_RESET_LONG_PRESS;
        }
    }

    // Reset button released
    if (currentReset == HIGH && _resetState == LOW) {
        unsigned long pressDuration = millis() - _resetPressStart;
        DEBUG_PRINTF("Button: Reset button released (duration: %lu ms)\n", pressDuration);
    }

    _resetState = currentReset;
    return BUTTON_NONE;
}

void ButtonHandler::enableWakeup() {
    // Configure both buttons as wake sources using ext1
    // Wake on ANY HIGH (either button going HIGH will wake the device)
    const uint64_t ext_wakeup_pin_mask =
        (1ULL << PIN_BUTTON_REROLL) |
        (1ULL << PIN_BUTTON_RESET);

    esp_sleep_enable_ext1_wakeup(ext_wakeup_pin_mask, ESP_EXT1_WAKEUP_ANY_HIGH);

    DEBUG_PRINTF("Button: Wake enabled on GPIO%d and GPIO%d\n",
                 PIN_BUTTON_REROLL, PIN_BUTTON_RESET);
}

bool ButtonHandler::wasWakeSource() {
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    return (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1);
}

uint8_t ButtonHandler::getWakePin() {
    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1) {
        uint64_t wakeup_pin_mask = esp_sleep_get_ext1_wakeup_status();

        if (wakeup_pin_mask & (1ULL << PIN_BUTTON_REROLL)) {
            return PIN_BUTTON_REROLL;
        }
        if (wakeup_pin_mask & (1ULL << PIN_BUTTON_RESET)) {
            return PIN_BUTTON_RESET;
        }
    }
    return 0;
}
