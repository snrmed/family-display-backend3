#pragma once

// Pin definitions for ESP32 + Spectra-6 wiring. Keep these values in sync
// with firmware/hardware_pins.md so documentation and firmware reference the
// same physical connections.

// EPD (Spectra-6) SPI interface
#define EPD_BUSY    4
#define EPD_RST     16
#define EPD_DC      23
#define EPD_CS      5
#define EPD_CLK     18
#define EPD_MOSI    19

// SD Card (shares the same VSPI bus as the display)
#define SD_CS       13
#define SD_MOSI     19
#define SD_MISO     27
#define SD_CLK      18

// Optional peripherals
#define BEEP_PIN    12
#define GPIO25      25
#define GPIO26      26
#define GPIO33      33
#define GPIO14      14
