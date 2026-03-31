import sqlite3
from typing import Optional

class Database:
    def __init__(self, path="cleancity.db"):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE,
                    full_name TEXT,
                    username TEXT,
                    joined_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    full_name TEXT,
                    username TEXT,
                    photo_id TEXT,
                    lat REAL,
                    lon REAL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
            """)

    def save_user(self, user_id, full_name, username):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, username=excluded.username
            """, (user_id, full_name, username))

    def create_report(self, user_id, full_name, username, photo_id, lat, lon, description):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reports (user_id,full_name,username,photo_id,lat,lon,description) VALUES (?,?,?,?,?,?,?)",
                (user_id, full_name, username, photo_id, lat, lon, description)
            )
            return cur.lastrowid

    def get_report(self, report_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            return dict(row) if row else None

    def get_user_reports(self, user_id):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM reports WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def update_report_status(self, report_id, status):
        with self._conn() as conn:
            conn.execute("UPDATE reports SET status=?, updated_at=datetime('now') WHERE id=?", (status, report_id))

    def get_all_reports(self, status: Optional[str] = None):
        with self._conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM reports WHERE status=? ORDER BY id DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_stats(self):
        with self._conn() as conn:
            return {
                "total":     conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
                "pending":   conn.execute("SELECT COUNT(*) FROM reports WHERE status='pending'").fetchone()[0],
                "approved":  conn.execute("SELECT COUNT(*) FROM reports WHERE status='approved'").fetchone()[0],
                "completed": conn.execute("SELECT COUNT(*) FROM reports WHERE status='completed'").fetchone()[0],
                "users":     conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            }
