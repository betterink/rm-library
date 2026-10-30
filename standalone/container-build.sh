#!/usr/bin/env bash
set -euo pipefail
sdk_environment="$(find /opt/rm-sdk -maxdepth 1 -name 'environment-setup-*' -type f -print -quit)"
if [[ -z "$sdk_environment" ]]; then
    echo 'SDK environment script not found in the build container.' >&2; exit 1
fi
exec bash tools/build-standalone.sh "$sdk_environment"
