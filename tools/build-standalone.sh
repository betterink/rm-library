#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Linux ]]; then
    echo 'The reMarkable SDK build requires Linux (VM, container or Linux computer).' >&2
    exit 1
fi
if [[ $# != 1 || ! -f "$1" ]]; then
    echo 'Usage: tools/build-standalone.sh /path/to/SDK/environment-setup-...' >&2
    exit 1
fi
# Yocto environment scripts may reference unset variables.
set +u
source "$1"
set -u
: "${OECORE_TARGET_SYSROOT:?SDK did not set OECORE_TARGET_SYSROOT}"
# Newer Yocto SDKs export CMAKE_TOOLCHAIN_FILE instead of the legacy OE name.
# Older SDKs may only install the standard file in the native sysroot.
toolchain_file="${CMAKE_TOOLCHAIN_FILE:-${OE_CMAKE_TOOLCHAIN_FILE:-}}"
if [[ -z "$toolchain_file" && -n "${OECORE_NATIVE_SYSROOT:-}" ]]; then
    for candidate in \
        "$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake" \
        "$OECORE_NATIVE_SYSROOT/usr/share/cmake/SDKToolchainConfig.cmake" \
        "$OECORE_NATIVE_SYSROOT/usr/share/cmake/Qt6Toolchain.cmake"; do
        if [[ -f "$candidate" ]]; then
            toolchain_file="$candidate"
            break
        fi
    done
fi
if [[ -z "$toolchain_file" || ! -f "$toolchain_file" ]]; then
    echo "SDK CMake toolchain file not found: ${toolchain_file:-no path supplied}." >&2
    echo "Native sysroot: ${OECORE_NATIVE_SYSROOT:-unset}" >&2
    echo 'Set CMAKE_TOOLCHAIN_FILE to the SDK toolchain file before invoking this script.' >&2
    exit 1
fi
export CMAKE_TOOLCHAIN_FILE="$toolchain_file"
echo "[build] CMake toolchain: $toolchain_file"
case "${OECORE_TARGET_ARCH:-${TARGET_PREFIX:-}}" in
    aarch64*) ;;
    *) echo 'Use the Paper Pro (ferrari) AArch64 target SDK.' >&2; exit 1 ;;
esac
cmake -S "$repo_dir/standalone" -B "$repo_dir/build/standalone-tablet" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE="$toolchain_file"
cmake --build "$repo_dir/build/standalone-tablet" --parallel 2
python3 "$repo_dir/tools/standalone.py" package \
    --binary "$repo_dir/build/standalone-tablet/ink-benchmark"
