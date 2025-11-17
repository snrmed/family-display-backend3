#include "text_welcome.h"

bool TextWelcome::showWelcomeScreen(SpectraDisplay& display) {
    DEBUG_PRINTLN("Welcome: Generating text-based welcome screen");

    // Allocate RAW7 buffer directly (192KB)
    uint8_t* raw7Buffer = (uint8_t*)malloc(RAW7_SIZE);
    if (!raw7Buffer) {
        DEBUG_PRINTLN("Welcome: RAW7 buffer allocation failed");
        return false;
    }

    // Initialize to white (0x00 = two white pixels)
    memset(raw7Buffer, 0x00, RAW7_SIZE);

    // === LAYOUT DESIGN ===
    // Screen: 800x480
    // - Top bar (0-100): Blue header with "Kin:D" branding
    // - Main area (100-480): Instructions in colored sections

    // === TOP BAR (Blue) ===
    fillRect(raw7Buffer, 0, 0, 800, 100, EPD_BLUE);

    // Add white "Kin:D" text placeholder (large rectangle)
    fillRect(raw7Buffer, 300, 25, 200, 50, EPD_WHITE);

    // === INSTRUCTION SECTIONS ===
    int sectionY = 120;
    int sectionHeight = 60;
    int sectionSpacing = 10;

    // Section 1: "Connect to WiFi: KIND-Setup"
    // Orange background with white text area
    fillRect(raw7Buffer, 50, sectionY, 700, sectionHeight, EPD_ORANGE);
    drawTextBlock(raw7Buffer, 70, sectionY + 10, 660, 40, EPD_WHITE, EPD_BLACK);

    sectionY += sectionHeight + sectionSpacing;

    // Section 2: "Password: kind1234"
    // Yellow background with black text area
    fillRect(raw7Buffer, 50, sectionY, 700, sectionHeight, EPD_YELLOW);
    drawTextBlock(raw7Buffer, 70, sectionY + 10, 660, 40, EPD_WHITE, EPD_BLACK);

    sectionY += sectionHeight + sectionSpacing;

    // Section 3: "Open browser to any website"
    // Green background with white text area
    fillRect(raw7Buffer, 50, sectionY, 700, sectionHeight, EPD_GREEN);
    drawTextBlock(raw7Buffer, 70, sectionY + 10, 660, 40, EPD_WHITE, EPD_BLACK);

    sectionY += sectionHeight + sectionSpacing;

    // Section 4: "Follow setup instructions"
    // Red background with white text area
    fillRect(raw7Buffer, 50, sectionY, 700, sectionHeight, EPD_RED);
    drawTextBlock(raw7Buffer, 70, sectionY + 10, 660, 40, EPD_WHITE, EPD_BLACK);

    // === FOOTER ===
    // Blue bar at bottom with "makeasmile.com" hint
    fillRect(raw7Buffer, 0, 420, 800, 60, EPD_BLUE);
    fillRect(raw7Buffer, 250, 435, 300, 30, EPD_WHITE);

    // === DISPLAY ===
    DEBUG_PRINTLN("Welcome: Displaying screen");
    display.displayRAW7(raw7Buffer, RAW7_SIZE);
    display.powerOff();

    // Clean up
    free(raw7Buffer);
    DEBUG_PRINTLN("Welcome: Screen displayed successfully");

    return true;
}

void TextWelcome::fillRect(uint8_t* raw7Buffer, int x, int y, int w, int h, uint8_t color) {
    // Fill a rectangle with the specified color in RAW7 format
    for (int py = y; py < y + h; py++) {
        if (py < 0 || py >= DISPLAY_HEIGHT) continue;

        for (int px = x; px < x + w; px++) {
            if (px < 0 || px >= DISPLAY_WIDTH) continue;

            setPixel(raw7Buffer, px, py, color);
        }
    }
}

void TextWelcome::drawTextBlock(uint8_t* raw7Buffer, int x, int y, int w, int h, uint8_t bgColor, uint8_t borderColor) {
    // Draw a text block (filled rectangle with border)
    // This simulates a text area since we don't have a font library

    // Fill background
    fillRect(raw7Buffer, x, y, w, h, bgColor);

    // Draw border (2 pixels thick)
    for (int i = 0; i < 2; i++) {
        // Top border
        fillRect(raw7Buffer, x + i, y + i, w - i * 2, 1, borderColor);
        // Bottom border
        fillRect(raw7Buffer, x + i, y + h - 1 - i, w - i * 2, 1, borderColor);
        // Left border
        fillRect(raw7Buffer, x + i, y + i, 1, h - i * 2, borderColor);
        // Right border
        fillRect(raw7Buffer, x + w - 1 - i, y + i, 1, h - i * 2, borderColor);
    }
}

void TextWelcome::setPixel(uint8_t* raw7Buffer, int x, int y, uint8_t color) {
    // Set a single pixel in RAW7 format
    // RAW7: 2 pixels per byte (high nibble = first pixel, low nibble = second pixel)

    if (x < 0 || x >= DISPLAY_WIDTH || y < 0 || y >= DISPLAY_HEIGHT) {
        return;
    }

    // Calculate byte index and pixel position within byte
    int pixelIndex = y * DISPLAY_WIDTH + x;
    int byteIndex = pixelIndex / 2;
    bool isFirstPixel = (pixelIndex % 2) == 0;

    // Read current byte
    uint8_t currentByte = raw7Buffer[byteIndex];

    // Update the appropriate nibble
    if (isFirstPixel) {
        // High nibble (first pixel)
        raw7Buffer[byteIndex] = (color << 4) | (currentByte & 0x0F);
    } else {
        // Low nibble (second pixel)
        raw7Buffer[byteIndex] = (currentByte & 0xF0) | (color & 0x0F);
    }
}
