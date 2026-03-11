/**
 * Desktop G-Board — Low-Level Keyboard Hook
 * ==========================================
 * Provides a WH_KEYBOARD_LL hook that intercepts all keystrokes
 * globally and forwards them to the Python orchestrator via IPC
 * with sub-5ms latency.
 *
 * Architecture:
 *   Hook Thread (HIGH_PRIORITY) -> Lock-free Queue -> IPC Writer Thread -> Named Pipe -> Python
 *
 * The hook callback MUST return quickly (<1ms) to avoid the
 * "Dead Zone" problem where the keyboard feels laggy.
 */

#pragma once

#ifndef KEYBOARD_HOOK_H
#define KEYBOARD_HOOK_H

#include <windows.h>
#include <atomic>
#include <cstdint>

// ─── Constants ──────────────────────────────────────────────────
constexpr size_t KEY_QUEUE_CAPACITY = 4096;  // Lock-free ring buffer size
constexpr const wchar_t* PIPE_NAME = L"\\\\.\\pipe\\DesktopGBoardKeys";

// ─── Key Event Structure ────────────────────────────────────────
// Packed tightly for fast IPC transfer.
#pragma pack(push, 1)
struct KeyEvent {
    uint32_t vk_code;       // Virtual key code (VK_A, VK_SPACE, etc.)
    uint32_t scan_code;     // Hardware scan code
    uint32_t flags;         // LLKHF_* flags (extended, injected, altdown, up)
    uint64_t timestamp;     // High-resolution timestamp (QPC ticks)
    uint8_t  is_keydown;    // 1 = key down, 0 = key up
    uint8_t  _padding[3];   // Alignment padding
};
#pragma pack(pop)

static_assert(sizeof(KeyEvent) == 24, "KeyEvent must be 24 bytes for IPC");

// ─── Lock-Free Ring Buffer ──────────────────────────────────────
// Single-producer (hook thread), single-consumer (IPC writer thread).
// Uses atomic indices for thread safety without mutexes.
class KeyEventQueue {
public:
    KeyEventQueue();

    // Returns true if the event was enqueued successfully.
    // Called from the hook callback — MUST be fast and lock-free.
    bool enqueue(const KeyEvent& event);

    // Returns true if an event was dequeued. Non-blocking.
    bool dequeue(KeyEvent& event);

    // Returns the number of events currently in the queue.
    size_t size() const;

    bool is_empty() const;

private:
    KeyEvent buffer_[KEY_QUEUE_CAPACITY];
    alignas(64) std::atomic<size_t> head_{0};  // Writer index (hook thread)
    alignas(64) std::atomic<size_t> tail_{0};  // Reader index (IPC thread)
};

// ─── Hook Management ────────────────────────────────────────────

// Install the global low-level keyboard hook.
// Returns true on success. Must be called from a thread with a message loop.
bool InstallKeyboardHook();

// Remove the keyboard hook. Safe to call even if not installed.
void UninstallKeyboardHook();

// Get the shared key event queue (singleton).
KeyEventQueue& GetKeyEventQueue();

// Check if the hook is currently active.
bool IsHookInstalled();

#endif // KEYBOARD_HOOK_H
