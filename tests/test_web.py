"""Web API permission and submission tests; uses isolated temporary database."""
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("LAB_SECRET_KEY", "test-only-secret-not-for-production-" + "x" * 40)
import app as web
import store


def zip_project():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("main.py", "print(42)\n")
    out.seek(0)
    return out


class WebFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.dbpatch = patch.object(store, "DB", root / "gateway.sqlite3")
        self.uppatch = patch.object(store, "UPLOAD", root / "uploads")
        self.dbpatch.start()
        self.uppatch.start()
        self.addCleanup(self.dbpatch.stop)
        self.addCleanup(self.uppatch.stop)
        store.init()
        store.create_user("professor", "long-password-teacher", "teacher")
        store.create_user("grupo01", "long-password-student", "student")
        store.create_user("grupo02", "long-password-second", "student")
        self.client = web.app.test_client()

    def token(self):
        with self.client.session_transaction() as session:
            return session.get("csrf", "")

    def login(self, username, password):
        self.client.get("/login")
        return self.client.post("/login", data={
            "_csrf": self.token(), "username": username, "password": password
        })

    def upload(self):
        return self.client.post("/upload", data={
            "_csrf": self.token(), "title": "Projeto teste",
            "file": (zip_project(), "projeto.zip")
        }, content_type="multipart/form-data")

    def test_auth_required(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.location)

    def test_csrf_blocks_post(self):
        r = self.client.post("/login", data={
            "username": "professor", "password": "long-password-teacher"
        })
        self.assertEqual(r.status_code, 400)

    def test_upload_and_teacher_queue(self):
        self.login("grupo01", "long-password-student")
        self.assertEqual(self.upload().status_code, 302)
        with store.connect() as db:
            sid = db.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        self.assertEqual(self.client.get(f"/project/{sid}").status_code, 200)
        self.assertEqual(self.client.post(f"/queue/{sid}", data={"_csrf": self.token()}).status_code, 403)
        self.client.post("/logout", data={"_csrf": self.token()})
        self.login("professor", "long-password-teacher")
        self.assertEqual(self.client.post(f"/queue/{sid}", data={"_csrf": self.token()}).status_code, 302)
        with store.connect() as db:
            row = db.execute("SELECT status FROM runs WHERE submission_id=?", (sid,)).fetchone()
        self.assertEqual(row["status"], "queued")

    def test_teacher_can_download_project_named_from_title(self):
        self.login("grupo01", "long-password-student")
        self.upload()
        with store.connect() as db:
            sid = db.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        self.assertEqual(self.client.get(f"/project/{sid}/download").status_code, 403)
        self.client.post("/logout", data={"_csrf": self.token()})
        self.login("professor", "long-password-teacher")
        r = self.client.get(f"/project/{sid}/download")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment;", r.headers.get("Content-Disposition", ""))
        self.assertIn("Projeto_teste.zip", r.headers.get("Content-Disposition", ""))
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            self.assertEqual(z.read("main.py"), b"print(42)\n")

    def test_group_cannot_read_other_group_submission(self):
        self.login("grupo01", "long-password-student")
        self.upload()
        with store.connect() as db:
            sid = db.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        self.client.post("/logout", data={"_csrf": self.token()})
        self.login("grupo02", "long-password-second")
        self.assertEqual(self.client.get(f"/project/{sid}").status_code, 403)

    def test_invalid_upload_rejected(self):
        self.login("grupo01", "long-password-student")
        r = self.client.post("/upload", data={
            "_csrf": self.token(), "title": "invalid",
            "file": (io.BytesIO(b"not a zip"), "projeto.zip")
        }, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
