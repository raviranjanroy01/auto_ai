/**
 * Desktop G-Board — Standalone Hook Service
 * ==========================================
 * A minimal Windows executable that:
 *   1. Installs the WH_KEYBOARD_LL hook on a high-priority thread
 *   2. Starts the IPC bridge (named pipe to Python)
 *   3. Runs a Windows message loop to keep the hook alive
 *
 * This runs as a separate process from Python to ensure the hook
 * callback always returns quickly (solving the "Dead Zone" problem).
 *
 * Usage:
 *   gboard_hook_service.exe
 *   (Python orchestrator connects via \\.\pipe\DesktopGBoardKeys)
 *
 * Build:
 *   cmake --build . --config Release
 *   — or —
 *   cl /EHsc /O2 /std:c++17 hook_service.cpp keyboard_hook.cpp ipc_bridge.cpp
 *      /link user32.lib kernel32.lib /OUT:gboard_hook_service.exe
 */

#include "keyboard_hook.h"
#include <cstdio>
#include <csignal>

// Forward declarations from ipc_bridge.cpp
extern bool StartIpcBridge();
extern void StopIpcBridge();

// ─── Signal Handler for Clean Shutdown ──────────────────────────
static volatile bool g_shutdown_requested = false;

static void SignalHandler(int signal) {
    printf("\n[SERVICE] Shutdown signal received (signal=%d)\n", signal);
    g_shutdown_requested = true;
    PostQuitMessage(0);  // Break the message loop
}

// ─── Main ───────────────────────────────────────────────────────
int main(int argc, char* argv[]) {
    printf("==============================================\n");
    printf("  Desktop G-Board — Hook Service v0.2.0\n");
    printf("==============================================\n\n");

    // Register signal handlers for clean shutdown
    signal(SIGINT, SignalHandler);
    signal(SIGTERM, SignalHandler);

    // 1. Elevate thread priority — the hook MUST be responsive
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
    printf("[SERVICE] Thread priority set to HIGHEST\n");

    // Optionally elevate process priority
    SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
    printf("[SERVICE] Process priority set to HIGH\n");

    // 2. Start the IPC bridge (creates named pipe, waits for Python)
    printf("[SERVICE] Starting IPC bridge...\n");
    if (!StartIpcBridge()) {
        fprintf(stderr, "[SERVICE] FATAL: Failed to start IPC bridge.\n");
        return 1;
    }

    // 3. Install the keyboard hook
    printf("[SERVICE] Installing keyboard hook...\n");
    if (!InstallKeyboardHook()) {
        fprintf(stderr, "[SERVICE] FATAL: Failed to install keyboard hook. Error: %lu\n",
                GetLastError());
        StopIpcBridge();
        return 1;
    }
    printf("[SERVICE] Keyboard hook installed successfully!\n");
    printf("[SERVICE] Intercepting all keystrokes. Press Ctrl+C to stop.\n\n");

    // 4. Run the Windows message loop
    // WH_KEYBOARD_LL requires a message loop on the thread that installed the hook.
    // Without this, the hook won't receive any callbacks.
    MSG msg;
    while (!g_shutdown_requested) {
        BOOL ret = GetMessage(&msg, nullptr, 0, 0);
        if (ret == 0 || ret == -1) {
            break;  // WM_QUIT or error
        }
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // 5. Cleanup
    printf("\n[SERVICE] Shutting down...\n");
    UninstallKeyboardHook();
    StopIpcBridge();
    printf("[SERVICE] Clean shutdown complete.\n");

    return 0;
}
