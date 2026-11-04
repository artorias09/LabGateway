"""Static deployment contracts, independent of Raspberry hardware."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DeploymentContracts(unittest.TestCase):
    def test_shell_syntax(self):
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            with self.subTest(script=path.name):
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_separate_services(self):
        web = (ROOT / "deploy/labgateway-web.service").read_text()
        worker = (ROOT / "deploy/labgateway-worker.service").read_text()
        self.assertIn("Group=labdata", web)
        self.assertIn("Group=labdata", worker)
        self.assertIn("127.0.0.1:5001", web)
        self.assertNotIn("SupplementaryGroups=docker", web)
        self.assertIn("SupplementaryGroups=docker", worker)
        self.assertNotIn("forno.service", web)
        self.assertNotIn("forno.service", worker)

    def test_armv7_requires_verified_memory_cgroup(self):
        installer = (ROOT / "scripts/install_pi.sh").read_text()
        self.assertIn("aarch64|armv7l", installer)
        self.assertIn('docker run --rm --network none --memory 128m --memory-swap 128m', installer)
        self.assertIn('134217728', installer)

    def test_smoke_directory_is_readable_by_unprivileged_container(self):
        script = (ROOT / "scripts/smoke_pi.sh").read_text()
        self.assertIn('chmod 755 "$TMP"', script)

    def test_installer_preserves_forno_and_eduroam(self):
        installer = (ROOT / "scripts/install_pi.sh").read_text()
        self.assertIn('MODE="${1:---check}"', installer)
        self.assertIn('if [ "$MODE" = "--check" ]; then', installer)
        for forbidden in ("systemctl restart forno", "systemctl stop forno",
                          "nmcli con mod", "raspi-config", "ngrok config add-authtoken",
                          "apt upgrade", "apt full-upgrade"):
            self.assertNotIn(forbidden, installer)

if __name__ == "__main__":
    unittest.main()
