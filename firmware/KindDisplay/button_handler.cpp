#include "button_handler.h"

ButtonHandler::ButtonHandler(uint8_t pin)
    : _pin(pin),
      _buttonState(HIGH),
      _lastButtonState(HIGH),
      _pressStartTime(0),
      _lastDebounceTime(0),
      _longPressTriggered(false) {
}

void ButtonHandler::begin() {
    pinMode(_pin, INPUT_PULLUP);
    _buttonState = digitalRead(_pin);
    _lastButtonState = _buttonState;

    DEBUG_PRINTF("Button: Initialized on GPIO %d\n", _pin);
}

bool ButtonHandler::readDebouncedState() {
    bool reading = digitalRead(_pin);

    // If the button state changed, reset debounce timer
    if (reading != _lastButtonState) {
        _lastDebounceTime = millis();
    }

    _lastButtonState = reading;

    // Only accept state change if it's been stable for debounce period
    if ((millis() - _lastDebounceTime) > BUTTON_DEBOUNCE_MS) {
        return reading;
    }

    return _buttonState;  // Return previous stable state
}

ButtonEvent ButtonHandler::checkButton() {
    bool currentState = readDebouncedState();

    // Button pressed (LOW, because we use INPUT_PULLUP)
    if (currentState == LOW && _buttonState == HIGH) {
        // Button just pressed
        _pressStartTime = millis();
        _longPressTriggered = false;
        DEBUG_PRINTLN("Button: Pressed");
    }

    // Button is being held
    if (currentState == LOW && _buttonState == LOW) {
        unsigned long pressDuration = millis() - _pressStartTime;

        // Long press detected
        if (!_longPressTriggered && pressDuration >= BUTTON_LONG_PRESS_MS) {
            _longPressTriggered = true;
            DEBUG_PRINTLN("Button: Long press detected (factory reset)");
            _buttonState = currentState;
            return BUTTON_LONG_PRESS;
        }
    }

    // Button released
    if (currentState == HIGH && _buttonState == LOW) {
        unsigned long pressDuration = millis() - _pressStartTime;
        DEBUG_PRINTF("Button: Released (duration: %lu ms)\n", pressDuration);

        _buttonState = currentState;

        // Short press (only if long press wasn't triggered)
        if (!_longPressTriggered && pressDuration < BUTTON_LONG_PRESS_MS) {
            DEBUG_PRINTLN("Button: Short press detected (background reroll)");
            return BUTTON_SHORT_PRESS;
        }

        return BUTTON_NONE;
    }

    _buttonState = currentState;
    return BUTTON_NONE;
}

void ButtonHandler::enableWakeup() {
    // Configure button as ext0 wake source (wake on LOW)
    esp_sleep_enable_ext0_wakeup((gpio_num_t)_pin, LOW);
    DEBUG_PRINTF("Button: Wake enabled on GPIO %d\n", _pin);
}

bool ButtonHandler::wasWakeSource() {
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    return (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0);
}
