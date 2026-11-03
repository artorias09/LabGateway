import os
import unittest
os.environ.setdefault("LAB_SECRET_KEY", "test-only-" + "x" * 48)
from app import app

class InterfaceTests(unittest.TestCase):
    def test_login_renders(self):
        c = app.test_client()
        r = c.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Acesso ao laborat", r.data)
        self.assertNotIn(b"\xf0\x9f", r.data)
        self.assertIn(b"/static/app.css", r.data)
    def test_css_available(self):
        c = app.test_client()
        r = c.get("/static/app.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b".panel", r.data)
    def test_protection_headers(self):
        c = app.test_client()
        r = c.get("/login")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertIn("form-action 'self'", r.headers.get("Content-Security-Policy", ""))

if __name__ == "__main__":
    unittest.main()
