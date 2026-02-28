import sqlite3

DB_PATH = "pulse.db"


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
        """)
