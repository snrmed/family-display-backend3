#include "http_task.h"
#include "config.h"

void HttpTask::taskFunction(void* parameter) {
    TaskContext* ctx = (TaskContext*)parameter;

    if (ctx && ctx->operation) {
        ctx->result = ctx->operation();
    }

    ctx->completed = true;
    xSemaphoreGive(ctx->semaphore);

    // Task deletes itself
    vTaskDelete(NULL);
}

bool HttpTask::runWithLargeStack(std::function<bool()> httpOperation, uint32_t stackSize) {
    TaskContext ctx;
    ctx.operation = httpOperation;
    ctx.result = false;
    ctx.completed = false;
    ctx.semaphore = xSemaphoreCreateBinary();

    if (!ctx.semaphore) {
        DEBUG_PRINTLN("HttpTask: Failed to create semaphore");
        return false;
    }

    // Create task with large stack on core 0 (protocol stack runs on core 0)
    TaskHandle_t taskHandle = NULL;
    BaseType_t created = xTaskCreatePinnedToCore(
        taskFunction,           // Task function
        "http_task",           // Task name
        stackSize / 4,         // Stack size in words (not bytes!)
        &ctx,                  // Parameters
        5,                     // Priority (higher than loop task)
        &taskHandle,           // Task handle
        0                      // Core 0 (WiFi/protocol stack)
    );

    if (created != pdPASS) {
        DEBUG_PRINTLN("HttpTask: Failed to create task");
        vSemaphoreDelete(ctx.semaphore);
        return false;
    }

    DEBUG_PRINTF("HttpTask: Created task with %d bytes stack\n", stackSize);

    // Wait for task to complete (max 2 minutes for slow HTTPS connections)
    BaseType_t taken = xSemaphoreTake(ctx.semaphore, pdMS_TO_TICKS(120000));

    vSemaphoreDelete(ctx.semaphore);

    if (taken != pdTRUE) {
        DEBUG_PRINTLN("HttpTask: Task timeout");
        return false;
    }

    DEBUG_PRINTF("HttpTask: Completed with result=%d\n", ctx.result);
    return ctx.result;
}
