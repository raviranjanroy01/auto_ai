"""
Desktop G-Board — C++ Hook Build Script
=========================================
Builds the C++ keyboard hook service using CMake.

Requirements:
  - CMake >= 3.20
  - Visual Studio Build Tools (MSVC) or MinGW-w64

Usage:
    python scripts/build_hook.py
    python scripts/build_hook.py --config Debug
"""

import os
import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description="Build the C++ keyboard hook service")
    parser.add_argument("--config", choices=["Release", "Debug"], default="Release",
                       help="Build configuration (default: Release)")
    parser.add_argument("--clean", action="store_true", help="Clean build directory first")
    args = parser.parse_args()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    hook_dir = os.path.join(root_dir, "core", "hook")
    build_dir = os.path.join(hook_dir, "build")

    # Check for CMake
    try:
        result = subprocess.run(["cmake", "--version"], capture_output=True, text=True)
        print(f"[OK] {result.stdout.splitlines()[0]}")
    except FileNotFoundError:
        print("[ERROR] CMake not found. Install from https://cmake.org/download/")
        print("        Or: winget install Kitware.CMake")
        sys.exit(1)

    # Clean if requested
    if args.clean and os.path.exists(build_dir):
        import shutil
        shutil.rmtree(build_dir)
        print("[OK] Cleaned build directory.")

    # Create build directory
    os.makedirs(build_dir, exist_ok=True)

    # Configure with CMake
    print(f"\n[BUILD] Configuring ({args.config})...")
    configure_cmd = [
        "cmake",
        "-S", hook_dir,
        "-B", build_dir,
        f"-DCMAKE_BUILD_TYPE={args.config}",
    ]

    result = subprocess.run(configure_cmd, cwd=hook_dir)
    if result.returncode != 0:
        print("[ERROR] CMake configure failed.")
        sys.exit(1)

    # Build
    print(f"\n[BUILD] Building...")
    build_cmd = [
        "cmake",
        "--build", build_dir,
        "--config", args.config,
    ]

    result = subprocess.run(build_cmd, cwd=hook_dir)
    if result.returncode != 0:
        print("[ERROR] Build failed.")
        sys.exit(1)

    # Find the built executable
    exe_name = "gboard_hook_service.exe"
    for dirpath, _, filenames in os.walk(build_dir):
        if exe_name in filenames:
            exe_path = os.path.join(dirpath, exe_name)
            print(f"\n[OK] Build successful!")
            print(f"     Executable: {exe_path}")
            print(f"\n     To use native hook mode:")
            print(f"     1. Run: {exe_path}")
            print(f"     2. Then: python main.py --hook native")
            return

    print(f"\n[OK] Build completed. Check {build_dir} for output.")


if __name__ == "__main__":
    main()
