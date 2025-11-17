#include "rtc_manager.h"

RTCManager::RTCManager()
    : _wakeHour(WAKE_HOUR),
      _wakeMinute(WAKE_MINUTE),
      _timeInitialized(false) {
}

bool RTCManager::begin(const char* ntpServer, long gmtOffset, int daylightOffset) {
    DEBUG_PRINTLN("RTC: Initializing and syncing time from NTP");

    // Configure time
    configTime(gmtOffset, daylightOffset, ntpServer);

    // Wait for time sync (max 10 seconds)
    int retry = 0;
    const int maxRetries = 20;
    struct tm timeinfo;

    while (retry < maxRetries) {
        if (getLocalTime(&timeinfo)) {
            _timeInitialized = true;
            DEBUG_PRINTF("RTC: Time synchronized - %04d-%02d-%02d %02d:%02d:%02d\n",
                        timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                        timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
            return true;
        }
        delay(500);
        retry++;
        DEBUG_PRINT(".");
    }

    DEBUG_PRINTLN("\nRTC: Failed to sync time from NTP");
    return false;
}

bool RTCManager::getCurrentTime(struct tm& timeinfo) {
    if (!getLocalTime(&timeinfo)) {
        DEBUG_PRINTLN("RTC: Failed to get local time");
        return false;
    }
    return true;
}

uint64_t RTCManager::getSecondsUntilWake() {
    struct tm timeinfo;
    if (!getCurrentTime(timeinfo)) {
        // If time not available, default to 1 hour
        DEBUG_PRINTLN("RTC: Time not available, defaulting to 1 hour sleep");
        return 3600;
    }

    // Current time in minutes since midnight
    int currentMinutes = timeinfo.tm_hour * 60 + timeinfo.tm_min;

    // Wake time in minutes since midnight
    int wakeMinutes = _wakeHour * 60 + _wakeMinute;

    // Calculate difference
    int minutesUntilWake;

    if (wakeMinutes > currentMinutes) {
        // Wake time is today
        minutesUntilWake = wakeMinutes - currentMinutes;
    } else {
        // Wake time is tomorrow
        minutesUntilWake = (24 * 60) - currentMinutes + wakeMinutes;
    }

    uint64_t secondsUntilWake = minutesUntilWake * 60 - timeinfo.tm_sec;

    DEBUG_PRINTF("RTC: Current time: %02d:%02d:%02d\n",
                timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
    DEBUG_PRINTF("RTC: Wake time: %02d:%02d:00\n", _wakeHour, _wakeMinute);
    DEBUG_PRINTF("RTC: Sleep duration: %llu seconds (%.1f hours)\n",
                secondsUntilWake, secondsUntilWake / 3600.0);

    return secondsUntilWake;
}

void RTCManager::sleepUntilWake() {
    uint64_t sleepSeconds = getSecondsUntilWake();
    sleepForSeconds(sleepSeconds);
}

void RTCManager::sleepForSeconds(uint64_t seconds) {
    // Ensure minimum sleep time (avoid very short sleeps)
    if (seconds < 60) {
        DEBUG_PRINTLN("RTC: Sleep time too short, setting to 1 minute");
        seconds = 60;
    }

    DEBUG_PRINTF("RTC: Entering deep sleep for %llu seconds\n", seconds);

    // Configure timer wake
    esp_sleep_enable_timer_wakeup(seconds * 1000000ULL);  // microseconds

    // Flush serial before sleeping
    Serial.flush();
    delay(100);

    // Enter deep sleep
    esp_deep_sleep_start();
}

esp_sleep_wakeup_cause_t RTCManager::getWakeupCause() {
    return esp_sleep_get_wakeup_cause();
}

String RTCManager::getWakeupReasonString() {
    esp_sleep_wakeup_cause_t wakeup_reason = getWakeupCause();

    switch (wakeup_reason) {
        case ESP_SLEEP_WAKEUP_EXT0:
            return "Button (EXT0)";
        case ESP_SLEEP_WAKEUP_EXT1:
            return "EXT1";
        case ESP_SLEEP_WAKEUP_TIMER:
            return "Timer (Scheduled)";
        case ESP_SLEEP_WAKEUP_TOUCHPAD:
            return "Touchpad";
        case ESP_SLEEP_WAKEUP_ULP:
            return "ULP";
        case ESP_SLEEP_WAKEUP_GPIO:
            return "GPIO";
        case ESP_SLEEP_WAKEUP_UART:
            return "UART";
        default:
            return "Power On / Reset";
    }
}

bool RTCManager::wasTimerWake() {
    return getWakeupCause() == ESP_SLEEP_WAKEUP_TIMER;
}
