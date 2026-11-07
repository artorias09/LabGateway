import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FornoReuseTests(unittest.TestCase):
    def test_audit_shell_syntax(self):
        p=ROOT/"scripts/audit_forno_reuse.sh"
        r=subprocess.run(["bash","-n",str(p)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_audit_is_read_only(self):
        script=(ROOT/"scripts/audit_forno_reuse.sh").read_text()
        for command in ("systemctl restart", "systemctl stop", "nmcli con mod",
                        "ngrok config add-authtoken", "ip route add", "ip route del",
                        "raspi-config", "cat /etc/wpa_supplicant", "cat ~/.config/ngrok"):
            self.assertNotIn(command,script)

    def test_reuse_doc_does_not_require_forno_reinstallation(self):
        content=(ROOT/"docs/REAPROVEITAMENTO_FORNO.md").read_text()
        self.assertIn("127.0.0.1:5001",content)
        self.assertIn("scripts/audit_forno_reuse.sh",content)
        self.assertIn("Não formatar",content)
