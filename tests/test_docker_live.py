"""Live Docker validation for CI Linux runner and, later, Raspberry.

Run only with LAB_RUN_DOCKER_TESTS=1. No production submissions are used.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import worker

@unittest.skipUnless(os.getenv("LAB_RUN_DOCKER_TESTS") == "1", "requires Docker opt-in")
class LiveRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="labgateway-live-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "project"
        self.folder.mkdir()
        self.patch_root = patch.object(worker.store, "UPLOAD", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)

    def execute(self, script):
        (self.folder / "main.py").write_text(script, encoding="utf8")
        return worker.run_container(str(self.folder))

    def test_program_success(self):
        status, output = self.execute("print('OK:LABGATEWAY')\n")
        self.assertEqual(status, "passed", output)
        self.assertIn("OK:LABGATEWAY", output)

    def test_program_error(self):
        status, output = self.execute("raise ValueError('ERRO_CONTROLADO')\n")
        self.assertEqual(status, "failed", output)
        self.assertIn("ERRO_CONTROLADO", output)

    def test_output_truncation(self):
        status, output = self.execute("print('A'*100000)\n")
        self.assertEqual(status, "passed", output)
        self.assertLess(len(output), 13000)
        self.assertIn("truncada", output)

    def test_network_disabled(self):
        script = (
            "import socket\\n"
            "s=socket.socket();s.settimeout(2)\\n"
            "try:\\n"
            " s.connect(('1.1.1.1', 80));print('NETWORK_BROKEN')\\n"
            "except OSError:\\n"
            " print('NETWORK_BLOCKED')\\n"
        )
        status, output = self.execute(script)
        self.assertEqual(status, "passed", output)
        self.assertIn("NETWORK_BLOCKED", output)
        self.assertNotIn("NETWORK_BROKEN", output)

    def test_readonly_filesystem(self):
        script = (
            "try:\\n"
            " open('/submission/new.txt','w').write('x');print('WRITE_BROKEN')\\n"
            "except OSError:\\n"
            " print('READONLY_OK')\\n"
        )
        status, output = self.execute(script)
        self.assertEqual(status, "passed", output)
        self.assertIn("READONLY_OK", output)
        self.assertNotIn("WRITE_BROKEN", output)

    def test_timeout_and_no_orphan(self):
        status, output = self.execute("import time\ntime.sleep(60)\n")
        self.assertEqual(status, "timeout", output)
        self.assertIn("removido", output)

if __name__ == "__main__":
    unittest.main()
