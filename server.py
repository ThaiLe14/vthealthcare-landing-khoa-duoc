#!/usr/bin/env python3
"""Static file server + survey submission API for the VT healthcare landing page.

Stores every "Đăng ký khảo sát quy trình" submission into a local SQLite
database (data/submissions.db) so it can be queried directly with plain SQL
(sqlite3 CLI, DB Browser for SQLite, etc.) after pulling the file down.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR
DB_PATH = BASE_DIR / "data" / "submissions.db"
PORT = int(os.environ.get("PORT", 8089))

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            position TEXT,
            hospital TEXT,
            phone TEXT NOT NULL,
            email TEXT,
            need TEXT,
            ip TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "VTHealthcareLanding/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        safe_path = os.path.normpath(path).lstrip("/\\")
        file_path = (STATIC_DIR / safe_path).resolve()
        if file_path != STATIC_DIR and STATIC_DIR not in file_path.parents:
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        ext = file_path.suffix.lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"
        self._serve_file(path)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/submit":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > 20000:
            self._send_json(400, {"ok": False, "error": "invalid body"})
            return

        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return

        name = str(data.get("name", "")).strip()[:200]
        position = str(data.get("position", "")).strip()[:200]
        hospital = str(data.get("hospital", "")).strip()[:300]
        phone = str(data.get("phone", "")).strip()[:50]
        email = str(data.get("email", "")).strip()[:200]
        need = str(data.get("need", "")).strip()[:2000]

        if not name or not phone:
            self._send_json(400, {"ok": False, "error": "missing name or phone"})
            return

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO submissions "
            "(created_at, name, position, hospital, phone, email, need, ip) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                name,
                position,
                hospital,
                phone,
                email,
                need,
                self.client_address[0],
            ),
        )
        conn.commit()
        conn.close()

        self._send_json(200, {"ok": True})


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving VT healthcare landing on 0.0.0.0:{PORT}")
    print(f"SQLite DB: {DB_PATH}")
    server.serve_forever()
