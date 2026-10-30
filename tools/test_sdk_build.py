#!/usr/bin/env python3
"""Exercise SDK environment variations without a Docker engine or compiler."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / 'build-standalone.sh'


class SdkBuildTests(unittest.TestCase):
    def build(self, variable=None, fallback=False, invalid=False):
        with tempfile.TemporaryDirectory(prefix='ink sdk ') as directory:
            root = Path(directory)
            native = root / 'native'
            toolchain = native / 'usr/share/cmake/OEToolchainConfig.cmake'
            if fallback or variable:
                toolchain.parent.mkdir(parents=True)
                toolchain.write_text('# test SDK toolchain\n')
            tools = root / 'bin'
            tools.mkdir()
            programs = {
                'uname': '#!/bin/sh\necho Linux\n',
                'cmake': '#!/bin/sh\nprintf "%s\\n" "$@" >> "$BUILD_TEST_LOG"\n',
                'python3': '#!/bin/sh\nexit 0\n',
            }
            for name, content in programs.items():
                path = tools / name
                path.write_text(content)
                path.chmod(0o755)
            environment = root / 'environment-setup'
            lines = [f'export OECORE_TARGET_SYSROOT={shlex.quote(str(root / "target"))}',
                     f'export OECORE_NATIVE_SYSROOT={shlex.quote(str(native))}',
                     'export OECORE_TARGET_ARCH=aarch64']
            if variable:
                value = root / 'missing.cmake' if invalid else toolchain
                lines.append(f'export {variable}={shlex.quote(str(value))}')
            environment.write_text('\n'.join(lines) + '\n')
            log = root / 'cmake.log'
            env = dict(os.environ)
            for name in ('CMAKE_TOOLCHAIN_FILE', 'OE_CMAKE_TOOLCHAIN_FILE'):
                env.pop(name, None)
            env.update(PATH=str(tools) + ':' + env['PATH'], BUILD_TEST_LOG=str(log))
            result = subprocess.run(['bash', str(SCRIPT), str(environment)],
                                    env=env, text=True, capture_output=True)
            calls = log.read_text() if log.exists() else ''
            if result.returncode == 0:
                self.assertIn('-DCMAKE_TOOLCHAIN_FILE=' + str(toolchain), calls)
            return result, calls

    def test_current_sdk_variable(self):
        result, _ = self.build(variable='CMAKE_TOOLCHAIN_FILE')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_sdk_variable(self):
        result, _ = self.build(variable='OE_CMAKE_TOOLCHAIN_FILE')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_sysroot_fallback(self):
        result, _ = self.build(fallback=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_invalid_toolchain_never_configures_host_build(self):
        for options in ({}, {'variable': 'CMAKE_TOOLCHAIN_FILE', 'invalid': True}):
            with self.subTest(options=options):
                result, calls = self.build(**options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('SDK CMake toolchain file not found', result.stderr)
                self.assertEqual(calls, '')


if __name__ == '__main__':
    unittest.main()
