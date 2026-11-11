import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

DB = Path(os.environ.get('LAB_DB', 'data/labgateway.sqlite3'))
UPLOAD = Path(os.environ.get('LAB_UPLOADS', 'data/uploads'))
DATASET_UPLOAD = Path(os.environ.get('LAB_DATASETS', 'data/datasets'))

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=15000')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init():
    UPLOAD.mkdir(parents=True, exist_ok=True)
    DATASET_UPLOAD.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('teacher','student')));
          CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES submissions(id), status TEXT NOT NULL CHECK(status IN ('queued','running','passed','failed','timeout','error')), output TEXT NOT NULL DEFAULT '', started_at TEXT, finished_at TEXT);
          CREATE TABLE IF NOT EXISTS datasets(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), submission_id INTEGER REFERENCES submissions(id), title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', units TEXT NOT NULL DEFAULT '', original_name TEXT NOT NULL, path TEXT NOT NULL, file_type TEXT NOT NULL CHECK(file_type IN ('csv','json')), row_count INTEGER NOT NULL DEFAULT 0, columns_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS idx_submissions_user ON submissions(user_id);
          CREATE INDEX IF NOT EXISTS idx_datasets_user ON datasets(user_id);
          CREATE INDEX IF NOT EXISTS idx_datasets_submission ON datasets(submission_id);
          CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        ''')

def create_user(username, password, role):
    if role not in ('teacher','student'):
        raise ValueError('role inválida')
    if len(password) < 12:
        raise ValueError('senha deve ter ao menos 12 caracteres')
    with connect() as db:
        db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                   (username,generate_password_hash(password),role))

def verify(username,password):
    with connect() as db:
        row = db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if row and check_password_hash(row['password_hash'],password):
        return dict(row)
    return None

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
