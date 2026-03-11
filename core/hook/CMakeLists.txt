cmake_minimum_required(VERSION 3.20)
project(DesktopGBoardHook LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ─── Keyboard Hook DLL ───────────────────────────────────────────
# This builds a shared library (.dll) that installs the
# WH_KEYBOARD_LL hook and communicates with the Python
# orchestrator via a Named Pipe.
add_library(keyboard_hook SHARED
    keyboard_hook.cpp
    ipc_bridge.cpp
)

target_link_libraries(keyboard_hook PRIVATE
    user32      # SetWindowsHookEx, CallNextHookEx
    kernel32    # Named Pipes, Events
)

# ─── Standalone Hook Service (optional) ──────────────────────────
# A minimal .exe that loads the hook and runs a message loop.
# Use this if you want to run the hook as a separate high-priority
# process instead of loading the DLL from Python via ctypes.
add_executable(hook_service
    hook_service.cpp
    keyboard_hook.cpp
    ipc_bridge.cpp
)

target_link_libraries(hook_service PRIVATE
    user32
    kernel32
)

# Set high priority hint for the service executable
set_target_properties(hook_service PROPERTIES
    WIN32_EXECUTABLE FALSE
    OUTPUT_NAME "gboard_hook_service"
)

install(TARGETS keyboard_hook hook_service
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
)
