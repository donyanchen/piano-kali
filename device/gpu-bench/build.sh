#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
g++ -O2 -std=c++17 -Wall -Wextra -Wno-missing-field-initializers bench.cpp -o bench $(pkg-config --cflags --libs epoxy egl vulkan)
glslangValidator -V scene.vert -o scene.vert.spv
glslangValidator -V -DLOOPS=0 -DALPHA=1.0 scene.frag -o fill.frag.spv
glslangValidator -V -DLOOPS=0 -DALPHA=0.35 scene.frag -o ui.frag.spv
glslangValidator -V -DLOOPS=64 -DALPHA=1.0 scene.frag -o alu.frag.spv
