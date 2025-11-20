#ifndef HTTP_TASK_H
#define HTTP_TASK_H

#include <Arduino.h>
#include <functional>

// ============================================================
// HTTP Task Manager - Dedicated Stack for HTTPS Operations
// ============================================================
// Runs HTTP/HTTPS operations in a dedicated FreeRTOS task
// with a large stack to avoid overflow during TLS handshake
// ============================================================

class HttpTask {
public:
    // Run a function in a dedicated task with large stack (64KB)
    // This avoids stack overflow issues with HTTPS/TLS on main task
    static bool runWithLargeStack(std::function<bool()> httpOperation,
                                   uint32_t stackSize = 65536);

private:
    struct TaskContext {
        std::function<bool()> operation;
        bool result;
        bool completed;
        SemaphoreHandle_t semaphore;
    };

    static void taskFunction(void* parameter);
};

#endif // HTTP_TASK_H
