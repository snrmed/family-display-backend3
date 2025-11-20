#ifndef RTC_MANAGER_H
#define RTC_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include "config.h"

// ============================================================
// RTC Memory Structure (persists across deep sleep)
// ============================================================
// Used for:
// - WiFi failure tracking (auto-recovery)
// - Refresh throttling (panel protection)
// - Rate limiting (prevent excessive refreshes)
// ============================================================

struct RTCData {
    uint32_t magic;                    // Magic number to verify valid data (0xCAFEBABE)
    uint8_t wifiFailureCount;          // Consecutive WiFi failures
    time_t lastRefreshTimestamp;       // Unix timestamp of last refresh
    time_t refreshHistory[RATE_LIMIT_MAX_REFRESHES];  // Ring buffer of recent refresh times (Unix timestamps)
    uint8_t refreshHistoryIndex;       // Current index in ring buffer
    uint8_t rotaryClickCount;          // Rotary switch click counter (for factory reset detection)
    uint32_t lastRotaryClickMillis;    // Millis timestamp of last rotary click
    uint32_t crc32;                    // CRC32 checksum for data integrity
};

#define RTC_MAGIC 0xCAFEBABE

// ============================================================
// RTC and Deep Sleep Manager
// ============================================================
// Manages:
// - Daily wake at configured time (default 01:00)
// - Deep sleep scheduling
// - Time synchronization via NTP
// - WiFi failure tracking (NEW)
// - Refresh throttling (NEW)
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

    // ========== NEW: WiFi Failure Tracking ==========
    // Record a WiFi connection failure
    void recordWiFiFailure();

    // Record a successful WiFi connection (resets failure count)
    void recordWiFiSuccess();

    // Get consecutive WiFi failure count
    uint8_t getWiFiFailureCount();

    // Reset WiFi failure count
    void resetWiFiFailureCount();

    // ========== NEW: Refresh Throttling & Rate Limiting ==========
    // Check if enough time has passed since last refresh
    bool canRefreshNow();

    // Record that a refresh occurred (updates timestamp and history)
    void recordRefresh();

    // Get milliseconds since last refresh
    uint32_t millisSinceLastRefresh();

    // Check if rate limit is exceeded (too many refreshes recently)
    bool isRateLimited();

    // ========== NEW: Rotary Click Tracking (for factory reset) ==========
    // Check and record rotary click, returns true if factory reset should be triggered (6 clicks)
    bool checkRotaryClicks();

    // Reset rotary click counter
    void resetRotaryClickCount();

private:
    int _wakeHour;
    int _wakeMinute;
    bool _timeInitialized;

    // RTC memory persistence
    void loadRTCData();
    void saveRTCData();
    uint32_t calculateCRC32(const uint8_t* data, size_t length);
};

#endif // RTC_MANAGER_H
