// ============================================================================
// Hardware pinout for my 7.3" Spectra-6 (E6) ESP32 e-ink dev board
// Board: "ESP32墨水屏开发板 节电版" with 7-colour GoodDisplay/Waveshare-style panel
// Built-ins: 7-colour e-ink, micro-SD, USB-C, LiPo charger
// ============================================================================
//
// -------- Shared SPI bus (display + SD) -------------------------------------
// NOTE: These are CONFIRMED from silkscreen next to the micro-SD socket:
//
//   CS  / 5   -> SD card chip-select (GPIO5)
//   CMD / 23  -> SD card MOSI      (GPIO23)
//   CLK / 18  -> SPI clock         (GPIO18)
//   DAT0 / 19 -> SD card MISO      (GPIO19)
//
// We also use the same SCK/MOSI for the e-ink display (write-only), no MISO.
// So SPI bus for both devices is:
//
//   SPI_SCK   = GPIO18
//   SPI_MOSI  = GPIO23
//   SPI_MISO  = GPIO19   // SD only
//
// -------- SD card -----------------------------------------------------------
//
//   SD_CS     = GPIO5     // from "CS/5" on PCB
//   SD_MOSI   = GPIO23    // "CMD/23"
//   SD_MISO   = GPIO19    // "DAT0/19"
//   SD_SCK    = GPIO18    // "CLK/18"
//
// In code, initialise SPI with these pins and mount SD with SD_CS = 5.
//
// -------- E-ink display (7-colour / Spectra-6) ------------------------------
//
// Uses the same SPI bus (CLK/MOSI) as SD, write-only.
// Control pins are from vendor docs / existing firmware for this board:
//
//   EPD_BUSY  = GPIO4     // busy line from panel
//   EPD_RST   = GPIO16    // reset line to panel
//   EPD_DC    = GPIO17    // data/command select
//   EPD_CS    = GPIO5     // *** ASSUMPTION: same CS as SD on this board ***
//
// If code needs separate CS for SD vs e-ink and this causes issues,
// try changing EPD_CS to a free GPIO (e.g. 15) and patching wiring or
// check with a continuity tester + schematic.
//
// -------- Power / battery ---------------------------------------------------
//
//   BAT_CONN  = 2-pin JST at top-right (goes into charger + regulator).
//   You generally do NOT talk to this via GPIO; it just powers the board.
//
// Some boards expose a battery ADC sense pin, usually something like:
//
//   BAT_ADC   = GPIO35    // *** IF exposed, can read battery voltage ***
//
// but this one may or may not break it out – treat as optional.
//
// -------- USB / serial ------------------------------------------------------
//
// Standard ESP32 UART0 for programming + logs:
//
//   USB-to-UART bridge -> ESP32:
//     UART_TX0 = GPIO1
//     UART_RX0 = GPIO3
//
// Use Serial.begin(115200) on these for debug.
//
// -------- Buttons (typical ESP32 layout) ------------------------------------
//
//   BOOT / FLASH button : GPIO0     // hold LOW on reset for flash mode
//   RESET button         : EN pin   // resets chip, not a normal GPIO
//
// If firmware needs a user button, BOOT (GPIO0) is usually what you read.
//
// -------- On-board LED (if present) -----------------------------------------
//
// Some revisions have an on-board LED on one of these pins:
//
//   LED_BUILTIN = GPIO2 or GPIO13   // *** BOARD-DEPENDENT, test with blink ***
//
// Try toggling GPIO2 and GPIO13; whichever lights the LED is the right one.
//
// -------- Free / general GPIOs ---------------------------------------------
//
// All other standard ESP32 GPIOs not used above (e.g. 12, 13, 14, 15, 21, 22,
// 25, 26, 27, 32, 33, 34, 35, 36, 39) are *likely* available on headers or
// test pads, depending on the board revision.
//
// You can safely assume the following are FREE for sensors/buttons *unless*
// the schematic says otherwise:
//
//   GPIO12, GPIO13, GPIO14, GPIO15,
//   GPIO21, GPIO22,
//   GPIO25, GPIO26, GPIO27,
//   GPIO32, GPIO33,
//   GPIO34, GPIO35, GPIO36, GPIO39 (input-only on standard ESP32).
//
// ============================================================================
// TL;DR for Codex:
//
//   SPI:     SCK=18, MOSI=23, MISO=19
//   SD:      CS=5
//   E-ink:   BUSY=4, RST=16, DC=17, CS=5 (assumed), uses SCK/MOSI above
//   UART0:   TX=1, RX=3
//   BOOT:    0, RESET=en
//   Free GPIOs: 12,13,14,15,21,22,25,26,27,32,33,34,35,36,39 (check per use)
// ============================================================================
