#ifndef TEXT_WELCOME_H
#define TEXT_WELCOME_H

#include <Arduino.h>
#include "config.h"
#include "display_driver.h"

// ============================================================
// Text-Based Welcome Screen Generator
// ============================================================
// Generates a simple, memory-efficient welcome screen with
// text-like blocks and colored sections for setup instructions
// ============================================================

class TextWelcome {
public:
    // Generate and display a simple text-based welcome screen
    static bool showWelcomeScreen(SpectraDisplay& display);

private:
    // Helper to draw a filled rectangle directly to RAW7 buffer
    static void fillRect(uint8_t* raw7Buffer, int x, int y, int w, int h, uint8_t color);

    // Helper to draw a text block (simulated with rectangles)
    static void drawTextBlock(uint8_t* raw7Buffer, int x, int y, int w, int h, uint8_t bgColor, uint8_t borderColor);

    // Set a single pixel in the RAW7 buffer
    static void setPixel(uint8_t* raw7Buffer, int x, int y, uint8_t color);
};

#endif // TEXT_WELCOME_H
