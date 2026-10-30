#!/usr/bin/env python3
"""Build, package and deploy the Ink AppLoad example (Python standard library)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'example'
DIST = ROOT / 'dist'
PACKAGE = 'ink-example-dev'
APP_ROOT = '/home/root/xovi/exthome/appload'
SSH_OPTIONS = ['-o', 'ConnectTimeout=8', '-o', 'ConnectionAttempts=1',
               '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=3']


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def rcc_path():
    if os.environ.get('RCC'):
        return os.environ['RCC']
    for name in ('rcc', 'rcc6'):
        if shutil.which(name):
            return shutil.which(name)
    for path in ('/opt/homebrew/opt/qt/bin/rcc', '/opt/homebrew/opt/qt/libexec/rcc',
                 '/opt/homebrew/opt/qt/share/qt/libexec/rcc',
                 '/opt/homebrew/opt/qtbase/share/qt/libexec/rcc',
                 '/usr/local/opt/qt/bin/rcc', '/usr/local/opt/qt/libexec/rcc',
                 '/usr/local/opt/qt/share/qt/libexec/rcc',
                 '/usr/local/opt/qtbase/share/qt/libexec/rcc',
                 '/usr/lib/qt6/libexec/rcc'):
        if Path(path).is_file():
            return path
    raise RuntimeError('Qt rcc not found. Install Qt 6, or set RCC to its rcc executable.')


def check_elf(path, machine=183):
    with open(path, 'rb') as source:
        header = source.read(20)
    if (len(header) < 20 or header[:6] != b'\x7fELF\x02\x01'
            or struct.unpack_from('<H', header, 18)[0] != machine):
        raise RuntimeError(f'{path} must be a little-endian ELF64 executable for machine {machine}')


def elf_dependencies(path):
    """Read ELF64 DT_NEEDED entries without a host readelf executable."""
    data = Path(path).read_bytes()
    try:
        phoff = struct.unpack_from('<Q', data, 32)[0]
        entry_size, count = struct.unpack_from('<HH', data, 54)
        if entry_size < 56:
            raise ValueError('Invalid program header size')
        segments = [struct.unpack_from('<IIQQQQQQ', data, phoff + i * entry_size)
                    for i in range(count)]
        dynamic = next((s for s in segments if s[0] == 2), None)
        if dynamic is None:
            return []
        entries = []
        for offset in range(dynamic[2], dynamic[2] + dynamic[5], 16):
            tag, value = struct.unpack_from('<qQ', data, offset)
            if tag == 0:
                break
            entries.append((tag, value))
        address = next(value for tag, value in entries if tag == 5)
        load = next(s for s in segments if s[0] == 1 and s[3] <= address < s[3] + s[5])
        base = load[2] + address - load[3]
        return [data[base + value:data.index(b'\0', base + value)].decode('utf-8')
                for tag, value in entries if tag == 1]
    except (struct.error, ValueError, StopIteration, UnicodeDecodeError) as error:
        raise RuntimeError(f'Cannot read ELF dependencies from {path}: {error}') from error


def make_icon(path):
    # A small code-generated monochrome test glyph; no external image dependency.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    pixels = bytearray()
    for y in range(96):
        pixels.append(0)
        for x in range(96):
            ink = (12 <= x <= 83 and (12 <= y <= 17 or 78 <= y <= 83)
                   or 12 <= y <= 83 and (12 <= x <= 17 or 78 <= x <= 83)
                   or 32 <= x <= 63 and 32 <= y <= 63)
            pixels.append(0 if ink else 255)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 96, 96, 8, 0, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def build(args):
    rcc = rcc_path()  # Fail before downloading Gradle if Qt is missing.
    if args.backend_binary:
        binary = Path(args.backend_binary).resolve()
    else:
        run(ROOT / 'tools/gradle.sh', '--console=plain', 'linkReleaseExecutableLinuxArm64')
        binary = EXAMPLE / 'build/bin/linuxArm64/releaseExecutable/entry.kexe'
    check_elf(binary)
    dependencies = elf_dependencies(binary)
    print('ELF dependencies: ' + (', '.join(dependencies) or '(none)'), flush=True)
    if 'libcrypt.so.1' in dependencies:
        raise RuntimeError('Backend still requires libcrypt.so.1. Rebuild with --as-needed before packaging.')
    bundle = DIST / PACKAGE
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / 'backend').mkdir(parents=True)
    shutil.copy2(binary, bundle / 'backend/entry')
    (bundle / 'backend/entry').chmod(0o755)
    shutil.copy2(EXAMPLE / 'manifest.json', bundle / 'manifest.json')
    make_icon(bundle / 'icon.png')
    # Avoid resource compression/version requirements newer than the tablet's Qt.
    run(rcc, '--binary', '--format-version', '2', '--no-compress',
        EXAMPLE / 'application.qrc', '-o', bundle / 'resources.rcc')
    archive = DIST / f'{PACKAGE}.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        output.add(bundle, arcname=PACKAGE)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(f'{checksum}  {archive.name}\n')
    print(f'Bundle: {archive}\nSHA256: {checksum}')


def check_host(host):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', host):
        raise RuntimeError('Use an SSH config alias such as rm for --host.')


def deploy(args):
    check_host(args.host)
    archive = DIST / f'{PACKAGE}.tar.gz'
    if not archive.is_file():
        raise RuntimeError('Build the bundle first: python3 tools/example.py build')
    # AppLoad must not be reading a bundle while its files are replaced. Require
    # the user to stop this example first; never restart the native UI implicitly.
    remote_script = f'''set -eu
app_root={APP_ROOT}
echo '[deploy] Connected; checking AppLoad installation.'
if ! test -d "$app_root"; then
    echo "AppLoad application directory missing: $app_root" >&2
    exit 1
fi
if pgrep -f '^backend/entry /tmp/ink[.]example[.]dev[.]sock$' >/dev/null; then
    echo 'Stop the Ink Example backend before deploying.' >&2
    exit 1
fi
stage=$(mktemp -d /home/root/.ink-example-stage.XXXXXX)
trap 'rm -rf "$stage"' EXIT
echo '[deploy] Receiving and extracting bundle.'
tar -xzf - -C "$stage"
test -f "$stage/{PACKAGE}/manifest.json"
test -x "$stage/{PACKAGE}/backend/entry"
echo '[deploy] Running Kotlin executable self-test.'
"$stage/{PACKAGE}/backend/entry" --self-test
echo '[deploy] Activating application bundle.'
mkdir -p /home/root/.ink-example-backups
if test -e "$app_root/{PACKAGE}"; then
    backup=$(mktemp -d /home/root/.ink-example-backups/install.XXXXXX)
    mv "$app_root/{PACKAGE}" "$backup/"
    if ! mv "$stage/{PACKAGE}" "$app_root/{PACKAGE}"; then
        mv "$backup/{PACKAGE}" "$app_root/{PACKAGE}"
        exit 1
    fi
else
    mv "$stage/{PACKAGE}" "$app_root/{PACKAGE}"
fi
echo 'Installed Ink Example (Dev). Open AppLoad and refresh its app list.'
'''
    print(f'[deploy] Connecting to {args.host} over SSH (8-second connection timeout)…', flush=True)
    with archive.open('rb') as source:
        try:
            run('ssh', *SSH_OPTIONS, args.host, remote_script, stdin=source)
        except subprocess.CalledProcessError as error:
            if error.returncode == 255:
                raise RuntimeError(
                    'SSH connection failed or disconnected. Check the tablet USB connection, '
                    f'then run: ssh -o ConnectTimeout=8 {args.host}'
                ) from error
            raise RuntimeError(f'Remote deployment failed (exit {error.returncode}); see the last deployment step above.') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build_parser = commands.add_parser('build', help='Compile Kotlin/Native and package the AppLoad bundle')
    build_parser.add_argument('--backend-binary', help='Package a precompiled linuxArm64 backend')
    for name in ('deploy', 'verify', 'logs'):
        command = commands.add_parser(name)
        command.add_argument('--host', default='rm')
    commands.add_parser('doctor')
    args = parser.parse_args()
    if args.command == 'build':
        build(args)
    elif args.command == 'deploy':
        deploy(args)
    elif args.command == 'doctor':
        print('Build needs: JDK 21, Qt 6 rcc, Python 3, and internet for Gradle/Kotlin downloads.')
        print(f'Qt rcc: {rcc_path()}')
        run(ROOT / 'tools/gradle.sh', '--version')
    else:
        check_host(args.host)
        if args.command == 'verify':
            run('ssh', args.host, f'{APP_ROOT}/{PACKAGE}/backend/entry --self-test')
        elif args.command == 'logs':
            run('ssh', '-t', args.host, 'journalctl -u xochitl -f -n 100 --no-pager')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
