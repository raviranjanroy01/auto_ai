/**
 * Desktop G-Board — IPC Bridge (Named Pipe)
 * ==========================================
 * Reads key events from the lock-free queue and writes them
 * to a Named Pipe that the Python orchestrator reads from.
 *
 * Architecture:
 *   KeyEventQueue (lock-free) ---> Named Pipe ---> Python (ctypes / struct.unpack)
 *
 * The Named Pipe is created as a byte-mode pipe for maximum throughput.
 * Each write is exactly sizeof(KeyEvent) = 24 bytes.
 *
 * Latency budget:
 *   Hook enqueue:   ~0.1ms (lock-free write)
 *   IPC bridge:     ~0.5ms (pipe write)
 *   Python read:    ~1.0ms (struct.unpack)
 *   Total:          ~1.6ms  (well under 5ms target)
 */

#include "keyboard_hook.h"
#include <cstdio>
#include <thread>
#include <chrono>

// ─── Globals ────────────────────────────────────────────────────
static HANDLE g_pipe_handle = INVALID_HANDLE_VALUE;
static std::thread g_ipc_thread;
static std::atomic<bool> g_ipc_running{false};

// ─── Named Pipe Server ─────────────────────────────────────────

/**
 * Create and wait for a client to connect to the named pipe.
 * Returns true when a Python client has connected.
 */
static bool CreateAndWaitForClient() {
    g_pipe_handle = CreateNamedPipeW(
        PIPE_NAME,
        PIPE_ACCESS_OUTBOUND,               // Server writes, Python reads
        PIPE_TYPE_BYTE | PIPE_WAIT,          // Byte mode, blocking
        1,                                    // Max instances
        sizeof(KeyEvent) * 256,              // Output buffer (6KB)
        0,                                    // Input buffer (not used)
        0,                                    // Default timeout
        nullptr                               // Default security
    );

    if (g_pipe_handle == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "[IPC] Failed to create named pipe. Error: %lu\n", GetLastError());
        return false;
    }

    printf("[IPC] Named pipe created: %ls\n", PIPE_NAME);
    printf("[IPC] Waiting for Python orchestrator to connect...\n");

    // Block until the Python side opens the pipe
    BOOL connected = ConnectNamedPipe(g_pipe_handle, nullptr);
    if (!connected && GetLastError() != ERROR_PIPE_CONNECTED) {
        fprintf(stderr, "[IPC] Client connection failed. Error: %lu\n", GetLastError());
        CloseHandle(g_pipe_handle);
        g_pipe_handle = INVALID_HANDLE_VALUE;
        return false;
    }

    printf("[IPC] Python orchestrator connected!\n");
    return true;
}

/**
 * IPC Writer Thread — Drains the key event queue and writes to the pipe.
 *
 * Runs at normal priority. Uses a spin-then-sleep strategy:
 *   - If events are available, write them immediately (spin)
 *   - If queue is empty, sleep for 1ms to avoid burning CPU
 */
static void IpcWriterThread() {
    printf("[IPC] Writer thread started (TID: %lu)\n", GetCurrentThreadId());

    KeyEvent event;
    int idle_count = 0;

    while (g_ipc_running.load(std::memory_order_relaxed)) {
        if (GetKeyEventQueue().dequeue(event)) {
            idle_count = 0;

            // Write the raw event bytes to the pipe
            DWORD bytes_written = 0;
            BOOL ok = WriteFile(
                g_pipe_handle,
                &event,
                sizeof(KeyEvent),
                &bytes_written,
                nullptr
            );

            if (!ok || bytes_written != sizeof(KeyEvent)) {
                fprintf(stderr, "[IPC] Pipe write failed (client disconnected?). Error: %lu\n",
                        GetLastError());
                // Client disconnected — stop and wait for reconnect
                break;
            }
        } else {
            // Queue empty — adaptive sleep
            idle_count++;
            if (idle_count > 100) {
                // Deep idle: sleep 5ms (no typing happening)
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            } else {
                // Light idle: sleep 1ms (user might be between keystrokes)
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        }
    }

    printf("[IPC] Writer thread exiting.\n");
}

// ─── Public API ─────────────────────────────────────────────────

/**
 * Start the IPC bridge. Creates the named pipe and spawns the writer thread.
 * Blocks until the Python client connects.
 */
bool StartIpcBridge() {
    if (g_ipc_running.load()) {
        return true;  // Already running
    }

    if (!CreateAndWaitForClient()) {
        return false;
    }

    g_ipc_running.store(true);
    g_ipc_thread = std::thread(IpcWriterThread);
    return true;
}

/**
 * Stop the IPC bridge and clean up resources.
 */
void StopIpcBridge() {
    g_ipc_running.store(false);

    if (g_ipc_thread.joinable()) {
        g_ipc_thread.join();
    }

    if (g_pipe_handle != INVALID_HANDLE_VALUE) {
        DisconnectNamedPipe(g_pipe_handle);
        CloseHandle(g_pipe_handle);
        g_pipe_handle = INVALID_HANDLE_VALUE;
    }

    printf("[IPC] Bridge stopped.\n");
}

// ─── Forward declarations for hook_service.cpp ──────────────────
extern bool StartIpcBridge();
extern void StopIpcBridge();
