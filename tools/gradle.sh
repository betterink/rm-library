#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
gradle_version=8.14.3
tool_dir="$repo_dir/.tools"
gradle_bin="$tool_dir/gradle-$gradle_version/bin/gradle"

if [[ -z "${JAVA_HOME:-}" && -x /opt/homebrew/opt/openjdk@21/bin/java ]]; then
    export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
fi
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
if ! "$java_bin" -version >/dev/null 2>&1; then
    echo 'A JDK is required on the build computer. On macOS: brew install openjdk@21' >&2
    exit 1
fi
if [[ ! -x "$gradle_bin" ]]; then
    mkdir -p "$tool_dir"
    archive="$tool_dir/gradle-$gradle_version-bin.zip"
    url="https://services.gradle.org/distributions/gradle-$gradle_version-bin.zip"
    curl --fail --location --retry 2 "$url" -o "$archive"
    curl --fail --location --retry 2 "$url.sha256" -o "$archive.sha256"
    python3 - "$archive" <<'PY'
import hashlib
import pathlib
import sys
import zipfile
archive = pathlib.Path(sys.argv[1])
expected = pathlib.Path(str(archive) + '.sha256').read_text().strip().split()[0]
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit('Gradle download checksum mismatch')
with zipfile.ZipFile(archive) as source:
    root = archive.parent.resolve()
    for entry in source.infolist():
        if root not in (root / entry.filename).resolve().parents:
            raise SystemExit('Unexpected path in Gradle archive')
    source.extractall(root)
PY
    chmod +x "$gradle_bin"
fi
exec "$gradle_bin" --project-dir "$repo_dir/example" "$@"
