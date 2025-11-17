#include "rtc_manager.h"

// RTC memory storage (persists across deep sleep)
RTC_DATA_ATTR RTCData rtcData;

RTCManager::RTCManager()
    : _wakeHour(WAKE_HOUR),
      _wakeMinute(WAKE_MINUTE),
      _timeInitialized(false) {
    // Load RTC data on construction
    loadRTCData();
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

// ============================================================
// NEW: RTC Memory Management
// ============================================================

void RTCManager::loadRTCData() {
    // Check if RTC data is valid
    if (rtcData.magic == RTC_MAGIC) {
        // Verify CRC
        uint32_t calculatedCRC = calculateCRC32((uint8_t*)&rtcData, sizeof(rtcData) - sizeof(rtcData.crc32));
        if (calculatedCRC == rtcData.crc32) {
            DEBUG_PRINTLN("RTC: Valid data loaded from RTC memory");
            DEBUG_PRINTF("RTC: WiFi failures: %d\n", rtcData.wifiFailureCount);
            DEBUG_PRINTF("RTC: Last refresh: %lu ms ago\n", millis() - rtcData.lastRefreshTimestamp);
            return;
        } else {
            DEBUG_PRINTLN("RTC: CRC mismatch - reinitializing RTC data");
        }
    } else {
        DEBUG_PRINTLN("RTC: First boot - initializing RTC data");
    }

    // Initialize RTC data
    rtcData.magic = RTC_MAGIC;
    rtcData.wifiFailureCount = 0;
    rtcData.lastRefreshTimestamp = 0;
    rtcData.refreshHistoryIndex = 0;
    for (int i = 0; i < RATE_LIMIT_MAX_REFRESHES; i++) {
        rtcData.refreshHistory[i] = 0;
    }
    saveRTCData();
}

void RTCManager::saveRTCData() {
    // Calculate and store CRC
    rtcData.crc32 = calculateCRC32((uint8_t*)&rtcData, sizeof(rtcData) - sizeof(rtcData.crc32));
    DEBUG_PRINTLN("RTC: Data saved to RTC memory");
}

uint32_t RTCManager::calculateCRC32(const uint8_t* data, size_t length) {
    // Simple CRC32 implementation
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc >> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
        }
    }
    return ~crc;
}

// ============================================================
// NEW: WiFi Failure Tracking
// ============================================================

void RTCManager::recordWiFiFailure() {
    rtcData.wifiFailureCount++;
    saveRTCData();
    DEBUG_PRINTF("RTC: WiFi failure recorded (count: %d)\n", rtcData.wifiFailureCount);
}

void RTCManager::recordWiFiSuccess() {
    if (rtcData.wifiFailureCount > 0) {
        DEBUG_PRINTF("RTC: WiFi success - clearing %d failures\n", rtcData.wifiFailureCount);
        rtcData.wifiFailureCount = 0;
        saveRTCData();
    }
}

uint8_t RTCManager::getWiFiFailureCount() {
    return rtcData.wifiFailureCount;
}

void RTCManager::resetWiFiFailureCount() {
    rtcData.wifiFailureCount = 0;
    saveRTCData();
    DEBUG_PRINTLN("RTC: WiFi failure count reset");
}

// ============================================================
// NEW: Refresh Throttling & Rate Limiting
// ============================================================

bool RTCManager::canRefreshNow() {
    uint32_t now = millis();
    uint32_t elapsed = now - rtcData.lastRefreshTimestamp;

    // Check minimum interval
    if (elapsed < MIN_REFRESH_INTERVAL_MS) {
        DEBUG_PRINTF("RTC: Refresh throttled - only %lu ms since last refresh (min: %lu ms)\n",
                     elapsed, (unsigned long)MIN_REFRESH_INTERVAL_MS);
        return false;
    }

    // Check rate limit
    if (isRateLimited()) {
        DEBUG_PRINTLN("RTC: Refresh rate limited - too many recent refreshes");
        return false;
    }

    return true;
}

void RTCManager::recordRefresh() {
    uint32_t now = millis();
    rtcData.lastRefreshTimestamp = now;

    // Add to refresh history ring buffer
    rtcData.refreshHistory[rtcData.refreshHistoryIndex] = now;
    rtcData.refreshHistoryIndex = (rtcData.refreshHistoryIndex + 1) % RATE_LIMIT_MAX_REFRESHES;

    saveRTCData();
    DEBUG_PRINTF("RTC: Refresh recorded at %lu ms\n", now);
}

uint32_t RTCManager::millisSinceLastRefresh() {
    return millis() - rtcData.lastRefreshTimestamp;
}

bool RTCManager::isRateLimited() {
    uint32_t now = millis();
    uint8_t recentCount = 0;

    // Count refreshes within the rate limit window
    for (int i = 0; i < RATE_LIMIT_MAX_REFRESHES; i++) {
        uint32_t refreshTime = rtcData.refreshHistory[i];
        if (refreshTime > 0 && (now - refreshTime) < RATE_LIMIT_WINDOW_MS) {
            recentCount++;
        }
    }

    // Rate limited if we've hit the max refreshes within the window
    bool limited = (recentCount >= RATE_LIMIT_MAX_REFRESHES);

    if (limited) {
        DEBUG_PRINTF("RTC: Rate limit check - %d refreshes in last %lu ms\n",
                     recentCount, (unsigned long)RATE_LIMIT_WINDOW_MS);
    }

    return limited;
}
