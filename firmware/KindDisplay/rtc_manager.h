#ifndef RTC_MANAGER_H
#define RTC_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include "config.h"

// ============================================================
// RTC and Deep Sleep Manager
// ============================================================
// Manages:
// - Daily wake at configured time (default 01:00)
// - Deep sleep scheduling
// - Time synchronization via NTP
// ============================================================

class RTCManager {
public:
    RTCManager();

    // Initialize RTC and sync time from NTP
    bool begin(const char* ntpServer = "pool.ntp.org", long gmtOffset = 0, int daylightOffset = 0);

    // Get current time
    bool getCurrentTime(struct tm& timeinfo);

    // Calculate seconds until next wake time
    uint64_t getSecondsUntilWake();

    // Enter deep sleep until next wake time
    void sleepUntilWake();

    // Enter deep sleep for specified seconds
    void sleepForSeconds(uint64_t seconds);

    // Check what caused the wake
    static esp_sleep_wakeup_cause_t getWakeupCause();

    // Get human-readable wakeup reason
    static String getWakeupReasonString();

    // Check if this is a timer wake (scheduled)
    static bool wasTimerWake();

private:
    int _wakeHour;
    int _wakeMinute;
    bool _timeInitialized;
};

#endif // RTC_MANAGER_H
