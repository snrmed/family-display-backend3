#include "memory_utils.h"

#if defined(ESP32)
#include <esp32-hal-psram.h>
#endif

uint8_t* allocateBuffer(size_t size, const char* tag) {
    uint8_t* ptr = nullptr;

#if defined(ESP32)
    if (psramFound()) {
        ptr = static_cast<uint8_t*>(ps_malloc(size));
        if (ptr) {
            DEBUG_PRINTF("%s: Allocated %u bytes from PSRAM (free=%u)\n",
                         tag, static_cast<unsigned>(size), ESP.getFreePsram());
            return ptr;
        }
        DEBUG_PRINTF("%s: PSRAM allocation failed (%u bytes requested)\n",
                     tag, static_cast<unsigned>(size));
    } else {
        DEBUG_PRINTLN("Memory: PSRAM not detected, using internal heap");
    }
#endif

    ptr = static_cast<uint8_t*>(malloc(size));
    if (ptr) {
        DEBUG_PRINTF("%s: Allocated %u bytes from heap (free=%u, max=%u)\n",
                     tag, static_cast<unsigned>(size), ESP.getFreeHeap(),
                     ESP.getMaxAllocHeap());
    } else {
        DEBUG_PRINTF("%s: ERROR - malloc failed (%u bytes). Free heap=%u, max block=%u\n",
                     tag, static_cast<unsigned>(size), ESP.getFreeHeap(),
                     ESP.getMaxAllocHeap());
    }
    return ptr;
}
