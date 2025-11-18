#pragma once

// Pin definitions for ESP32 + Spectra-6 wiring. Keep these values in sync
// with firmware/hardware_pins.md so documentation and firmware reference the
// same physical connections.

// EPD (Spectra-6) SPI interface
// Pin assignments from original device firmware
#define EPD_BUSY    25
#define EPD_RST     26
#define EPD_DC      27
#define EPD_CS      33
#define EPD_CLK     13
#define EPD_MOSI    14

// SD Card SPI interface
// Pin assignments match the board silkscreen labels
// No conflicts with EPD - completely separate pins
#define SD_CS       5   // CS pin (as labeled on board)
#define SD_MOSI     23  // CMD pin (as labeled on board)
#define SD_MISO     19  // DAT pin (as labeled on board)
#define SD_CLK      18  // CLK pin (as labeled on board)

// Optional peripherals
#define BEEP_PIN    12
// Note: GPIO25, GPIO26, GPIO33, GPIO14 are used by EPD (BUSY, RST, CS, MOSI)
