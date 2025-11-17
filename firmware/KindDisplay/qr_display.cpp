#include "qr_display.h"
#include <qrcode.h>  // Using ricmoo/qrcode library

void QRDisplay::showSetupScreen(SpectraDisplay& display) {
    DEBUG_PRINTLN("QR: Rendering setup screen");

    // Allocate buffer for display (800x480)
    uint8_t* buffer = new uint8_t[DISPLAY_WIDTH * DISPLAY_HEIGHT];
    if (!buffer) {
        DEBUG_PRINTLN("QR: Memory allocation failed");
        return;
    }

    // Clear buffer to white
    memset(buffer, EPD_WHITE, DISPLAY_WIDTH * DISPLAY_HEIGHT);

    // === LAYOUT ===
    // Center QR code with branding above and instructions below

    const int qrX = 250;  // X position for QR code
    const int qrY = 120;  // Y position for QR code
    const int qrScale = 6;  // Pixel size multiplier

    // === DRAW HEADER ===
    // "Kin:D" brand name at top
    const char* brand = "Kin:D";
    const char* tagline = "make a smile";
    const char* instruction1 = "1. Connect to WiFi: KIND-Setup";
    const char* instruction2 = "2. Password: kind1234";
    const char* instruction3 = "3. Scan QR or visit http://192.168.4.1";
    const char* instruction4 = "4. Follow setup instructions";

    // Simple text rendering (we'll draw this as rectangles for key labels)
    // For now, just show the QR code - text rendering requires a font library

    // === GENERATE QR CODE ===
    QRCode qrcode;
    uint8_t qrcodeData[qrcode_getBufferSize(3)];  // Version 3 QR code
    qrcode_initText(&qrcode, qrcodeData, 3, ECC_LOW, "http://192.168.4.1");

    DEBUG_PRINTF("QR: Generated QR code, size: %d\n", qrcode.size);

    // === RENDER QR CODE ===
    for (uint8_t y = 0; y < qrcode.size; y++) {
        for (uint8_t x = 0; x < qrcode.size; x++) {
            bool isBlack = qrcode_getModule(&qrcode, x, y);
            uint8_t color = isBlack ? EPD_BLACK : EPD_WHITE;

            // Draw scaled pixel
            for (int dy = 0; dy < qrScale; dy++) {
                for (int dx = 0; dx < qrScale; dx++) {
                    int px = qrX + x * qrScale + dx;
                    int py = qrY + y * qrScale + dy;

                    if (px >= 0 && px < DISPLAY_WIDTH && py >= 0 && py < DISPLAY_HEIGHT) {
                        buffer[py * DISPLAY_WIDTH + px] = color;
                    }
                }
            }
        }
    }

    // === ADD BLUE ACCENTS ===
    // Top bar (Kin:D branding area)
    for (int y = 20; y < 80; y++) {
        for (int x = 200; x < 600; x++) {
            buffer[y * DISPLAY_WIDTH + x] = EPD_BLUE;
        }
    }

    // Draw text labels using simple rectangles as placeholders
    // Top center: "Kin:D" (we'll use blue bar as background)

    // Bottom instructions bar
    for (int y = 380; y < 460; y++) {
        for (int x = 50; x < 750; x++) {
            // Alternate stripes for visual interest
            if (y % 20 < 10) {
                buffer[y * DISPLAY_WIDTH + x] = EPD_YELLOW;
            }
        }
    }

    // === RENDER TO DISPLAY ===
    // Pack buffer to RAW7 format (2 pixels per byte)
    uint8_t* raw7Buffer = new uint8_t[RAW7_SIZE];
    if (!raw7Buffer) {
        DEBUG_PRINTLN("QR: RAW7 buffer allocation failed");
        delete[] buffer;
        return;
    }

    for (size_t i = 0; i < RAW7_SIZE; i++) {
        uint8_t pixel1 = buffer[i * 2];
        uint8_t pixel2 = buffer[i * 2 + 1];
        raw7Buffer[i] = (pixel1 << 4) | (pixel2 & 0x0F);
    }

    // Display on e-ink
    display.displayRAW7(raw7Buffer, RAW7_SIZE);

    // Clean up
    delete[] buffer;
    delete[] raw7Buffer;

    DEBUG_PRINTLN("QR: Setup screen displayed");
}
