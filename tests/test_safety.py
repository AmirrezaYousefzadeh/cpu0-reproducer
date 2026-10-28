import os
from pathlib import Path
import pwd
import tempfile
import json
import unittest
from unittest.mock import patch
import controls
import matrix
from run import classify


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_root = Path(__file__).resolve().parents[1] / ".build"
        cls.temporary_root.mkdir(exist_ok=True)

    def test_setup_error_is_not_counted_as_hardware_failure(self):
        log = "filesystem error: Permission denied [/root/.openroad]\nSignal 6 received"
        self.assertEqual(classify(log, 1), "setup_error")
        self.assertEqual(classify("Signal 11 received", 1), "SIGSEGV")
        self.assertEqual(classify("CPU_AFFINITY_REPRO_SUCCESS", 0), "pass")

    def test_sudo_home_is_restored_to_the_workload_owner(self):
        account = pwd.getpwuid(os.getuid())
        with patch.dict(os.environ, {"HOME": "/root", "USER": "root"}):
            env = matrix.user_environment(account)
        self.assertEqual(env["HOME"], account.pw_dir)
        self.assertEqual(env["USER"], account.pw_name)

    def test_partial_cap_failure_restores_both_original_limits(self):
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as d:
            paths = {c: Path(d) / str(c) for c in (0, 6)}
            for p in paths.values():
                p.mkdir(); (p / "scaling_max_freq").write_text("5700000\n")
            original = controls.write_limit
            def failing(directory, value):
                if directory == paths[6] and value == 3700000:
                    raise OSError("simulated write failure")
                original(directory, value)
            with patch.object(controls, "write_limit", failing):
                with self.assertRaises(OSError):
                    with controls.temporary_limits(paths, {0: 5700000, 6: 5700000}, 3700000):
                        self.fail("Body should not start")
            self.assertTrue(all(int((p / "scaling_max_freq").read_text()) == 5700000 for p in paths.values()))

    def test_interrupt_during_workload_restores_limits(self):
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as d:
            paths = {c: Path(d) / str(c) for c in (0, 6)}
            for p in paths.values():
                p.mkdir(); (p / "scaling_max_freq").write_text("5700000\n")
            with self.assertRaises(KeyboardInterrupt):
                with controls.temporary_limits(paths, {0: 5700000, 6: 5700000}, 3700000):
                    raise KeyboardInterrupt()
            self.assertTrue(all(int((p / "scaling_max_freq").read_text()) == 5700000 for p in paths.values()))

    def test_queued_matrix_rejects_incomplete_or_failed_control_sweep(self):
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as d:
            root = Path(d); (root / "sweep").mkdir()
            description = {"label": "sweep", "cpus": [0, 6], "trials": 1}
            a = {"cpu": 0, "trial": 1, "classification": "SIGSEGV", "stop_reason": None}
            b = {"cpu": 6, "trial": 1, "classification": "pass", "stop_reason": None}
            p = root / "sweep/results.json"
            p.write_text(json.dumps([a]))
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                matrix.validate_sweep(root, description)
            b["classification"] = "SIGSEGV"; p.write_text(json.dumps([a, b]))
            with self.assertRaisesRegex(RuntimeError, "CPU 6 failed"):
                matrix.validate_sweep(root, description)
            b["classification"] = "pass"; p.write_text(json.dumps([a, b]))
            matrix.validate_sweep(root, description)


if __name__ == "__main__":
    unittest.main()
