/**
 * Desktop G-Board — WH_KEYBOARD_LL Hook Implementation
 * =====================================================
 *
 * CRITICAL PERFORMANCE NOTES:
 * ---------------------------
 * 1. The LowLevelKeyboardProc callback runs on a DEDICATED HIGH-PRIORITY
 *    thread. It MUST return within ~1ms or Windows will skip the hook.
 *
 * 2. We use a lock-free SPSC ring buffer to pass key events to the
 *    IPC writer thread. No mutexes, no allocations in the hot path.
 *
 * 3. AI inference happens in a SEPARATE LOWER-PRIORITY PROCESS (Python).
 *    The hook never waits for inference results.
 *
 * Build:
 *   cl /EHsc /O2 /std:c++17 keyboard_hook.cpp ipc_bridge.cpp /link user32.lib kernel32.lib
 *   — or use CMakeLists.txt with: cmake --build . --config Release
 */

#include "keyboard_hook.h"
#include <cstring>

// ─── Globals ────────────────────────────────────────────────────
static HHOOK g_hook_handle = nullptr;
static KeyEventQueue g_key_queue;
static LARGE_INTEGER g_qpc_frequency;

// ─── KeyEventQueue Implementation ───────────────────────────────

KeyEventQueue::KeyEventQueue() {
    memset(buffer_, 0, sizeof(buffer_));
}

bool KeyEventQueue::enqueue(const KeyEvent& event) {
    const size_t current_head = head_.load(std::memory_order_relaxed);
    const size_t next_head = (current_head + 1) % KEY_QUEUE_CAPACITY;

    // If next_head == tail, the queue is full — drop the event.
    // In practice this should never happen unless the IPC thread is frozen.
    if (next_head == tail_.load(std::memory_order_acquire)) {
        return false;  // Queue full — key event dropped
    }

    buffer_[current_head] = event;
    head_.store(next_head, std::memory_order_release);
    return true;
}

bool KeyEventQueue::dequeue(KeyEvent& event) {
    const size_t current_tail = tail_.load(std::memory_order_relaxed);

    if (current_tail == head_.load(std::memory_order_acquire)) {
        return false;  // Queue empty
    }

    event = buffer_[current_tail];
    tail_.store((current_tail + 1) % KEY_QUEUE_CAPACITY, std::memory_order_release);
    return true;
}

size_t KeyEventQueue::size() const {
    const size_t h = head_.load(std::memory_order_acquire);
    const size_t t = tail_.load(std::memory_order_acquire);
    return (h >= t) ? (h - t) : (KEY_QUEUE_CAPACITY - t + h);
}

bool KeyEventQueue::is_empty() const {
    return head_.load(std::memory_order_acquire) == tail_.load(std::memory_order_acquire);
}

// ─── Hook Callback ──────────────────────────────────────────────

/**
 * LowLevelKeyboardProc — Called by Windows for EVERY keystroke system-wide.
 *
 * PERFORMANCE: This function must complete in <1ms.
 * We only do:
 *   1. Read the KBDLLHOOKSTRUCT
 *   2. Get a QPC timestamp
 *   3. Enqueue into the lock-free ring buffer
 *   4. Return (call next hook)
 *
 * NO allocations, NO I/O, NO blocking calls.
 */
static LRESULT CALLBACK LowLevelKeyboardProc(
    int nCode,
    WPARAM wParam,
    LPARAM lParam
) {
    if (nCode == HC_ACTION) {
        const KBDLLHOOKSTRUCT* kb = reinterpret_cast<const KBDLLHOOKSTRUCT*>(lParam);

        // Skip injected events (from our own simulated input or other hooks)
        if (kb->flags & LLKHF_INJECTED) {
            return CallNextHookEx(g_hook_handle, nCode, wParam, lParam);
        }

        // Build the key event
        KeyEvent event;
        event.vk_code   = kb->vkCode;
        event.scan_code  = kb->scanCode;
        event.flags      = kb->flags;
        event.is_keydown = (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN) ? 1 : 0;
        memset(event._padding, 0, sizeof(event._padding));

        // High-resolution timestamp
        LARGE_INTEGER qpc;
        QueryPerformanceCounter(&qpc);
        event.timestamp = static_cast<uint64_t>(qpc.QuadPart);

        // Enqueue — lock-free, O(1), no blocking
        g_key_queue.enqueue(event);
    }

    return CallNextHookEx(g_hook_handle, nCode, wParam, lParam);
}

// ─── Public API ─────────────────────────────────────────────────

bool InstallKeyboardHook() {
    if (g_hook_handle != nullptr) {
        return true;  // Already installed
    }

    // Cache QPC frequency for timestamp conversion
    QueryPerformanceFrequency(&g_qpc_frequency);

    g_hook_handle = SetWindowsHookExW(
        WH_KEYBOARD_LL,
        LowLevelKeyboardProc,
        GetModuleHandle(nullptr),
        0  // 0 = all threads (global hook)
    );

    return g_hook_handle != nullptr;
}

void UninstallKeyboardHook() {
    if (g_hook_handle != nullptr) {
        UnhookWindowsHookEx(g_hook_handle);
        g_hook_handle = nullptr;
    }
}

KeyEventQueue& GetKeyEventQueue() {
    return g_key_queue;
}

bool IsHookInstalled() {
    return g_hook_handle != nullptr;
}
