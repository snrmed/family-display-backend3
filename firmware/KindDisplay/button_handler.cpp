#include "button_handler.h"

ButtonHandler::ButtonHandler()
    : _currentMode(MODE_UNKNOWN),
      _lastReadTime(0) {
}

void ButtonHandler::begin() {
    // Configure switch position GPIOs
    // GPIO 34 and 35 are input-only, no internal pull-ups available
    // Expecting external pull-downs or direct switch connections
    pinMode(PIN_SWITCH_34, INPUT);
    pinMode(PIN_SWITCH_35, INPUT);

    // Read initial mode
    _currentMode = readMode();

    DEBUG_PRINTF("Switch: Initialized - GPIO34=%d, GPIO35=%d\n",
                 PIN_SWITCH_34, PIN_SWITCH_35);
    DEBUG_PRINTF("Switch: Current mode: %s\n", getModeString(_currentMode));
}

SwitchMode ButtonHandler::readDebouncedMode() {
    // Read both GPIO pins
    bool gpio34 = digitalRead(PIN_SWITCH_34);
    bool gpio35 = digitalRead(PIN_SWITCH_35);

    // Determine mode based on switch position
    // NORMAL MODE:  GPIO34 = HIGH, GPIO35 = LOW
    // SPECIAL MODE: GPIO34 = LOW,  GPIO35 = HIGH

    if (gpio34 == HIGH && gpio35 == LOW) {
        return MODE_NORMAL;
    } else if (gpio34 == LOW && gpio35 == HIGH) {
        return MODE_SPECIAL;
    } else {
        // Invalid state (both HIGH, both LOW, or transition)
        return MODE_UNKNOWN;
    }
}

SwitchMode ButtonHandler::readMode() {
    unsigned long now = millis();

    // Simple debounce: only read every 50ms
    if (now - _lastReadTime < BUTTON_DEBOUNCE_MS) {
        return _currentMode;
    }

    _lastReadTime = now;
    SwitchMode newMode = readDebouncedMode();

    // Only update if we get a valid mode
    if (newMode != MODE_UNKNOWN) {
        _currentMode = newMode;
    }

    return _currentMode;
}

const char* ButtonHandler::getModeString(SwitchMode mode) {
    switch (mode) {
        case MODE_NORMAL:  return "NORMAL";
        case MODE_SPECIAL: return "SPECIAL";
        case MODE_UNKNOWN: return "UNKNOWN";
        default:           return "INVALID";
    }
}

void ButtonHandler::enableWakeup() {
    // DISABLED: All GPIO wake sources disabled due to boot loop issues
    // Both GPIO0 and GPIO34 cause immediate re-wake after deep sleep
    // Relying on timer wake only until press-button GPIO is identified

    // TODO: Investigate rotary "press down" button for wake source

    DEBUG_PRINTLN("Switch: GPIO wake DISABLED - timer wake only (boot loop prevention)");

    // No wake sources enabled - device will only wake on timer
}

bool ButtonHandler::wasWakeSource() {
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    return (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1);
}

uint8_t ButtonHandler::getWakePin() {
    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1) {
        uint64_t wakeup_pin_mask = esp_sleep_get_ext1_wakeup_status();

        if (wakeup_pin_mask & (1ULL << 0)) {
            return 0;  // GPIO0 (UP position)
        }
        if (wakeup_pin_mask & (1ULL << PIN_SWITCH_34)) {
            return PIN_SWITCH_34;  // GPIO34 (DOWN position)
        }
    }
    return 255;  // Invalid/unknown
}
