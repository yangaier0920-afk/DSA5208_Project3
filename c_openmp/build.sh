#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
mode=${1:-cpu}
case "$mode" in
  mac)
    /opt/homebrew/opt/llvm/bin/clang++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp \
      -I/opt/homebrew/opt/libomp/include -L/opt/homebrew/opt/libomp/lib \
      -Wl,-rpath,/opt/homebrew/opt/libomp/lib jacobi_c_openmp.cpp -o build/jacobi_c_cpu ;;
  cpu)
    "${CXX:-g++}" -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp jacobi_c_openmp.cpp -o build/jacobi_c_cpu ;;
  nvidia)
    # Keep the working host-header workaround; no FloatN or GPU memory-mode flags.
    # Publish only a successfully linked binary. A failed rebuild exits nonzero.
    c_gpu_tmp=build/jacobi_c_gpu.tmp
    c_obj_dir=$(mktemp -d build/nvhpc_objects.XXXXXX)
    trap 'rm -f "$c_gpu_tmp"; rm -rf "$c_obj_dir"' EXIT
    echo '[1/3] C++ host/CPU compilation (no GPU lowering)'
    nvc++ --gcc-toolchain="$(command -v gcc)" -std=c++17 -O2 -mp=multicore -DC_ENABLE_TARGET -c jacobi_c_openmp.cpp -o "$c_obj_dir/host.o"
    echo '[2/3] Isolated C OpenMP GPU compilation'
    nvc --gcc-toolchain="$(command -v gcc)" -std=c11 -O2 -mp=gpu -Minfo=mp -c jacobi_c_target.c -o "$c_obj_dir/target.o"
    echo '[3/3] CPU/GPU link'
    nvc++ --gcc-toolchain="$(command -v gcc)" -mp=gpu "$c_obj_dir/host.o" "$c_obj_dir/target.o" -o "$c_gpu_tmp"
    mv "$c_gpu_tmp" build/jacobi_c_gpu ;;
  *) echo 'Usage: bash build.sh mac|cpu|nvidia' >&2; exit 2 ;;
esac
