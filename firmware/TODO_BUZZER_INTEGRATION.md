# Todo Schedule Buzzer Integration

## Overview

Integrate reTerminal E1002 buzzer with todo schedule to provide audio reminders for upcoming tasks.

## Implementation Approaches

### Option 1: Backend Signals "Beep Now" (Recommended)

**How it works:**
1. Device wakes once per day (e.g., 1 AM)
2. Backend sends daily schedule with buzzer timings
3. Device sets RTC alarms for each todo time
4. Device wakes at todo time, beeps, goes back to sleep

**Data flow:**
```
Backend Response (at 1 AM daily update):
{
  "image_url": "/v1/raw7?device=abc",
  "buzzer_schedule": [
    {
      "time": "08:00",
      "pattern": "2,100,100",
      "label": "Morning medication"
    },
    {
      "time": "14:00",
      "pattern": "3,150,200",
      "label": "Afternoon walk"
    },
    {
      "time": "20:00",
      "pattern": "2,100,100",
      "label": "Evening medication"
    }
  ]
}
```

**Firmware implementation:**
```cpp
// Parse buzzer schedule from JSON response
struct BuzzerEvent {
  uint8_t hour;
  uint8_t minute;
  uint8_t beep_count;
  uint16_t beep_on_ms;
  uint16_t beep_off_ms;
};

BuzzerEvent events[MAX_DAILY_EVENTS]; // e.g., 10 max
int event_count = 0;

// Set RTC alarms for each event
void setupDailyBuzzerAlarms() {
  for (int i = 0; i < event_count; i++) {
    rtc.setAlarm(events[i].hour, events[i].minute);
  }
}

// Wake handler
void onWakeFromSleep() {
  if (wakeReason == RTC_ALARM) {
    // Check which event triggered
    BuzzerEvent* event = getCurrentEvent();
    playBuzzerPattern(event->beep_count, event->beep_on_ms, event->beep_off_ms);

    // Go back to sleep until next alarm
    enterDeepSleep(calculateNextWakeTime());
  }
}
```

**Pros:**
- ✅ Most battery efficient (device only wakes when needed)
- ✅ Accurate timing (RTC-based)
- ✅ Works offline after initial sync
- ✅ Simple device logic

**Cons:**
- ❌ Requires ESP32 RTC alarm support (it has this)
- ❌ Limited to ~10 events per day (RTC alarm limit)

---

### Option 2: Device Polls Backend Periodically

**How it works:**
1. Device wakes every 15-30 minutes
2. Checks backend for "should beep now?" status
3. Beeps if backend says yes
4. Goes back to sleep

**Pros:**
- ✅ Backend has full control
- ✅ Can change schedule dynamically
- ✅ Simple device code

**Cons:**
- ❌ **Very bad for battery** (48-96 wakes per day vs 1)
- ❌ Requires WiFi connection every 15 min
- ❌ Timing accuracy ±15 min

**Verdict:** ❌ Not recommended due to battery impact

---

### Option 3: Backend Sends Schedule via HTTP Header (Hybrid)

**How it works:**
1. Device wakes once daily for image update
2. Backend sends buzzer schedule in HTTP header (not JSON body)
3. Device parses header, sets RTC alarms
4. Device wakes at alarm times to beep

**Example HTTP header:**
```http
X-Buzzer-Schedule: 08:00:2:100:100,14:00:3:150:200,20:00:2:100:100
Format: HH:MM:count:on_ms:off_ms
```

**Pros:**
- ✅ Battery efficient (same as Option 1)
- ✅ No JSON parsing overhead
- ✅ Works with existing RAW7 endpoint

**Cons:**
- ❌ Less human-readable than JSON
- ❌ Header size limits (~8KB)

---

## Battery Impact Analysis

### Power Consumption Breakdown

**Components:**
- **ESP32-S3 Active**: ~150mA @ 3.7V = 555mW
- **ESP32-S3 Deep Sleep**: ~50μA @ 3.7V = 0.185mW
- **WiFi Active**: ~200mA @ 3.7V = 740mW
- **Buzzer**: ~30mA @ 3.7V = 111mW (typical piezo buzzer)
- **Display Refresh**: ~150mA @ 3.7V for ~60s = 555mW

### Scenario 1: Current Setup (1 wake/day, no buzzer)
```
Daily power consumption:
- 1x Display update (60s active + 30s WiFi) = 90s total
  - Active: 150mA × 90s = 3.75 mAh
  - WiFi overhead: 200mA × 30s = 1.67 mAh
- Deep sleep (23h 58.5m): 50μA × 86310s = 1.20 mAh
Total: ~6.6 mAh/day

Battery life (2000mAh): 2000 / 6.6 = 303 days (~10 months)
```

### Scenario 2: Daily update + 3 buzzer events (Option 1 - Recommended)
```
Daily power consumption:
- 1x Display update: 6.6 mAh (same as above)
- 3x Buzzer events:
  - Each wake: ~2s active (no WiFi/display)
    - ESP32 active: 150mA × 2s = 0.083 mAh
    - Buzzer: 30mA × 0.3s (3 beeps × 100ms) = 0.0025 mAh
  - 3 events: 3 × 0.086 mAh = 0.26 mAh
Total: 6.6 + 0.26 = 6.86 mAh/day

Battery life (2000mAh): 2000 / 6.86 = 291 days (~9.7 months)

Impact: -4% battery life (negligible!)
```

### Scenario 3: Polling every 15 min (Option 2 - NOT Recommended)
```
Daily power consumption:
- 96 wakes/day (every 15 min):
  - Each wake: WiFi connect (10s) + check (2s) = 12s
    - ESP32: 150mA × 12s = 0.5 mAh
    - WiFi: 200mA × 10s = 0.56 mAh
  - 96 wakes: 96 × 1.06 mAh = 101.76 mAh
- Deep sleep (between wakes): 50μA × 86400s = 1.2 mAh
Total: ~103 mAh/day

Battery life (2000mAh): 2000 / 103 = 19 days

Impact: -94% battery life! ❌ TERRIBLE
```

### Verdict on Battery Impact

✅ **Option 1 (RTC alarms)**: **Negligible impact** (~4% reduction)
- 303 days → 291 days (still 9+ months)
- **Recommended approach**

❌ **Option 2 (Polling)**: **Catastrophic impact** (94% reduction)
- 303 days → 19 days
- **Do not use**

---

## Recommended Implementation

### 1. Backend Changes

#### Update `/v1/raw7` endpoint to include buzzer schedule

**Response headers:**
```http
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Length: 192000
X-Buzzer-Schedule: 08:00:2:100:100,14:00:3:150:200,20:00:2:100:100

[RAW7 binary data...]
```

**Or use JSON wrapper (if switching to JSON API):**
```json
{
  "image": {
    "url": "/v1/raw7?device=abc",
    "size": 192000
  },
  "buzzer_schedule": [
    {"time": "08:00", "pattern": "2,100,100", "label": "Morning medication"},
    {"time": "14:00", "pattern": "3,150,200", "label": "Afternoon walk"},
    {"time": "20:00", "pattern": "2,100,100", "label": "Evening medication"}
  ],
  "temperature": 72.5,
  "humidity": 45
}
```

#### Generate schedule from todos

```python
# In backend (pseudo-code)
def get_buzzer_schedule(device_id):
    todos = get_active_todos(device_id)
    schedule = []

    for todo in todos:
        if todo.reminder_enabled and todo.due_time:
            # Buzzer 5 minutes before due time
            reminder_time = todo.due_time - timedelta(minutes=5)
            schedule.append({
                "time": reminder_time.strftime("%H:%M"),
                "pattern": "3,100,200",  # 3 beeps
                "label": todo.title
            })

    return schedule
```

### 2. Frontend/Firmware Changes

#### Add RTC alarm management

**New file: `firmware/shared/alarm_manager.h`**
```cpp
#pragma once

#include <Arduino.h>

#define MAX_DAILY_ALARMS 10

struct BuzzerAlarm {
  uint8_t hour;
  uint8_t minute;
  uint8_t beep_count;
  uint16_t beep_on_ms;
  uint16_t beep_off_ms;
  bool active;
};

class AlarmManager {
public:
  void setup();
  void parseBuzzerSchedule(const char* schedule); // Parse HTTP header
  void setAlarms();
  void checkAndTrigger(); // Called on RTC wake
  void clearAll();

private:
  BuzzerAlarm alarms[MAX_DAILY_ALARMS];
  int alarm_count = 0;
};
```

**Implementation:**
```cpp
// Parse schedule from HTTP header
// Format: "08:00:2:100:100,14:00:3:150:200"
void AlarmManager::parseBuzzerSchedule(const char* schedule) {
  alarm_count = 0;

  char* schedule_copy = strdup(schedule);
  char* token = strtok(schedule_copy, ",");

  while (token != NULL && alarm_count < MAX_DAILY_ALARMS) {
    int h, m, count, on_ms, off_ms;
    if (sscanf(token, "%d:%d:%d:%d:%d", &h, &m, &count, &on_ms, &off_ms) == 5) {
      alarms[alarm_count].hour = h;
      alarms[alarm_count].minute = m;
      alarms[alarm_count].beep_count = count;
      alarms[alarm_count].beep_on_ms = on_ms;
      alarms[alarm_count].beep_off_ms = off_ms;
      alarms[alarm_count].active = true;
      alarm_count++;
    }
    token = strtok(NULL, ",");
  }

  free(schedule_copy);
  DEBUG_PRINTF("Parsed %d buzzer alarms\n", alarm_count);
}

void AlarmManager::checkAndTrigger() {
  time_t now;
  struct tm timeinfo;
  time(&now);
  localtime_r(&now, &timeinfo);

  uint8_t current_hour = timeinfo.tm_hour;
  uint8_t current_min = timeinfo.tm_min;

  for (int i = 0; i < alarm_count; i++) {
    if (alarms[i].active &&
        alarms[i].hour == current_hour &&
        alarms[i].minute == current_min) {

      DEBUG_PRINTF("Alarm triggered: %02d:%02d\n", current_hour, current_min);
      playBuzzerPattern(
        alarms[i].beep_count,
        alarms[i].beep_on_ms,
        alarms[i].beep_off_ms
      );

      alarms[i].active = false; // Don't trigger again today
    }
  }
}
```

#### Update main firmware loop

**In `KindDisplay.ino`:**
```cpp
#include "alarm_manager.h"

AlarmManager alarmManager;

void setup() {
  // ... existing setup ...
  alarmManager.setup();
}

void loop() {
  // On wake from deep sleep
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();

  if (wakeup_reason == ESP_SLEEP_WAKEUP_TIMER) {
    // Daily image update
    updateDisplay();

    // Parse buzzer schedule from HTTP response
    const char* schedule = httpClient.getHeader("X-Buzzer-Schedule");
    if (schedule) {
      alarmManager.parseBuzzerSchedule(schedule);
      alarmManager.setAlarms();
    }

    // Sleep until next alarm or daily update
    enterDeepSleepWithAlarms();

  } else if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
    // RTC alarm triggered
    alarmManager.checkAndTrigger();

    // Go back to sleep
    enterDeepSleepWithAlarms();
  }
}

void enterDeepSleepWithAlarms() {
  // Calculate next wake time (earliest of: daily update or next alarm)
  uint64_t daily_update_us = calculateDailyUpdateSleep();
  uint64_t next_alarm_us = alarmManager.getNextAlarmSleep();

  uint64_t sleep_time = min(daily_update_us, next_alarm_us);

  esp_sleep_enable_timer_wakeup(sleep_time);
  esp_deep_sleep_start();
}
```

#### Update HTTP client to capture headers

**In `raw7_decoder.cpp`:**
```cpp
class RAW7Decoder {
public:
  // ... existing methods ...
  const char* getResponseHeader(const char* header_name);

private:
  std::map<String, String> response_headers;
};

void RAW7Decoder::fetch() {
  // ... existing fetch logic ...

  // Capture response headers
  if (http.hasHeader("X-Buzzer-Schedule")) {
    response_headers["X-Buzzer-Schedule"] = http.header("X-Buzzer-Schedule");
  }
}
```

---

## User Experience Flow

### 1. User creates todo in web UI
```
"Morning medication - 8:00 AM - Enable reminder"
```

### 2. Backend generates buzzer schedule
```python
schedule = [
  {"time": "07:55", "pattern": "3,100,200", "label": "Morning medication in 5 min"}
]
```

### 3. Device receives schedule at daily update (1 AM)
```
X-Buzzer-Schedule: 07:55:3:100:200
```

### 4. Device sets RTC alarm for 7:55 AM
```cpp
alarmManager.setAlarms(); // Programs ESP32 RTC
```

### 5. Device wakes at 7:55 AM
```
ESP32 RTC alarm → Wake from deep sleep → Check alarm → Beep 3 times
```

### 6. User hears reminder, takes medication

### 7. Device goes back to sleep until next alarm or daily update

---

## Configuration Options

### Backend Configuration (in todo model)

```python
class Todo:
    title: str
    due_time: datetime
    reminder_enabled: bool = True
    reminder_minutes_before: int = 5  # Beep 5 min before
    beep_pattern: str = "3,100,200"   # 3 beeps, 100ms on, 200ms off
```

### Device Configuration (in `config.h`)

```cpp
// Buzzer settings
#define MAX_DAILY_BUZZER_ALARMS 10
#define BUZZER_DEFAULT_PATTERN "3,100,200"
#define BUZZER_VOLUME 50  // 0-100 (PWM duty cycle for volume control)
```

---

## Testing Checklist

### Backend Testing
- [ ] Generate buzzer schedule from todos
- [ ] Include schedule in HTTP header
- [ ] Handle empty schedule (no todos)
- [ ] Handle max 10 events per day
- [ ] Verify header format

### Firmware Testing
- [ ] Parse buzzer schedule header
- [ ] Set RTC alarms correctly
- [ ] Wake at alarm time
- [ ] Beep with correct pattern
- [ ] Return to sleep after beep
- [ ] Handle multiple alarms per day
- [ ] Handle no alarms (empty schedule)
- [ ] Battery consumption test (should be <10mAh/day increase)

### User Testing
- [ ] Create todo with reminder
- [ ] Verify device beeps at correct time
- [ ] Verify timing accuracy (±1 min acceptable)
- [ ] Test with multiple todos same day
- [ ] Test with no todos
- [ ] Battery life test (1 week minimum)

---

## Future Enhancements

### Smart Snooze
```cpp
// User presses button during beep
if (buttonPressed() during beep) {
  snoozeAlarm(5_minutes); // Beep again in 5 min
}
```

### Progressive Beeping
```cpp
// Beep more urgently if user doesn't respond
if (alarm not acknowledged) {
  wait(2_minutes);
  beep_louder();
  wait(2_minutes);
  beep_even_louder();
}
```

### Buzzer Volume Control
```cpp
// Use PWM for volume control
ledcWrite(BUZZER_CHANNEL, duty_cycle); // 0-255 for volume
```

### Acknowledgment via Button
```cpp
// User presses button to acknowledge
// Backend knows todo was seen
sendAcknowledgment(todo_id, timestamp);
```

---

## Summary

✅ **Recommended: Option 1 (RTC Alarms)**
- Battery impact: **Negligible** (~4% reduction, still 9+ months)
- Implementation: Medium complexity
- User experience: Excellent (accurate, reliable)

✅ **Backend sends schedule via HTTP header**
- Simple integration with existing RAW7 endpoint
- No JSON parsing overhead
- Works offline after daily sync

✅ **Use cases:**
- Medication reminders (2-3x per day)
- Appointment alerts
- Daily routine prompts
- Smart home notifications

**Battery life with buzzer reminders:**
- Without buzzer: ~10 months (303 days)
- With 3 daily beeps: ~9.7 months (291 days)
- **Difference: 12 days** (totally acceptable!)

Ready to implement? I can create the firmware code for alarm management and update the backend integration guide.
