import sqlite3
import hashlib

DB_PATH = "pulse.db"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS markers (
                id          TEXT PRIMARY KEY,
                lat         REAL NOT NULL,
                lng         REAL NOT NULL,
                name        TEXT NOT NULL,
                type        TEXT DEFAULT '',
                color       TEXT DEFAULT '#f97316',
                priority    TEXT DEFAULT 'med',
                info        TEXT DEFAULT '',
                coords_x    INTEGER DEFAULT 0,
                coords_y    INTEGER DEFAULT 0,
                zone        INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS freq_state (
                idx     INTEGER PRIMARY KEY,
                state   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT NOT NULL,
                user    TEXT NOT NULL,
                role    TEXT DEFAULT 'self',
                text    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bug_reports (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                category    TEXT DEFAULT '',
                priority    TEXT DEFAULT 'med',
                description TEXT DEFAULT '',
                steps       TEXT DEFAULT '',
                callsign    TEXT DEFAULT '',
                contact     TEXT DEFAULT '',
                sysinfo     TEXT DEFAULT '',
                files_count INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pilots (
                id          TEXT PRIMARY KEY,
                callsign    TEXT NOT NULL UNIQUE,
                unit        TEXT DEFAULT '',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pilot_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pilot_id    TEXT NOT NULL REFERENCES pilots(id),
                period      TEXT NOT NULL DEFAULT 'all',
                tech        INTEGER DEFAULT 0,
                infantry    INTEGER DEFAULT 0,
                comms       INTEGER DEFAULT 0,
                agro        INTEGER DEFAULT 0,
                delivery    INTEGER DEFAULT 0,
                pos_fpv     INTEGER DEFAULT 0,
                pos_wing    INTEGER DEFAULT 0,
                queue       INTEGER DEFAULT 0,
                flights     INTEGER DEFAULT 0,
                updated_at  TEXT NOT NULL,
                UNIQUE(pilot_id, period)
            );

            CREATE TABLE IF NOT EXISTS killfeed (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                callsign    TEXT NOT NULL,
                target_type TEXT DEFAULT '',
                coords      TEXT DEFAULT '',
                note        TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'pilot',
                callsign      TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id         TEXT PRIMARY KEY,
                type       TEXT NOT NULL,
                data       TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT DEFAULT ''
            );
        """)

        # Migrate markers table — add new columns if missing
        for col_def in [
            "radius      REAL DEFAULT 0",
            "extra       TEXT DEFAULT ''",
            "marker_role TEXT DEFAULT ''",
            "expires_at  TEXT DEFAULT ''",
            "attachments TEXT DEFAULT ''",
        ]:
            col_name = col_def.split()[0]
            try:
                db.execute(f"ALTER TABLE markers ADD COLUMN {col_def}")
            except Exception:
                pass  # column already exists

        # Seed demo users (INSERT OR IGNORE — safe to run every startup)
        demo_users = [
            ("pilot-demo-id",     "pilot",     hash_password("pilot123"),     "pilot",     "Пилот-1"),
            ("scout-demo-id",     "scout",     hash_password("scout123"),     "scout",     "Разведчик-1"),
            ("reb-demo-id",       "reb",       hash_password("reb123"),       "reb",       "РЭБ-1"),
            ("rer-demo-id",       "rer",       hash_password("rer123"),       "rer",       "РЭР-1"),
            ("commander-demo-id", "commander", hash_password("commander123"), "commander", "Командир-1"),
            ("admin-demo-id",     "admin",     hash_password("admin123"),     "admin",     "Администратор"),
        ]
        for uid, uname, phash, role, callsign in demo_users:
            db.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, role, callsign) VALUES (?,?,?,?,?)",
                (uid, uname, phash, role, callsign),
            )
