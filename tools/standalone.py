#!/usr/bin/env python3
"""Standalone Qt interaction benchmark; independent of AppLoad and Kotlin."""
import argparse
import hashlib
import json
import os
import platform
import shlex
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

from example import ROOT, SSH_OPTIONS, check_host, check_elf, elf_dependencies, run
from display_symbols import display_symbol_report

SOURCE = ROOT / 'standalone'
DIST = ROOT / 'dist'
NAME = 'ink-standalone-benchmark'


def desktop_build(test=False, navigation_test=False, display_test=False):
    if sys.platform != 'darwin':
        raise RuntimeError('This preview helper targets Homebrew Qt on macOS; use CMake on other hosts.')
    qt = Path('/opt/homebrew/opt/qt')
    if not qt.exists():
        qt = Path('/usr/local/opt/qt')
    library = qt / 'lib'
    moc = qt / 'share/qt/libexec/moc'
    rcc = qt / 'share/qt/libexec/rcc'
    if not moc.is_file() or not rcc.is_file():
        raise RuntimeError('Homebrew Qt development tools are missing.')
    build = ROOT / 'build/standalone-desktop'
    build.mkdir(parents=True, exist_ok=True)
    run(moc, '-F' + str(library), SOURCE / 'StrokeSurface.h', '-o', build / 'moc_StrokeSurface.cpp')
    run(moc, '-F' + str(library), SOURCE / 'EpaperDisplayControl.h', '-o', build / 'moc_EpaperDisplayControl.cpp')
    run(rcc, '--name', 'ink_benchmark', '--no-compress', SOURCE / 'application.qrc', '-o', build / 'resources.cpp')
    binary = build / ('display-test' if display_test else 'navigation-test' if navigation_test else 'canvas-test' if test else 'ink-benchmark')
    main_source = ('tests/display_test.cpp' if display_test else 'tests/navigation_test.cpp'
                   if navigation_test else 'tests/canvas_test.cpp' if test else 'main.cpp')
    frameworks = ['QtQuick', 'QtQml', 'QtGui', 'QtCore']
    arguments = ['xcrun', 'clang++', '-std=c++17', '-O2', '-fPIC', '-F' + str(library),
                 '-I' + str(qt / 'include'), '-I' + str(SOURCE),
                 SOURCE / main_source,
                 SOURCE / 'StrokeSurface.cpp', SOURCE / 'TabletNavigation.cpp',
                 SOURCE / 'EpaperDisplayControl.cpp', build / 'moc_EpaperDisplayControl.cpp',
                 build / 'moc_StrokeSurface.cpp', build / 'resources.cpp',
                 '-Wl,-rpath,' + str(library), '-o', binary]
    if display_test:
        run(moc, '-F' + str(library), '-I' + str(SOURCE), SOURCE / 'tests/DisplayTestBackend.h',
            '-o', build / 'moc_DisplayTestBackend.cpp')
        arguments.append(build / 'moc_DisplayTestBackend.cpp')
    for framework in frameworks:
        arguments.extend(['-framework', framework])
    run(*arguments)
    return binary


def docker_executable():
    executable = shutil.which('docker')
    bundled = Path('/Applications/Docker.app/Contents/Resources/bin/docker')
    return executable or (str(bundled) if bundled.is_file() else None)


def check_docker():
    executable = docker_executable()
    if not executable:
        raise RuntimeError('Docker is not installed. Install and start Docker Desktop first.')
    try:
        result = subprocess.run([executable, 'info', '--format', '{{.OSType}}/{{.Architecture}}'],
                                capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('Docker did not respond within 15 seconds. Check Docker Desktop is running.') from error
    if result.returncode:
        detail = result.stderr.strip()[-600:]
        raise RuntimeError('Cannot access Docker Engine. Open Docker Desktop and wait until it is running. '
                           'If access is denied in an agent sandbox, run this command in your normal Terminal. '
                           + detail)
    print('Docker Engine: ' + result.stdout.strip(), flush=True)
    return executable


def sdk_choice(url=None):
    architecture = 'aarch64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x86_64'
    if not url:
        configuration = json.loads((SOURCE / 'sdk.json').read_text())
        url = configuration['urls'][architecture]
        print(f"SDK candidate: {configuration['candidateFirmware']} for {configuration['product']}; "
              f"tablet target: {configuration['targetFirmware']}. Compatibility is not verified.", flush=True)
    return architecture, url


def build_tablet(url=None):
    executable = check_docker()
    architecture, url = sdk_choice(url)
    target = 'linux/arm64' if architecture == 'aarch64' else 'linux/amd64'
    print('Building using the supplied ferrari SDK. Its compatibility with tablet firmware '
          'must be checked before interpreting performance results.', flush=True)
    run(executable, 'build', '--progress=plain', '--platform', target, '--build-arg', f'SDK_URL={url}',
        '--build-arg', f'SDK_HOST_ARCH={architecture}', '-t', 'ink-benchmark-sdk:local', SOURCE)
    run(executable, 'run', '--rm', '--platform', target, '-v', f'{ROOT}:/workspace', 'ink-benchmark-sdk:local')


def package(binary):
    binary = Path(binary).resolve()
    check_elf(binary)
    dependencies = elf_dependencies(binary)
    DIST.mkdir(exist_ok=True)
    # Source may already be inside dist: stage before changing any output.
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / NAME
        bundle.mkdir()
        shutil.copy2(binary, bundle / 'ink-benchmark')
        shutil.copy2(SOURCE / 'run-on-tablet.sh', bundle / 'run-on-tablet.sh')
        for filename in ('ink-benchmark', 'run-on-tablet.sh'):
            (bundle / filename).chmod(0o755)
        (bundle / 'metadata.json').write_text(json.dumps({
            'name': NAME, 'architecture': 'aarch64', 'dependencies': dependencies,
            'runtime': 'Qt Quick epaper', 'requiresAppLoad': False,
            'deviceValidated': False,
            'sdkSource': os.environ.get('INK_BUILD_SDK_URL', 'user-provided build'),
        }, indent=2) + '\n')
        archive = DIST / f'{NAME}.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            output.add(bundle, arcname=NAME)
    print(f'Bundle: {archive}\nDependencies: {", ".join(dependencies)}')


def deploy(host):
    archive = DIST / f'{NAME}.tar.gz'
    if not archive.is_file():
        raise RuntimeError('No tablet bundle. Build on Linux with the matching ferrari SDK first.')
    script = f'''set -eu
root=/home/root/ink-benchmark
if systemctl is-active --quiet ink-benchmark.service; then
    echo 'Stop the benchmark before deploying.' >&2; exit 1
fi
mkdir -p "$root"
stage=$(mktemp -d "$root/stage.XXXXXX")
trap 'rm -rf "$stage"' EXIT
echo '[standalone] Receiving bundle.'
tar -xzf - -C "$stage"
echo '[standalone] Checking binary dependencies without opening the display.'
"$stage/{NAME}/ink-benchmark" --probe
if test -d "$root/current"; then
    previous=$(mktemp -d "$root/previous.XXXXXX")
    mv "$root/current" "$previous/bundle"
    if ! mv "$stage/{NAME}" "$root/current"; then
        mv "$previous/bundle" "$root/current"; exit 1
    fi
else
    mv "$stage/{NAME}" "$root/current"
fi
echo '[standalone] Installed. Native interface has not been stopped.'
'''
    print(f'Connecting to {host}…', flush=True)
    with archive.open('rb') as source:
        run('ssh', *SSH_OPTIONS, host, script, stdin=source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preview = commands.add_parser('preview', help='Build and run the macOS functional preview')
    preview.add_argument('--smoke-test', action='store_true')
    commands.add_parser('test', help='Build and test the native raster surface on macOS')
    tablet = commands.add_parser('build-tablet', help='Build in Linux using Docker and an official ferrari SDK')
    tablet.add_argument('--sdk-url', help='Override the recorded official SDK candidate')
    setup = commands.add_parser('setup', help='Build and deploy; optionally start a tablet session')
    setup.add_argument('--sdk-url', help='Override the recorded official SDK candidate')
    setup.add_argument('--host', default='rm')
    setup.add_argument('--launch', action='store_true', help='Also stop Xochitl and run the benchmark after installation')
    commands.add_parser('doctor', help='Check Docker access and show the selected SDK candidate')
    package_parser = commands.add_parser('package', help='Package an SDK-built AArch64 executable')
    package_parser.add_argument('--binary', required=True)
    for name in ('deploy', 'run', 'stop', 'logs', 'inspect'):
        command = commands.add_parser(name)
        command.add_argument('--host', default='rm')
        if name == 'run':
            command.add_argument('--pen-input', choices=['none', 'evdevtablet'], default='none')
    diagnose = commands.add_parser('diagnose', help='Save read-only screen/input/plugin diagnostics locally')
    diagnose.add_argument('--host', default='rm')
    diagnose.add_argument('--display-library', action='store_true',
                          help='Also copy the installed epaper library and inspect its exported interface names locally')
    args = parser.parse_args()
    if args.command in ('preview', 'test'):
        binary = desktop_build(test=args.command == 'test')
        env = os.environ.copy()
        arguments = [binary]
        if args.command == 'test' or args.smoke_test:
            env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
            if args.command == 'preview':
                arguments.append('--smoke-test')
        run(*arguments, env=env)
        if args.command == 'test':
            run(desktop_build(navigation_test=True), env=env)
            run(desktop_build(display_test=True), env=env)
    elif args.command == 'build-tablet':
        build_tablet(args.sdk_url)
    elif args.command == 'setup':
        check_host(args.host)
        build_tablet(args.sdk_url)
        deploy(args.host)
        if args.launch:
            run('ssh', *SSH_OPTIONS, args.host, '/home/root/ink-benchmark/current/run-on-tablet.sh')
        else:
            print('Installed. Start on-screen with: python3 tools/standalone.py run --host ' + args.host)
    elif args.command == 'doctor':
        sdk_choice()
        check_docker()
    elif args.command == 'package':
        package(args.binary)
    else:
        check_host(args.host)
        if args.command == 'deploy':
            deploy(args.host)
        elif args.command == 'run':
            print('Starting a 10-minute benchmark session; save open tablet work first.', flush=True)
            run('ssh', *SSH_OPTIONS, args.host,
                '/home/root/ink-benchmark/current/run-on-tablet.sh ' + shlex.quote(args.pen_input))
        elif args.command == 'diagnose':
            report = ROOT / 'build/standalone-device-diagnostics.txt'
            report.parent.mkdir(parents=True, exist_ok=True)
            script = '''uname -a
cat /etc/os-release
cat /proc/bus/input/devices
find /usr/lib -name '*epaper*.so' -o -name '*tablet*.so'
systemctl show ink-benchmark.service -p Environment -p Result -p ExecMainStatus
journalctl -u ink-benchmark.service -n 150 --no-pager
'''
            result = subprocess.run(['ssh', *SSH_OPTIONS, args.host, script],
                                    capture_output=True, text=True, timeout=30)
            report.write_text(result.stdout + '\n' + result.stderr)
            print('Device diagnostics: ' + str(report))
            if result.returncode:
                raise RuntimeError('Diagnostics returned SSH/remote errors; see the saved report.')
            if args.display_library:
                with tempfile.TemporaryDirectory(dir=report.parent) as directory:
                    library = Path(directory) / 'libqsgepaper.so'
                    with library.open('wb') as output:
                        run('ssh', *SSH_OPTIONS, args.host,
                            'cat /usr/lib/plugins/scenegraph/libqsgepaper.so', stdout=output)
                    summary = display_symbol_report(library)
                    fingerprint = hashlib.sha256(library.read_bytes()).hexdigest()
                    library.replace(report.parent / 'device-libqsgepaper.so')
                with report.open('a') as output:
                    output.write('\nDisplay library SHA256: ' + fingerprint + '\n' + summary)
                print('Saved installed display library and interface names under build/. No library code was executed.')
        elif args.command == 'stop':
            run('ssh', *SSH_OPTIONS, args.host, 'systemctl stop ink-benchmark.service')
        elif args.command == 'logs':
            run('ssh', *SSH_OPTIONS, '-t', args.host,
                'journalctl -u ink-benchmark.service -n 100 -f --no-pager')
        elif args.command == 'inspect':
            run('ssh', *SSH_OPTIONS, args.host,
                "uname -m; cat /etc/os-release; command -v qmake6 || command -v qmake || true; "
                "find /usr/lib -name '*epaper*.so' -print; systemctl is-active xochitl")


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f'Error: {Path(str(error.cmd[0])).name} failed (exit {error.returncode}); '
              'see output above. The next setup step was not run.', file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
