#include "led_status.h"

LEDStatus::LEDStatus()
    : _initialized(false),
      _currentPattern(LED_OFF),
      _patternStartTime(0),
      _lastToggleTime(0),
      _ledState(false),
      _blinkCount(0) {
}

void LEDStatus::begin() {
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);
    _initialized = true;
    DEBUG_PRINTLN("LED: Status LED initialized on GPIO2");
}

void LEDStatus::on() {
    if (!_initialized) return;
    digitalWrite(PIN_STATUS_LED, HIGH);
    _ledState = true;
}

void LEDStatus::off() {
    if (!_initialized) return;
    digitalWrite(PIN_STATUS_LED, LOW);
    _ledState = false;
}

void LEDStatus::show(LEDPattern pattern) {
    if (!_initialized) return;
    executePattern(pattern);
}

void LEDStatus::executePattern(LEDPattern pattern) {
    switch (pattern) {
        case LED_OFF:
            off();
            break;

        case LED_ON:
            on();
            break;

        case LED_FAST_BLINK:
            // Fast blink ~200ms ON/OFF (WiFi connecting)
            // Run for a reasonable duration or until manually stopped
            DEBUG_PRINTLN("LED: Fast blink (WiFi connecting)");
            for (int i = 0; i < 20; i++) {  // 20 blinks = ~8 seconds
                on();
                delay(200);
                off();
                delay(200);
            }
            break;

        case LED_SLOW_BLINK:
            // Slow blink ~1s ON/OFF (WiFi setup AP mode)
            // This pattern is typically started non-blocking
            DEBUG_PRINTLN("LED: Slow blink (Setup AP mode)");
            on();
            delay(1000);
            off();
            delay(1000);
            break;

        case LED_TRIPLE_BLINK:
            // 3 short blinks (background reroll sent)
            DEBUG_PRINTLN("LED: Triple blink (BG reroll sent)");
            for (int i = 0; i < 3; i++) {
                on();
                delay(150);
                off();
                delay(150);
            }
            delay(500);  // Pause after triple blink
            break;

        case LED_SOLID_3S:
            // Solid ON for 3 seconds (new frame applied)
            DEBUG_PRINTLN("LED: Solid 3s (Frame applied)");
            on();
            delay(3000);
            off();
            break;

        case LED_FIVE_QUICK_BLINKS:
            // 5 quick blinks (factory reset)
            DEBUG_PRINTLN("LED: 5 quick blinks (Factory reset)");
            for (int i = 0; i < 5; i++) {
                on();
                delay(100);
                off();
                delay(100);
            }
            break;

        default:
            off();
            break;
    }
}

void LEDStatus::startPattern(LEDPattern pattern) {
    _currentPattern = pattern;
    _patternStartTime = millis();
    _lastToggleTime = millis();
    _blinkCount = 0;
}

void LEDStatus::update() {
    // Non-blocking pattern update for slow blink (used in config portal)
    if (_currentPattern == LED_SLOW_BLINK) {
        unsigned long now = millis();
        if (now - _lastToggleTime >= 1000) {
            _ledState = !_ledState;
            digitalWrite(PIN_STATUS_LED, _ledState ? HIGH : LOW);
            _lastToggleTime = now;
        }
    }
}
