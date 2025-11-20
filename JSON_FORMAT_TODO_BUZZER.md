# JSON Format Specification - Todo with Buzzer Integration

This document defines the JSON format for todo items with buzzer reminder support for reTerminal E1002 devices.

## Overview

Todo items now support buzzer reminders, allowing the reTerminal E1002 to beep at specified times to remind users of upcoming tasks. The buzzer setting is optional and backward-compatible with devices that don't have a buzzer.

## JSON Structure

### Complete Layout JSON with Todo Element

```json
{
  "elements": [
    {
      "kind": "todo",
      "x": 50,
      "y": 300,
      "width": 300,
      "height": 400,
      "opacity": 1,
      "layout": "kids",
      "title": "TODAY'S MISSIONS 🎯",
      "showTime": true,
      "fontSize": 16,
      "fontFamily": "Inter",
      "fontWeight": "400",
      "color": "#000000",
      "textShadowType": "none",
      "textShadowColor": "#000000",
      "textShadowIntensity": 1,
      "items": [
        {
          "emoji": "💊",
          "time": "8:00am",
          "task": "Morning medication",
          "days": ["mon", "tue", "wed", "thu", "fri"],
          "buzzer": true
        },
        {
          "emoji": "🚶",
          "time": "2:00pm",
          "task": "Afternoon walk",
          "days": ["all"],
          "buzzer": true
        },
        {
          "emoji": "💊",
          "time": "8:00pm",
          "task": "Evening medication",
          "days": ["mon", "tue", "wed", "thu", "fri"],
          "buzzer": true
        },
        {
          "emoji": "📚",
          "time": "7:00pm",
          "task": "Reading time",
          "days": ["all"],
          "buzzer": false
        }
      ]
    }
  ]
}
```

## Todo Item Fields

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `emoji` | string | Emoji icon for the task (1-2 characters) | `"💊"` |
| `time` | string | Time of day for the task | `"8:00am"`, `"14:00"` |
| `task` | string | Task description | `"Morning medication"` |
| `days` | array | Days when task applies | `["mon", "tue", "wed"]` or `["all"]` |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `buzzer` | boolean | `false` | Enable buzzer reminder for this task |

## Days Field Values

Valid day values:
- `"all"` - Every day
- `"mon"` - Monday
- `"tue"` - Tuesday
- `"wed"` - Wednesday
- `"thu"` - Thursday
- `"fri"` - Friday
- `"sat"` - Saturday
- `"sun"` - Sunday

**Note**: If `["all"]` is present, it applies to every day regardless of other values.

## Buzzer Field Behavior

### When `buzzer: true`
- Backend generates buzzer schedule for this todo item
- Device (reTerminal E1002) sets RTC alarm
- Device beeps 5 minutes before the task time
- Beep pattern: 3 beeps, 100ms on, 200ms off (default)

### When `buzzer: false` or omitted
- No buzzer reminder generated
- Task still displays on screen
- Works on all devices (reTerminal, XIAO, Waveshare)

### Device Compatibility

| Device | Buzzer Support | Behavior |
|--------|----------------|----------|
| reTerminal E1002 | ✅ Full support | Beeps at scheduled times |
| XIAO EE04 | ❌ No buzzer | Ignores buzzer field |
| Waveshare ESP32 REV3 | ❌ No buzzer | Ignores buzzer field |

## Backend Processing

### 1. Parse Layout JSON

```python
# Example backend code
def process_todo_layout(layout_json):
    elements = layout_json.get('elements', [])

    for element in elements:
        if element.get('kind') == 'todo':
            items = element.get('items', [])
            todo_schedule = []

            for item in items:
                if item.get('buzzer', False) and item.get('time'):
                    # Parse time
                    task_time = parse_time(item['time'])  # e.g., "8:00am" -> datetime

                    # Create buzzer event 5 minutes before
                    reminder_time = task_time - timedelta(minutes=5)

                    todo_schedule.append({
                        'time': reminder_time.strftime('%H:%M'),
                        'pattern': '3,100,200',  # 3 beeps, 100ms on, 200ms off
                        'label': item['task'],
                        'days': item.get('days', ['all'])
                    })

            return todo_schedule
```

### 2. Generate Buzzer Schedule for Device

The backend filters buzzer schedule by current day:

```python
def get_daily_buzzer_schedule(todo_schedule, current_day):
    """
    current_day: 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
    """
    daily_schedule = []

    for event in todo_schedule:
        days = event.get('days', ['all'])

        # Include if 'all' or current day is in the list
        if 'all' in days or current_day in days:
            daily_schedule.append({
                'time': event['time'],
                'pattern': event['pattern']
            })

    return daily_schedule
```

### 3. Send to Device via HTTP Header

```python
def format_buzzer_header(daily_schedule):
    """
    Format: "HH:MM:beeps:on_ms:off_ms,HH:MM:beeps:on_ms:off_ms"
    Example: "07:55:3:100:200,13:55:3:100:200,19:55:3:100:200"
    """
    parts = []
    for event in daily_schedule:
        time_str = event['time']  # "07:55"
        pattern = event['pattern']  # "3,100,200"
        parts.append(f"{time_str}:{pattern}")

    return ','.join(parts)
```

## HTTP Response from Backend

### Image Endpoint with Buzzer Schedule

```http
GET /v1/raw7?device=abc123&temp=72.5&humidity=45

HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Length: 192000
X-Buzzer-Schedule: 07:55:3:100:200,13:55:3:100:200,19:55:3:100:200

[RAW7 binary data...]
```

**Header Format**:
- **Header Name**: `X-Buzzer-Schedule`
- **Format**: `HH:MM:beeps:on_ms:off_ms` (comma-separated)
- **Example**: `07:55:3:100:200,13:55:3:100:200`
  - `07:55` - Time (24-hour format)
  - `3` - Number of beeps
  - `100` - Beep on duration (milliseconds)
  - `200` - Beep off duration (milliseconds)

### Pattern Examples

| Pattern | Description |
|---------|-------------|
| `3,100,200` | 3 short beeps (standard reminder) |
| `5,50,100` | 5 quick beeps (urgent) |
| `2,200,300` | 2 long beeps (gentle reminder) |
| `1,500,0` | 1 long beep (alert) |

## Firmware Processing (reTerminal E1002)

### 1. Parse HTTP Header

```cpp
// In raw7_decoder.cpp
const char* schedule = httpClient.getHeader("X-Buzzer-Schedule");
if (schedule) {
  alarmManager.parseBuzzerSchedule(schedule);
  alarmManager.setAlarms();
}
```

### 2. Set RTC Alarms

```cpp
// In alarm_manager.cpp
void AlarmManager::parseBuzzerSchedule(const char* schedule) {
  // Parse "07:55:3:100:200,13:55:3:100:200"
  // Extract: hour, minute, beep_count, on_ms, off_ms
  // Program ESP32 RTC alarms
}
```

### 3. Wake and Beep

```cpp
// Wake at alarm time
void onWakeFromSleep() {
  if (wakeReason == RTC_ALARM) {
    BuzzerEvent* event = getCurrentEvent();
    playBuzzerPattern(event->beep_count, event->beep_on_ms, event->beep_off_ms);
    enterDeepSleep();
  }
}
```

## Time Format Parsing

The `time` field supports multiple formats:

### Supported Formats

| Format | Example | Parsed As |
|--------|---------|-----------|
| 12-hour with am/pm | `"8:00am"` | 08:00 |
| 12-hour with am/pm | `"2:30pm"` | 14:30 |
| 24-hour | `"14:00"` | 14:00 |
| 24-hour | `"08:30"` | 08:30 |

### Parsing Logic (Backend)

```python
import re
from datetime import datetime

def parse_time(time_str):
    """
    Parse various time formats to datetime
    """
    time_str = time_str.strip().lower()

    # Try 12-hour format with am/pm
    match = re.match(r'(\d{1,2}):(\d{2})(am|pm)', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)

        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        return datetime.now().replace(hour=hour, minute=minute, second=0)

    # Try 24-hour format
    match = re.match(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return datetime.now().replace(hour=hour, minute=minute, second=0)

    raise ValueError(f"Invalid time format: {time_str}")
```

## Examples

### Example 1: Medication Reminders

```json
{
  "items": [
    {
      "emoji": "💊",
      "time": "8:00am",
      "task": "Morning medication",
      "days": ["all"],
      "buzzer": true
    },
    {
      "emoji": "💊",
      "time": "8:00pm",
      "task": "Evening medication",
      "days": ["all"],
      "buzzer": true
    }
  ]
}
```

**Generated schedule** (for Monday):
```
X-Buzzer-Schedule: 07:55:3:100:200,19:55:3:100:200
```

### Example 2: Weekday Only Reminders

```json
{
  "items": [
    {
      "emoji": "🏫",
      "time": "7:00am",
      "task": "School preparation",
      "days": ["mon", "tue", "wed", "thu", "fri"],
      "buzzer": true
    },
    {
      "emoji": "🎮",
      "time": "5:00pm",
      "task": "Free time",
      "days": ["sat", "sun"],
      "buzzer": false
    }
  ]
}
```

**Generated schedule** (for Monday):
```
X-Buzzer-Schedule: 06:55:3:100:200
```

**Generated schedule** (for Saturday):
```
X-Buzzer-Schedule:
(empty - no buzzer events)
```

### Example 3: Mixed Buzzer Settings

```json
{
  "items": [
    {
      "emoji": "💊",
      "time": "8:00am",
      "task": "Medication",
      "days": ["all"],
      "buzzer": true
    },
    {
      "emoji": "🥗",
      "time": "12:00pm",
      "task": "Lunch",
      "days": ["all"],
      "buzzer": false
    },
    {
      "emoji": "🚶",
      "time": "3:00pm",
      "task": "Walk",
      "days": ["all"],
      "buzzer": true
    }
  ]
}
```

**Generated schedule**:
```
X-Buzzer-Schedule: 07:55:3:100:200,14:55:3:100:200
```

(Note: Lunch at 12:00pm has `buzzer: false`, so it's not included)

## Validation Rules

### Backend Validation

```python
def validate_todo_item(item):
    # Required fields
    if not item.get('emoji'):
        raise ValueError("emoji is required")
    if not item.get('time'):
        raise ValueError("time is required")
    if not item.get('task'):
        raise ValueError("task is required")
    if not item.get('days'):
        raise ValueError("days is required")

    # Validate emoji length
    if len(item['emoji']) > 2:
        raise ValueError("emoji must be 1-2 characters")

    # Validate days
    valid_days = {'all', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
    for day in item['days']:
        if day not in valid_days:
            raise ValueError(f"Invalid day: {day}")

    # Validate time format
    try:
        parse_time(item['time'])
    except Exception as e:
        raise ValueError(f"Invalid time format: {item['time']}")

    # Validate buzzer (optional boolean)
    if 'buzzer' in item and not isinstance(item['buzzer'], bool):
        raise ValueError("buzzer must be a boolean")

    return True
```

## Backward Compatibility

### With Older Layouts (No Buzzer Field)

```json
{
  "items": [
    {
      "emoji": "💊",
      "time": "8:00am",
      "task": "Morning medication",
      "days": ["all"]
      // No buzzer field - defaults to false
    }
  ]
}
```

Backend treats missing `buzzer` field as `false`.

### With Older Firmware (No Buzzer Support)

Devices without buzzer hardware (XIAO EE04, Waveshare ESP32 REV3) simply ignore the `X-Buzzer-Schedule` header.

## Testing

### Test Cases

1. **All buzzer enabled**
   ```json
   {"buzzer": true, "time": "8:00am", ...} → Expect alarm at 07:55
   ```

2. **All buzzer disabled**
   ```json
   {"buzzer": false, "time": "8:00am", ...} → Expect no alarm
   ```

3. **Mixed buzzer settings**
   ```json
   [
     {"buzzer": true, "time": "8:00am", ...},
     {"buzzer": false, "time": "12:00pm", ...},
     {"buzzer": true, "time": "8:00pm", ...}
   ] → Expect 2 alarms: 07:55, 19:55
   ```

4. **Day filtering**
   ```json
   {"buzzer": true, "days": ["mon", "wed", "fri"], ...}
   → On Monday: alarm set
   → On Tuesday: no alarm
   ```

5. **Time format parsing**
   ```json
   "8:00am" → 08:00
   "2:30pm" → 14:30
   "14:00" → 14:00
   ```

## Summary

- **Buzzer field**: Optional boolean, defaults to `false`
- **Backend**: Filters todos with `buzzer: true`, generates schedule
- **HTTP header**: `X-Buzzer-Schedule` in format `HH:MM:beeps:on_ms:off_ms`
- **Firmware**: Parses header, sets RTC alarms, wakes to beep
- **Compatibility**: Backward compatible, ignored by non-buzzer devices
- **Battery impact**: Minimal (~4% reduction for 3 daily beeps)

## See Also

- `firmware/TODO_BUZZER_INTEGRATION.md` - Firmware implementation details
- `firmware/reterminal-e1002/README.md` - reTerminal E1002 documentation
- `firmware/ARCHITECTURE_DECISIONS.md` - Design rationale
