#!/usr/bin/env python3
"""Setup must never deploy or launch after a failed prerequisite."""
import subprocess
import unittest
from unittest.mock import patch

import standalone


class SetupTests(unittest.TestCase):
    def test_failed_build_does_not_touch_tablet(self):
        with patch('sys.argv', ['standalone.py', 'setup']), \
             patch.object(standalone, 'build_tablet', side_effect=RuntimeError('build failed')), \
             patch.object(standalone, 'deploy') as deploy, patch.object(standalone, 'run') as run:
            with self.assertRaises(RuntimeError):
                standalone.main()
            deploy.assert_not_called()
            run.assert_not_called()

    def test_setup_does_not_take_over_display_by_default(self):
        with patch('sys.argv', ['standalone.py', 'setup', '--host', 'rm']), \
             patch.object(standalone, 'build_tablet'), patch.object(standalone, 'deploy') as deploy, \
             patch.object(standalone, 'run') as run:
            standalone.main()
            deploy.assert_called_once_with('rm')
            run.assert_not_called()

    def test_failed_deployment_does_not_launch(self):
        with patch('sys.argv', ['standalone.py', 'setup', '--launch']), \
             patch.object(standalone, 'build_tablet'), \
             patch.object(standalone, 'deploy', side_effect=RuntimeError('probe failed')), \
             patch.object(standalone, 'run') as run:
            with self.assertRaises(RuntimeError):
                standalone.main()
            run.assert_not_called()

    def test_docker_permission_failure_is_actionable(self):
        result = subprocess.CompletedProcess([], 1, '', 'permission denied: docker.sock')
        with patch.object(standalone, 'docker_executable', return_value='docker'), \
             patch.object(standalone.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'normal Terminal'):
                standalone.check_docker()


if __name__ == '__main__':
    unittest.main()
