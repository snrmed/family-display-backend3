#pragma once

#include <Arduino.h>
#include "config.h"

// Utility helpers for allocating large image buffers. Prefer PSRAM when
// available so RAW7 downloads (192KB) and expanded pixel buffers (384KB)
// succeed even when internal heap is fragmented.
uint8_t* allocateBuffer(size_t size, const char* tag);
inline uint8_t* allocateRaw7Buffer(const char* tag = "RAW7") {
    return allocateBuffer(RAW7_SIZE, tag);
}
