"""Docker worker regression tests. Docker daemon is not required for these mocks."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import worker


class WorkerTests(unittest.TestCase):
    def test_no_docker_is_fail_closed(self):
        with patch("worker.shutil.which", return_value=None):
            status, msg = worker.run_container("/not/a/path")
        self.assertEqual(status, "error")
        self.assertIn("NÃO realizada", msg)

    def test_unsafe_path_rejected_before_execution(self):
        with patch("worker.shutil.which", return_value="/usr/bin/docker"):
            status, _ = worker.run_container("/tmp")
        self.assertEqual(status, "error")

    def test_timeout_attempts_forced_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "abc"
            source.mkdir()
            (source / "main.py").write_text("print(1)")
            with patch.object(worker.store, "UPLOAD", root), \
                 patch("worker.shutil.which", return_value="/usr/bin/docker"), \
                 patch("worker._run_bounded", side_effect=subprocess.TimeoutExpired(["docker", "run"], 15)), \
                 patch("worker.subprocess.run") as run:
                run.side_effect = [
                    SimpleNamespace(returncode=0),
                    SimpleNamespace(returncode=1),
                ]
                status, msg = worker.run_container(str(source))
                self.assertEqual(status, "timeout")
                self.assertIn("removido", msg)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(run.call_args_list[0].args[0][1:3], ["rm", "-f"])
                self.assertEqual(run.call_args_list[1].args[0][1], "inspect")

    def test_failed_cleanup_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "abc"
            source.mkdir()
            (source / "main.py").write_text("print(1)")
            with patch.object(worker.store, "UPLOAD", root), \
                 patch("worker.shutil.which", return_value="/usr/bin/docker"), \
                 patch("worker.subprocess.run") as run:
                run.side_effect = [
                    subprocess.TimeoutExpired(["docker", "run"], 15),
                    SimpleNamespace(returncode=1),
                    SimpleNamespace(returncode=0),
                ]
                status, msg = worker.run_container(str(source))
                self.assertEqual(status, "error")
                self.assertTrue(msg.startswith("ALERTA:"))

    def test_truncated_output_uses_fixed_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "abc"
            source.mkdir()
            (source / "main.py").write_text("print(1)")
            with patch.object(worker.store, "UPLOAD", root), \
                 patch("worker.shutil.which", return_value="/usr/bin/docker"), \
                 patch("worker._run_bounded", return_value=(0, b"hello", True)):
                status, msg = worker.run_container(str(source))
            self.assertEqual(status, "passed")
            self.assertIn("truncada", msg)


if __name__ == "__main__":
    unittest.main()
