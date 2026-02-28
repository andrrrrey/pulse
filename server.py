import os
import uuid
import sqlite3
from datetime import datetime

import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db, get_conn

app = FastAPI(title="PULSE API")

# ─────────────────────────────────────────────
#  MARKERS
# ─────────────────────────────────────────────

@app.get("/api/markers")
def get_markers():
    with get_conn() as db:
        rows = db.execute("SELECT * FROM markers ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/markers")
def add_marker(data: dict):
    required = {"lat", "lng", "name"}
    if not required.issubset(data):
        raise HTTPException(400, "lat, lng и name обязательны")
    mid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_conn() as db:
        db.execute(
            """INSERT INTO markers
               (id,lat,lng,name,type,color,priority,info,coords_x,coords_y,zone,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                mid,
                data["lat"], data["lng"], data["name"],
                data.get("type", ""),
                data.get("color", "#f97316"),
                data.get("priority", "med"),
                data.get("info", ""),
                data.get("coords_x", 0),
                data.get("coords_y", 0),
                data.get("zone", 0),
                now,
            ),
        )
    return {"id": mid, "created_at": now}


@app.patch("/api/markers/{marker_id}")
def update_marker(marker_id: str, data: dict):
    fields = {k: v for k, v in data.items()
              if k in ("name", "type", "color", "priority", "info", "coords_x", "coords_y", "zone")}
    if not fields:
        raise HTTPException(400, "Нет допустимых полей для обновления")
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as db:
        db.execute(
            f"UPDATE markers SET {set_clause} WHERE id=?",
            (*fields.values(), marker_id),
        )
    return {"ok": True}


@app.delete("/api/markers/{marker_id}")
def delete_marker(marker_id: str):
    with get_conn() as db:
        db.execute("DELETE FROM markers WHERE id=?", (marker_id,))
    return {"ok": True}


# ─────────────────────────────────────────────
#  FREQUENCY TABLE
# ─────────────────────────────────────────────

@app.get("/api/freq")
def get_freq():
    with get_conn() as db:
        rows = db.execute("SELECT idx, state FROM freq_state").fetchall()
        return {str(r["idx"]): r["state"] for r in rows}


@app.put("/api/freq")
def save_freq(data: dict):
    with get_conn() as db:
        for idx, state in data.items():
            db.execute(
                "INSERT OR REPLACE INTO freq_state (idx, state) VALUES (?,?)",
                (int(idx), int(state)),
            )
    return {"ok": True}


# ─────────────────────────────────────────────
#  CHAT
# ─────────────────────────────────────────────

@app.get("/api/chat")
def get_chat(limit: int = 100):
    with get_conn() as db:
        rows = db.execute(
            "SELECT id, ts, user, role, text FROM chat_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


@app.post("/api/chat")
def send_message(data: dict):
    if not data.get("text", "").strip():
        raise HTTPException(400, "text обязателен")
    with get_conn() as db:
        db.execute(
            "INSERT INTO chat_messages (ts, user, role, text) VALUES (?,?,?,?)",
            (
                data.get("ts", datetime.utcnow().strftime("%H:%M")),
                data.get("user", "Вы"),
                data.get("role", "self"),
                data["text"].strip(),
            ),
        )
    return {"ok": True}


# ─────────────────────────────────────────────
#  BUG REPORTS
# ─────────────────────────────────────────────

@app.get("/api/reports")
def get_reports():
    with get_conn() as db:
        rows = db.execute(
            """SELECT id, title, category, priority, callsign, created_at
               FROM bug_reports ORDER BY rowid DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/reports")
def submit_report(data: dict):
    if not data.get("title", "").strip():
        raise HTTPException(400, "title обязателен")
    if not data.get("description", "").strip():
        raise HTTPException(400, "description обязателен")
    with get_conn() as db:
        count = db.execute("SELECT COUNT(*) FROM bug_reports").fetchone()[0]
        rid = f"#{1000 + count + 1}"
        now = datetime.utcnow().isoformat(timespec="seconds")
        db.execute(
            """INSERT INTO bug_reports
               (id,title,category,priority,description,steps,callsign,contact,sysinfo,files_count,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                data["title"].strip(),
                data.get("category", ""),
                data.get("priority", "med"),
                data.get("description", "").strip(),
                data.get("steps", ""),
                data.get("callsign", ""),
                data.get("contact", ""),
                data.get("sysinfo", ""),
                data.get("files_count", 0),
                now,
            ),
        )
    return {"id": rid, "created_at": now}


# ─────────────────────────────────────────────
#  FILE UPLOADS
# ─────────────────────────────────────────────

@app.post("/api/uploads")
async def upload_file(file: UploadFile = File(...)):
    allowed = {
        "image/png", "image/jpeg", "image/gif", "image/webp",
        "video/mp4", "video/quicktime", "video/webm",
    }
    if file.content_type not in allowed:
        raise HTTPException(400, f"Тип файла не поддерживается: {file.content_type}")

    os.makedirs("uploads", exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join("uploads", filename)

    async with aiofiles.open(path, "wb") as f:
        content = await file.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(400, "Файл превышает 25 МБ")
        await f.write(content)

    return {"url": f"/uploads/{filename}", "name": file.filename}


# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    with get_conn() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/settings")
def save_settings(data: dict):
    with get_conn() as db:
        for key, value in data.items():
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                (str(key), str(value)),
            )
    return {"ok": True}


# ─────────────────────────────────────────────
#  LEADERBOARD — PILOTS
# ─────────────────────────────────────────────

@app.get("/api/pilots")
def get_pilots():
    with get_conn() as db:
        pilots = db.execute("SELECT * FROM pilots ORDER BY callsign").fetchall()
        result = []
        for p in pilots:
            stats = db.execute(
                "SELECT * FROM pilot_stats WHERE pilot_id=?", (p["id"],)
            ).fetchall()
            stats_by_period = {s["period"]: dict(s) for s in stats}
            row = dict(p)
            row["stats"] = stats_by_period
            result.append(row)
    return result


@app.post("/api/pilots")
def add_pilot(data: dict):
    if not data.get("callsign", "").strip():
        raise HTTPException(400, "callsign обязателен")
    pid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_conn() as db:
        try:
            db.execute(
                "INSERT INTO pilots (id, callsign, unit, created_at) VALUES (?,?,?,?)",
                (pid, data["callsign"].strip(), data.get("unit", ""), now),
            )
        except Exception:
            raise HTTPException(409, "Позывной уже существует")
    return {"id": pid, "created_at": now}


@app.put("/api/pilots/{pilot_id}/stats")
def update_pilot_stats(pilot_id: str, data: dict):
    """Обновить или создать статистику пилота за период (week/month/all)."""
    period = data.get("period", "all")
    if period not in ("week", "month", "all"):
        raise HTTPException(400, "period: week | month | all")
    now = datetime.utcnow().isoformat(timespec="seconds")
    allowed = ("tech", "infantry", "comms", "agro", "delivery", "pos_fpv", "pos_wing", "queue", "flights")
    vals = {k: int(data.get(k, 0)) for k in allowed}
    with get_conn() as db:
        p = db.execute("SELECT id FROM pilots WHERE id=?", (pilot_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Пилот не найден")
        db.execute(
            """INSERT INTO pilot_stats
               (pilot_id,period,tech,infantry,comms,agro,delivery,pos_fpv,pos_wing,queue,flights,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(pilot_id,period) DO UPDATE SET
               tech=excluded.tech, infantry=excluded.infantry, comms=excluded.comms,
               agro=excluded.agro, delivery=excluded.delivery, pos_fpv=excluded.pos_fpv,
               pos_wing=excluded.pos_wing, queue=excluded.queue, flights=excluded.flights,
               updated_at=excluded.updated_at""",
            (pilot_id, period, *vals.values(), now),
        )
    return {"ok": True}


@app.patch("/api/pilots/{pilot_id}/stats")
def increment_pilot_stats(pilot_id: str, data: dict):
    """Инкрементально увеличить счётчики пилота за все периоды."""
    allowed = ("tech", "infantry", "comms", "agro", "delivery", "pos_fpv", "pos_wing", "queue", "flights")
    deltas = {k: int(data.get(k, 0)) for k in allowed if data.get(k)}
    if not deltas:
        raise HTTPException(400, "Нет допустимых полей")
    now = datetime.utcnow().isoformat(timespec="seconds")
    set_clause = ", ".join(f"{k}={k}+?" for k in deltas)
    with get_conn() as db:
        p = db.execute("SELECT id FROM pilots WHERE id=?", (pilot_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Пилот не найден")
        for period in ("week", "month", "all"):
            # Ensure row exists
            db.execute(
                """INSERT OR IGNORE INTO pilot_stats
                   (pilot_id,period,tech,infantry,comms,agro,delivery,pos_fpv,pos_wing,queue,flights,updated_at)
                   VALUES (?,?,0,0,0,0,0,0,0,0,0,?)""",
                (pilot_id, period, now),
            )
            db.execute(
                f"UPDATE pilot_stats SET {set_clause}, updated_at=? WHERE pilot_id=? AND period=?",
                (*deltas.values(), now, pilot_id, period),
            )
    return {"ok": True}


@app.delete("/api/pilots/{pilot_id}")
def delete_pilot(pilot_id: str):
    with get_conn() as db:
        db.execute("DELETE FROM pilot_stats WHERE pilot_id=?", (pilot_id,))
        db.execute("DELETE FROM pilots WHERE id=?", (pilot_id,))
    return {"ok": True}


# ─────────────────────────────────────────────
#  KILLFEED
# ─────────────────────────────────────────────

@app.get("/api/killfeed")
def get_killfeed(limit: int = 20):
    with get_conn() as db:
        rows = db.execute(
            "SELECT * FROM killfeed ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


@app.post("/api/killfeed")
def add_killfeed(data: dict):
    if not data.get("callsign", "").strip():
        raise HTTPException(400, "callsign обязателен")
    now = datetime.utcnow().strftime("%H:%M")
    with get_conn() as db:
        db.execute(
            "INSERT INTO killfeed (ts, callsign, target_type, coords, note) VALUES (?,?,?,?,?)",
            (
                data.get("ts", now),
                data["callsign"].strip(),
                data.get("target_type", ""),
                data.get("coords", ""),
                data.get("note", ""),
            ),
        )
    return {"ok": True}


# ─────────────────────────────────────────────
#  STATIC FILES  (должны быть ПОСЛЕ всех /api/...)
# ─────────────────────────────────────────────

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ─────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    print("✓ БД инициализирована")
    print("✓ PULSE запущен → http://localhost:8000")
