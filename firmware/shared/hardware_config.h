#pragma once

// Multi-device hardware configuration system
// Supports: reTerminal E1002, XIAO ePaper EE04, Waveshare ESP32 REV3, Original ESP32 dev board

// Device detection and selection
// Uncomment ONE of these to manually select device, or leave all commented for auto-detection
// #define DEVICE_RETERMINAL_E1002
// #define DEVICE_XIAO_EE04
// #define DEVICE_WAVESHARE_ESP32_REV3
// #define DEVICE_ORIGINAL_ESP32

// Auto-detect device if not manually specified
#if !defined(DEVICE_RETERMINAL_E1002) && !defined(DEVICE_XIAO_EE04) && !defined(DEVICE_WAVESHARE_ESP32_REV3) && !defined(DEVICE_ORIGINAL_ESP32)
  // Auto-detection logic based on ESP32 variant
  #if defined(CONFIG_IDF_TARGET_ESP32S3)
    // ESP32-S3 detected - need to distinguish between reTerminal and XIAO
    // Check for unique hardware features
    #define DEVICE_AUTO_DETECT
    // Default to reTerminal E1002 for ESP32-S3 (can be overridden at runtime)
    #define DEVICE_RETERMINAL_E1002
  #else
    // ESP32 classic - could be Waveshare or original dev board
    // Default to Waveshare ESP32 REV3 (more common)
    #define DEVICE_WAVESHARE_ESP32_REV3
  #endif
#endif

// =============================================================================
// Device-specific pin configurations
// =============================================================================

#if defined(DEVICE_RETERMINAL_E1002)
  // -------------------------------------------------------------------------
  // Seeed reTerminal E1002 Configuration
  // ESP32-S3, Spectra 6 display, 2000mAh battery
  // -------------------------------------------------------------------------

  #define DEVICE_NAME "reTerminal E1002"
  #define DEVICE_HAS_TEMP_SENSOR  true
  #define DEVICE_HAS_MICROPHONE   true
  #define DEVICE_HAS_BUZZER       true
  #define DEVICE_HAS_SD_CARD      true  // Shares SPI with display
  #define DEVICE_BATTERY_CAPACITY 2000  // mAh

  // Display (Spectra 6) - SPI interface
  #define EPD_CLK     7
  #define EPD_MOSI    9
  #define EPD_MISO    8   // Used by SD card
  #define EPD_CS      10
  #define EPD_DC      11
  #define EPD_RST     12
  #define EPD_BUSY    13

  // SD Card - shares SPI bus with display
  #define SD_CLK      7   // Shared with EPD_CLK
  #define SD_MOSI     9   // Shared with EPD_MOSI
  #define SD_MISO     8
  #define SD_CS       -1  // TODO: Find SD CS pin from schematic

  // Buttons
  #define BUTTON_GREEN  3   // Wake button
  #define BUTTON_WHITE  4   // User button
  #define BUTTON_CENTER BUTTON_GREEN  // Alias for compatibility

  // Battery monitoring
  #define BATTERY_ADC_PIN    1
  #define BATTERY_ENABLE_PIN 21
  #define BATTERY_ADC_CHANNEL ADC1_CHANNEL_0

  // Temperature & Humidity Sensor (SHT40)
  #define I2C_SDA     19
  #define I2C_SCL     20
  #define SHT40_ADDR  0x44

  // Audio
  #define BUZZER_PIN       45
  #define MIC_POWER_PIN    38
  #define MIC_BCLK_PIN     42
  #define MIC_DATA_PIN     41

  // LED (if present)
  #define LED_STATUS_PIN   -1  // TODO: Verify if LED exists

  // UART (Default ESP32-S3)
  #define UART_TX     43
  #define UART_RX     44

#elif defined(DEVICE_XIAO_EE04)
  // -------------------------------------------------------------------------
  // Seeed XIAO ePaper Display Board EE04 Configuration
  // ESP32-S3 Plus, Spectra 6 display support
  // -------------------------------------------------------------------------

  #define DEVICE_NAME "XIAO ePaper EE04"
  #define DEVICE_HAS_TEMP_SENSOR  false
  #define DEVICE_HAS_MICROPHONE   false
  #define DEVICE_HAS_BUZZER       false
  #define DEVICE_HAS_SD_CARD      true  // Shares SPI with display
  #define DEVICE_BATTERY_CAPACITY 1000  // Typical for XIAO (user-provided)
  #define DEVICE_HAS_FONT_CHIP    true  // GT32L32S0140

  // Display (Spectra 6) - SPI interface
  #define EPD_CLK     7
  #define EPD_MOSI    9
  #define EPD_MISO    -1  // Not used for display
  #define EPD_CS      44
  #define EPD_DC      10
  #define EPD_RST     38
  #define EPD_BUSY    4

  // SD Card - shares SPI bus with display
  #define SD_CLK      7   // Shared with EPD_CLK
  #define SD_MOSI     9   // Shared with EPD_MOSI
  #define SD_MISO     -1  // TODO: Verify SD MISO pin
  #define SD_CS       -1  // TODO: Find SD CS pin from schematic

  // Buttons (3 user buttons + 1 reset)
  #define BUTTON_KEY0   2
  #define BUTTON_KEY1   3
  #define BUTTON_KEY2   5
  #define BUTTON_CENTER BUTTON_KEY0  // Alias for compatibility

  // Battery monitoring
  #define BATTERY_ADC_PIN    1
  #define BATTERY_ENABLE_PIN 6
  #define BATTERY_ADC_CHANNEL ADC1_CHANNEL_0

  // Font chip (GT32L32S0140) - SPI interface
  #define FONT_CS     -1  // TODO: Find font chip CS pin

  // No temperature sensor
  #define I2C_SDA     -1
  #define I2C_SCL     -1

  // No audio peripherals
  #define BUZZER_PIN       -1
  #define MIC_POWER_PIN    -1

  // LED (if present)
  #define LED_STATUS_PIN   -1  // TODO: Verify if LED exists

#elif defined(DEVICE_WAVESHARE_ESP32_REV3)
  // -------------------------------------------------------------------------
  // Waveshare e-Paper ESP32 Driver Board Universal REV3 Configuration
  // ESP32 classic, universal e-paper driver for various displays
  // -------------------------------------------------------------------------

  #define DEVICE_NAME "Waveshare ESP32 REV3"
  #define DEVICE_HAS_TEMP_SENSOR  false
  #define DEVICE_HAS_MICROPHONE   false
  #define DEVICE_HAS_BUZZER       false
  #define DEVICE_HAS_SD_CARD      false  // Can be added but not standard
  #define DEVICE_BATTERY_CAPACITY 1000  // User-provided battery

  // Display - SPI interface (supports multiple Waveshare panels)
  // Pin mappings from Waveshare documentation
  #define EPD_CLK     13
  #define EPD_MOSI    14
  #define EPD_MISO    19  // MISO for SPI
  #define EPD_CS      15  // Different from original! (was 33)
  #define EPD_DC      27
  #define EPD_RST     26
  #define EPD_BUSY    25

  // SD Card (optional - not standard on this board)
  #define SD_CLK      18
  #define SD_MOSI     23
  #define SD_MISO     19
  #define SD_CS       5

  // Buttons (typically not present on driver board)
  #define BUTTON_CENTER   -1  // No buttons on board

  // Battery monitoring (not built-in)
  #define BATTERY_ADC_PIN    -1
  #define BATTERY_ENABLE_PIN -1
  #define BATTERY_ADC_CHANNEL ADC1_CHANNEL_0

  // No temperature sensor
  #define I2C_SDA     -1
  #define I2C_SCL     -1

  // No buzzer
  #define BUZZER_PIN  -1

  // No microphone
  #define MIC_POWER_PIN -1

  // LED (typically GPIO2 on ESP32)
  #define LED_STATUS_PIN 2

#else  // DEVICE_ORIGINAL_ESP32
  // -------------------------------------------------------------------------
  // Original ESP32 Development Board Configuration
  // ESP32 classic, Spectra 6 display
  // -------------------------------------------------------------------------

  #define DEVICE_NAME "ESP32 Dev Board"
  #define DEVICE_HAS_TEMP_SENSOR  false
  #define DEVICE_HAS_MICROPHONE   false
  #define DEVICE_HAS_BUZZER       true
  #define DEVICE_HAS_SD_CARD      true
  #define DEVICE_BATTERY_CAPACITY 1000  // Varies by user battery

  // Display (Spectra 6) - SPI interface
  #define EPD_CLK     13
  #define EPD_MOSI    14
  #define EPD_MISO    -1  // Not used for display
  #define EPD_CS      33
  #define EPD_DC      27
  #define EPD_RST     26
  #define EPD_BUSY    25

  // SD Card - separate SPI bus
  #define SD_CLK      18
  #define SD_MOSI     23
  #define SD_MISO     19
  #define SD_CS       5

  // Buttons (rotary switch with center press)
  #define BUTTON_ROTARY_A 34
  #define BUTTON_ROTARY_B 35
  #define BUTTON_CENTER   BUTTON_ROTARY_A  // Center press on rotary

  // Battery monitoring
  #define BATTERY_ADC_PIN    -1  // Not implemented on original
  #define BATTERY_ENABLE_PIN -1
  #define BATTERY_ADC_CHANNEL ADC1_CHANNEL_0

  // No temperature sensor
  #define I2C_SDA     -1
  #define I2C_SCL     -1

  // Buzzer
  #define BUZZER_PIN  12

  // No microphone
  #define MIC_POWER_PIN -1

  // LED (if present)
  #define LED_STATUS_PIN -1

#endif

// =============================================================================
// Common display configuration (same for all devices using Spectra 6)
// =============================================================================

#define EPD_WIDTH   800
#define EPD_HEIGHT  480
#define EPD_PANEL_TYPE "Spectra-6"
#define EPD_COLOR_MODE 7  // 7-color mode

// =============================================================================
// Runtime device information
// =============================================================================

struct DeviceInfo {
  const char* name;
  bool has_temp_sensor;
  bool has_microphone;
  bool has_buzzer;
  bool has_sd_card;
  bool has_font_chip;
  uint16_t battery_capacity_mah;

  // Pin mappings
  struct {
    int8_t clk, mosi, miso, cs, dc, rst, busy;
  } epd;

  struct {
    int8_t clk, mosi, miso, cs;
  } sd;

  struct {
    int8_t center;
    int8_t button1;
    int8_t button2;
  } buttons;

  struct {
    int8_t adc_pin;
    int8_t enable_pin;
    uint8_t adc_channel;
  } battery;

  struct {
    int8_t sda, scl;
    uint8_t addr;
  } i2c;

  struct {
    int8_t buzzer;
    int8_t mic_power;
    int8_t mic_bclk;
    int8_t mic_data;
  } audio;
};

// Get current device configuration
inline DeviceInfo getDeviceInfo() {
  DeviceInfo info;

  info.name = DEVICE_NAME;
  info.has_temp_sensor = DEVICE_HAS_TEMP_SENSOR;
  info.has_microphone = DEVICE_HAS_MICROPHONE;
  info.has_buzzer = DEVICE_HAS_BUZZER;
  info.has_sd_card = DEVICE_HAS_SD_CARD;
  #ifdef DEVICE_HAS_FONT_CHIP
  info.has_font_chip = DEVICE_HAS_FONT_CHIP;
  #else
  info.has_font_chip = false;
  #endif
  info.battery_capacity_mah = DEVICE_BATTERY_CAPACITY;

  // EPD pins
  info.epd.clk = EPD_CLK;
  info.epd.mosi = EPD_MOSI;
  info.epd.miso = EPD_MISO;
  info.epd.cs = EPD_CS;
  info.epd.dc = EPD_DC;
  info.epd.rst = EPD_RST;
  info.epd.busy = EPD_BUSY;

  // SD pins
  info.sd.clk = SD_CLK;
  info.sd.mosi = SD_MOSI;
  info.sd.miso = SD_MISO;
  info.sd.cs = SD_CS;

  // Button pins
  info.buttons.center = BUTTON_CENTER;
  #if defined(DEVICE_XIAO_EE04)
  info.buttons.button1 = BUTTON_KEY1;
  info.buttons.button2 = BUTTON_KEY2;
  #elif defined(DEVICE_ORIGINAL_ESP32)
  info.buttons.button1 = BUTTON_ROTARY_A;
  info.buttons.button2 = BUTTON_ROTARY_B;
  #else
  info.buttons.button1 = BUTTON_WHITE;
  info.buttons.button2 = -1;
  #endif

  // Battery pins
  info.battery.adc_pin = BATTERY_ADC_PIN;
  info.battery.enable_pin = BATTERY_ENABLE_PIN;
  info.battery.adc_channel = BATTERY_ADC_CHANNEL;

  // I2C pins
  info.i2c.sda = I2C_SDA;
  info.i2c.scl = I2C_SCL;
  #ifdef SHT40_ADDR
  info.i2c.addr = SHT40_ADDR;
  #else
  info.i2c.addr = 0;
  #endif

  // Audio pins
  #ifdef BUZZER_PIN
  info.audio.buzzer = BUZZER_PIN;
  #else
  info.audio.buzzer = -1;
  #endif

  #ifdef MIC_POWER_PIN
  info.audio.mic_power = MIC_POWER_PIN;
  #else
  info.audio.mic_power = -1;
  #endif

  #ifdef MIC_BCLK_PIN
  info.audio.mic_bclk = MIC_BCLK_PIN;
  #else
  info.audio.mic_bclk = -1;
  #endif

  #ifdef MIC_DATA_PIN
  info.audio.mic_data = MIC_DATA_PIN;
  #else
  info.audio.mic_data = -1;
  #endif

  return info;
}

// Helper to print device info at startup
inline void printDeviceInfo() {
  DeviceInfo info = getDeviceInfo();
  Serial.println("===========================================");
  Serial.print("Device: ");
  Serial.println(info.name);
  Serial.println("===========================================");
  Serial.printf("Temperature Sensor: %s\n", info.has_temp_sensor ? "Yes" : "No");
  Serial.printf("Microphone: %s\n", info.has_microphone ? "Yes" : "No");
  Serial.printf("Buzzer: %s\n", info.has_buzzer ? "Yes" : "No");
  Serial.printf("SD Card: %s\n", info.has_sd_card ? "Yes" : "No");
  Serial.printf("Font Chip: %s\n", info.has_font_chip ? "Yes" : "No");
  Serial.printf("Battery Capacity: %d mAh\n", info.battery_capacity_mah);
  Serial.println("-------------------------------------------");
  Serial.printf("EPD Pins: CLK=%d MOSI=%d CS=%d DC=%d RST=%d BUSY=%d\n",
    info.epd.clk, info.epd.mosi, info.epd.cs, info.epd.dc, info.epd.rst, info.epd.busy);
  Serial.printf("Battery: ADC=%d EN=%d\n", info.battery.adc_pin, info.battery.enable_pin);
  Serial.printf("Buttons: Center=%d\n", info.buttons.center);
  Serial.println("===========================================");
}
