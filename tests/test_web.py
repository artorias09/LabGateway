"""Web API permission and submission tests; uses isolated temporary database."""
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("LAB_SECRET_KEY", "test-only-secret-not-for-production-" + "x" * 40)
os.environ.setdefault("LAB_INGEST_TOKEN", "test-ingest-token-" + "x" * 32)
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
        self.datapatch = patch.object(store, "DATASET_UPLOAD", root / "datasets")
        self.dbpatch.start()
        self.uppatch.start()
        self.datapatch.start()
        self.addCleanup(self.dbpatch.stop)
        self.addCleanup(self.uppatch.stop)
        self.addCleanup(self.datapatch.stop)
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

    def test_dataset_upload_and_teacher_access(self):
        self.login("grupo01", "long-password-student")
        r = self.client.post("/datasets/upload", data={
            "_csrf": self.token(),
            "title": "Ensaio temperatura",
            "description": "Leitura do sensor",
            "units": "tempo (s), temperatura (C)",
            "submission_id": "",
            "file": (io.BytesIO(b"tempo,temp\n0,25.1\n1,25.4\n"), "ensaio.csv"),
        }, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        with store.connect() as db:
            row = db.execute("SELECT * FROM datasets LIMIT 1").fetchone()
        self.assertEqual(row["row_count"], 2)
        self.assertEqual(row["file_type"], "csv")
        did = row["id"]
        self.assertEqual(self.client.get(f"/dataset/{did}").status_code, 200)
        self.client.post("/logout", data={"_csrf": self.token()})
        self.login("professor", "long-password-teacher")
        detail = self.client.get(f"/dataset/{did}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Ensaio temperatura", detail.data)
        download = self.client.get(f"/dataset/{did}/download")
        self.assertEqual(download.status_code, 200)
        self.assertIn("ensaio.csv", download.headers.get("Content-Disposition", ""))

    def test_other_group_cannot_read_dataset(self):
        self.login("grupo01", "long-password-student")
        self.client.post("/datasets/upload", data={
            "_csrf": self.token(),
            "title": "Dados privados",
            "description": "",
            "units": "",
            "submission_id": "",
            "file": (io.BytesIO(b"x,y\n1,2\n"), "dados.csv"),
        }, content_type="multipart/form-data")
        with store.connect() as db:
            did = db.execute("SELECT id FROM datasets LIMIT 1").fetchone()["id"]
        self.client.post("/logout", data={"_csrf": self.token()})
        self.login("grupo02", "long-password-second")
        self.assertEqual(self.client.get(f"/dataset/{did}").status_code, 403)
        self.assertEqual(self.client.get(f"/dataset/{did}/download").status_code, 403)

    def test_linked_dataset_appears_on_project_page(self):
        self.login("grupo01", "long-password-student")
        self.upload()
        with store.connect() as db:
            sid = db.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        self.client.post("/datasets/upload", data={
            "_csrf": self.token(),
            "title": "Curva do sensor",
            "description": "",
            "units": "tempo (s), tensao (V)",
            "submission_id": str(sid),
            "file": (io.BytesIO(b"tempo,tensao\n0,1.0\n"), "curva.csv"),
        }, content_type="multipart/form-data")
        project = self.client.get(f"/project/{sid}")
        self.assertEqual(project.status_code, 200)
        self.assertIn(b"Curva do sensor", project.data)
        self.assertIn(b"Dados experimentais vinculados", project.data)


    def test_esp32_ingest_creates_station_and_measurements(self):
        payload = {
            "station": "grupo_01",
            "name": "Estacao 01",
            "group": "Grupo 01",
            "data": {"temperatura": 24.7, "umidade": 61.2},
            "units": {"temperatura": "C", "umidade": "%"},
        }
        r = self.client.post("/api/v1/measurements", json=payload, headers={
            "X-LabGateway-Token": os.environ["LAB_INGEST_TOKEN"]
        })
        self.assertEqual(r.status_code, 201)
        with store.connect() as db:
            station = db.execute("SELECT * FROM stations WHERE station_key='grupo_01'").fetchone()
            rows = db.execute("SELECT * FROM measurements WHERE station_id=? ORDER BY metric",(station["id"],)).fetchall()
        self.assertEqual(station["name"], "Estacao 01")
        self.assertEqual(len(rows), 2)

    def test_esp32_ingest_rejects_bad_token(self):
        r = self.client.post("/api/v1/measurements", json={
            "station": "grupo_01", "data": {"temperatura": 20}
        }, headers={"X-LabGateway-Token": "errado"})
        self.assertEqual(r.status_code, 401)

    def test_teacher_can_open_station_monitor(self):
        self.client.post("/api/v1/measurements", json={
            "station": "grupo_01", "name": "Estacao 01",
            "data": {"temperatura": 20.5}, "units": {"temperatura": "C"}
        }, headers={"X-LabGateway-Token": os.environ["LAB_INGEST_TOKEN"]})
        self.login("professor", "long-password-teacher")
        overview = self.client.get("/monitor")
        self.assertEqual(overview.status_code, 200)
        self.assertIn(b"Estacao 01", overview.data)
        with store.connect() as db:
            station_id = db.execute("SELECT id FROM stations WHERE station_key='grupo_01'").fetchone()["id"]
        detail = self.client.get(f"/monitor/{station_id}")
        self.assertEqual(detail.status_code, 200)
        series = self.client.get(f"/api/v1/stations/{station_id}/series?metric=temperatura")
        self.assertEqual(series.status_code, 200)
        self.assertEqual(series.get_json()["points"][0]["value"], 20.5)

    def test_station_human_name_is_used_without_changing_station_key(self):
        r = self.client.post("/api/v1/measurements", json={
            "station": "esp32_A0FD678DBD44",
            "name": "Grupo 3 - Estacao Meteorologica",
            "data": {"Temperatura": 26.4},
            "units": {"Temperatura": "C"},
        }, headers={"X-LabGateway-Token": os.environ["LAB_INGEST_TOKEN"]})
        self.assertEqual(r.status_code, 201)

        with store.connect() as db:
            station = db.execute(
                "SELECT * FROM stations WHERE station_key='esp32_A0FD678DBD44'"
            ).fetchone()

        self.assertEqual(station["station_key"], "esp32_A0FD678DBD44")
        self.assertEqual(station["name"], "Grupo 3 - Estacao Meteorologica")

        self.login("professor", "long-password-teacher")
        overview = self.client.get("/monitor")
        self.assertIn(b"Grupo 3 - Estacao Meteorologica", overview.data)
        self.assertIn(b"esp32_A0FD678DBD44", overview.data)

    def test_semantic_measurements_keep_names_and_units_in_csv(self):
        for temp, hum in ((24.5, 62.0), (24.8, 61.7)):
            r = self.client.post("/api/v1/measurements", json={
                "station": "estacao_semantica",
                "name": "Estacao Semantica",
                "data": {
                    "Temperatura": temp,
                    "Umidade": hum,
                },
                "units": {
                    "Temperatura": "C",
                    "Umidade": "%",
                },
            }, headers={"X-LabGateway-Token": os.environ["LAB_INGEST_TOKEN"]})
            self.assertEqual(r.status_code, 201)

        self.login("professor", "long-password-teacher")
        with store.connect() as db:
            station_id = db.execute(
                "SELECT id FROM stations WHERE station_key='estacao_semantica'"
            ).fetchone()["id"]

        detail = self.client.get(f"/monitor/{station_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Temperatura", detail.data)
        self.assertIn(b"Umidade", detail.data)
        self.assertIn(b"C", detail.data)

        series = self.client.get(
            f"/api/v1/stations/{station_id}/series?metric=Temperatura"
        )
        self.assertEqual(series.status_code, 200)
        body = series.get_json()
        self.assertEqual(body["label"], "Temperatura")
        self.assertEqual(body["points"][-1]["unit"], "C")

        csv_response = self.client.get(f"/monitor/{station_id}/download.csv")
        self.assertEqual(csv_response.status_code, 200)
        csv_text = csv_response.data.decode("utf-8-sig")
        self.assertIn("Temperatura (C)", csv_text)
        self.assertIn("Umidade (%)", csv_text)
        self.assertIn("24.5", csv_text)
        self.assertIn("24.8", csv_text)

    def test_teacher_can_rename_metrics_and_download_station_csv(self):
        for temp, hum in ((20.5, 60.0), (21.0, 61.0)):
            self.client.post("/api/v1/measurements", json={
                "station": "grupo_csv", "name": "Estacao CSV",
                "data": {"variavel_1": temp, "variavel_2": hum}
            }, headers={"X-LabGateway-Token": os.environ["LAB_INGEST_TOKEN"]})
        self.login("professor", "long-password-teacher")
        with store.connect() as db:
            station_id = db.execute("SELECT id FROM stations WHERE station_key='grupo_csv'").fetchone()["id"]

        r = self.client.post(f"/monitor/{station_id}/labels", data={
            "_csrf": self.token(),
            "label_variavel_1": "Temperatura",
            "unit_variavel_1": "C",
            "label_variavel_2": "Umidade",
            "unit_variavel_2": "%",
        })
        self.assertEqual(r.status_code, 302)

        detail = self.client.get(f"/monitor/{station_id}")
        self.assertIn(b"Temperatura", detail.data)
        self.assertIn(b"Umidade", detail.data)

        csv_response = self.client.get(f"/monitor/{station_id}/download.csv")
        self.assertEqual(csv_response.status_code, 200)
        text = csv_response.data.decode("utf-8-sig")
        self.assertIn("Temperatura (C)", text)
        self.assertIn("Umidade (%)", text)
        self.assertIn("20.5", text)
        self.assertIn("21.0", text)


if __name__ == "__main__":
    unittest.main()
