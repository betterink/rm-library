#!/usr/bin/env python3
"""Check the runner's preflight and transient-service contract without a tablet."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def run_runner(self, pen_input=None, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            programs = {
                'probe': '#!/bin/sh\nexit "${PROBE_RESULT:-0}"\n',
                'systemctl': '''#!/bin/sh
if test "$1" = is-active; then
    case "$*" in
        *xochitl*) exit "${XOCHITL_RESULT:-0}" ;;
        *) exit "${BENCHMARK_RESULT:-1}" ;;
    esac
fi
exit 0
''',
                'find': '''#!/bin/sh
test "${PLUGINS_MISSING:-0}" = 0 || exit 0
case "$*" in
    *evdevtablet*) test "${TABLET_PLUGIN_MISSING:-0}" = 0 || exit 0 ;;
esac
echo /usr/lib/plugins/test-epaper.so
''',
                'systemd-run': '#!/bin/sh\nprintf "%s\\n" "$@" > "$UNIT_ARGS"\n',
            }
            for name, content in programs.items():
                (root / name).write_text(content)
                (root / name).chmod(0o755)
            script = (ROOT / 'standalone/run-on-tablet.sh').read_text().replace(
                'app=/home/root/ink-benchmark/current/ink-benchmark', f'app={root}/probe')
            runner = root / 'runner.sh'
            runner.write_text(script)
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                       UNIT_ARGS=str(root / 'unit-args'), **overrides)
            result = subprocess.run(['sh', str(runner)] + ([pen_input] if pen_input else []),
                                    env=env, capture_output=True, text=True)
            arguments = (root / 'unit-args').read_text().splitlines() if (root / 'unit-args').exists() else []
            return result, arguments

    def test_service_has_restore_timeout_and_separate_epaper_process(self):
        result, args = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--collect', args)
        self.assertIn('--property=RuntimeMaxSec=600', args)
        self.assertTrue(any(a.startswith('--property=ExecStartPre=') and a.endswith(' stop xochitl') for a in args))
        self.assertTrue(any(a.startswith('--property=ExecStopPost=') and a.endswith(' start xochitl') for a in args))
        self.assertIn('--setenv=QT_QUICK_BACKEND=epaper', args)
        self.assertIn('--setenv=LD_PRELOAD=', args)
        self.assertEqual(args[-3:], ['--fullscreen', '-platform', 'epaper'])

    def test_preflight_failures_do_not_launch_service(self):
        for configuration in ({'PROBE_RESULT': '127'}, {'XOCHITL_RESULT': '1'},
                              {'BENCHMARK_RESULT': '0'}, {'PLUGINS_MISSING': '1'}):
            with self.subTest(configuration=configuration):
                result, args = self.run_runner(**configuration)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(args, [])

    def test_requested_pen_plugin_is_enabled(self):
        result, args = self.run_runner(pen_input='evdevtablet')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--setenv=QT_QPA_GENERIC_PLUGINS=evdevtablet', args)

    def test_missing_pen_plugin_does_not_stop_native_interface(self):
        result, args = self.run_runner(pen_input='evdevtablet', TABLET_PLUGIN_MISSING='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('evdevtablet plugin not installed', result.stderr)
        self.assertEqual(args, [])


if __name__ == '__main__':
    unittest.main()
