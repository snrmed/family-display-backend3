#ifndef QR_DISPLAY_H
#define QR_DISPLAY_H

#include <Arduino.h>
#include "display_driver.h"
#include "config.h"

// ============================================================
// QR Code Display for Setup
// ============================================================
// Shows QR code + branding on first boot
// QR code points to http://192.168.4.1 (setup portal)
// ============================================================

class QRDisplay {
public:
    // Display setup screen with QR code on e-ink
    static void showSetupScreen(SpectraDisplay& display);

private:
    // Render QR code bitmap (simple version)
    static void renderQR(SpectraDisplay& display, const char* url, int x, int y, int scale);

    // Draw text on display (simple bitmap font)
    static void drawText(uint8_t* buffer, const char* text, int x, int y, uint8_t color);

    // Draw a filled rectangle
    static void drawRect(uint8_t* buffer, int x, int y, int w, int h, uint8_t color);
};

#endif // QR_DISPLAY_H
