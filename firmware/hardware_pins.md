# ESP32 Pin Reference

These pin assignments are shared by both the documentation and the firmware.
The actual firmware constants live in [`hardware_pins.h`](./hardware_pins.h)
and `config.h` simply includes that header to pick up the same values. Update
both files together if your board revision requires a different wiring map.

## Display (EPD Adapter → ESP32)

Pin assignments from original device firmware.

| Signal | ESP32 GPIO | Notes |
|--------|------------|-------|
| BUSY   | GPIO25     | Display busy indicator |
| RST    | GPIO26     | Hardware reset |
| DC     | GPIO27     | Data/Command select |
| CS     | GPIO33     | Chip select |
| CLK    | GPIO13     | SPI clock |
| MOSI   | GPIO14     | SPI MOSI (DIN) |

## SD Card (as labeled on board silkscreen)

| Signal | ESP32 GPIO | Notes |
|--------|------------|-------|
| CS     | GPIO5      | Board label: CS |
| MOSI   | GPIO23     | Board label: CMD |
| MISO   | GPIO19     | Board label: DAT |
| CLK    | GPIO18     | Board label: CLK |

**NOTE:** EPD and SD use completely separate pins - no conflicts. Both can operate independently.

## Optional / Expansion Pins

| Label    | ESP32 GPIO | Notes |
|----------|------------|-------|
| BUZZER   | GPIO12     | Buzzer / speaker |

**Note:** GPIO25, GPIO26, GPIO33, GPIO14 are used by the EPD and are no longer available as expansion pins.
