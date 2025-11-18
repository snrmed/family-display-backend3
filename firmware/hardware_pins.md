# ESP32 Pin Reference

These pin assignments are shared by both the documentation and the firmware.
The actual firmware constants live in [`hardware_pins.h`](./hardware_pins.h)
and `config.h` simply includes that header to pick up the same values. Update
both files together if your board revision requires a different wiring map.

## Display (EPD Adapter → ESP32)

| Signal | ESP32 GPIO | Notes |
|--------|------------|-------|
| BUSY   | GPIO4      | Display busy indicator |
| RST    | GPIO16     | Hardware reset |
| DC     | GPIO23     | Data/Command select |
| CS     | GPIO5      | Chip select |
| SCK    | GPIO18     | Shared VSPI clock |
| MOSI   | GPIO19     | Shared VSPI MOSI |

## SD Card (shares the same VSPI bus)

| Signal | ESP32 GPIO | Notes |
|--------|------------|-------|
| CS     | GPIO13     | Dedicated SD chip select |
| MOSI   | GPIO19     | Shared with display |
| MISO   | GPIO27     | VSPI MISO |
| SCK    | GPIO18     | Shared VSPI clock |

## Optional / Expansion Pins

| Label    | ESP32 GPIO | Notes |
|----------|------------|-------|
| BUZZER   | GPIO12     | Buzzer / speaker |
| AUX1     | GPIO25     | Spare GPIO |
| AUX2     | GPIO26     | Spare GPIO |
| AUX3     | GPIO33     | Spare GPIO |
| AUX4     | GPIO14     | Spare GPIO |
