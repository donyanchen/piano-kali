#!/bin/sh
# Keep glibc allocation arenas bounded for this application and its children.
# Use the default freedreno OpenGL driver with Burp's bundled ARM64 runtime.
export MALLOC_ARENA_MAX=4
unset MESA_LOADER_DRIVER_OVERRIDE GALLIUM_DRIVER VK_DRIVER_FILES VK_ICD_FILENAMES
exec "$HOME/.local/opt/BurpSuite/BurpSuite" "$@"
