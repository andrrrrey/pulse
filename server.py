import os
import uuid
import json
import secrets
import sqlite3
from datetime import datetime, timedelta

import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from database import init_db, get_conn, hash_password

app = FastAPI(title="PULSE API")


# ─────────────────────────────────────────────
#  AUTH HELPERS
# ─────────────────────────────────────────────

def get_user_from_token(authorization: str | None) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    with get_conn() as db:
        row = db.execute(
            """SELECT u.id, u.username, u.role, u.callsign
               FROM sessions s JOIN users u ON s.user_id = u.id
               WHERE s.token = ?""",
            (token,),
        ).fetchone()
    return dict(row) if row else None


def require_auth(authorization: str | None) -> dict:
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(401, "Требуется авторизация")
    return user


# ─────────────────────────────────────────────
#  AUTH ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/api/auth/login")
def login(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        raise HTTPException(400, "Укажите логин и пароль")
    phash = hash_password(password)
    with get_conn() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND password_hash=?",
            (username, phash),
        ).fetchone()
    if not user:
        raise HTTPException(401, "Неверный логин или пароль")
    token = secrets.token_hex(32)
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_conn() as db:
        db.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
            (token, user["id"], now),
        )
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "callsign": user["callsign"],
        },
    }


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        with get_conn() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
    return {"ok": True}


@app.get("/api/auth/me")
def get_me(authorization: str | None = Header(None)):
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(401, "Требуется авторизация")
    return user


# ─────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────

@app.get("/api/notifications")
def get_notifications():
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_conn() as db:
        rows = db.execute(
            """SELECT * FROM notifications
               WHERE expires_at = '' OR expires_at > ?
               ORDER BY created_at DESC""",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/notifications")
def create_notification(data: dict):
    nid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat(timespec="seconds")
    ntype = data.get("type", "info")
    ndata = data.get("data", "")
    # expires_in_minutes: 0 = no expiry
    expires_in = int(data.get("expires_in_minutes", 0))
    expires_at = ""
    if expires_in > 0:
        expires_at = (datetime.utcnow() + timedelta(minutes=expires_in)).isoformat(timespec="seconds")
    with get_conn() as db:
        db.execute(
            "INSERT INTO notifications (id, type, data, created_at, expires_at) VALUES (?,?,?,?,?)",
            (nid, ntype, ndata, now, expires_at),
        )
    return {"id": nid, "created_at": now}


@app.delete("/api/notifications/{notif_id}")
def delete_notification(notif_id: str):
    with get_conn() as db:
        db.execute("DELETE FROM notifications WHERE id=?", (notif_id,))
    return {"ok": True}


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
    # expires_at for strike markers (30 min)
    expires_in = int(data.get("expires_in_minutes", 0))
    expires_at = ""
    if expires_in > 0:
        expires_at = (datetime.utcnow() + timedelta(minutes=expires_in)).isoformat(timespec="seconds")
    import json as _json
    attachments = data.get("attachments", [])
    attachments_str = _json.dumps(attachments) if attachments else ''
    with get_conn() as db:
        db.execute(
            """INSERT INTO markers
               (id,lat,lng,name,type,color,priority,info,coords_x,coords_y,zone,created_at,
                radius,extra,marker_role,expires_at,attachments)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                float(data.get("radius", 0)),
                data.get("extra", ""),
                data.get("marker_role", ""),
                expires_at,
                attachments_str,
            ),
        )
    return {"id": mid, "created_at": now}


@app.patch("/api/markers/{marker_id}")
def update_marker(marker_id: str, data: dict, authorization: str | None = Header(default=None)):
    user = require_auth(authorization)
    allowed_fields = {
        "name", "type", "color", "priority", "info",
        "coords_x", "coords_y", "zone", "radius", "extra", "marker_role",
    }
    fields = {k: v for k, v in data.items() if k in allowed_fields}
    if not fields:
        raise HTTPException(400, "Нет допустимых полей для обновления")
    if "radius" in fields and user["role"] not in ("reb", "admin"):
        raise HTTPException(403, "Изменять радиус РЭБ может только Специалист РЭБ или администратор")
    if "priority" in fields and user["role"] not in ("commander", "admin"):
        raise HTTPException(403, "Изменять приоритет метки может только Командир или администратор")
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
#  STREAMS
# ─────────────────────────────────────────────

# In-memory WebRTC signaling state (per-process, lost on restart — intentional)
_pilot_ws: dict = {}    # stream_id → WebSocket
_viewer_ws: dict = {}   # (stream_id, viewer_id) → WebSocket


@app.websocket("/ws/streams")
async def streams_signaling(websocket: WebSocket):
    await websocket.accept()
    role = None
    stream_id = None
    viewer_id = None
    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            t = msg.get("type")

            if t == "pilot-register":
                stream_id = msg.get("streamId")
                role = "pilot"
                if stream_id:
                    _pilot_ws[stream_id] = websocket

            elif t == "viewer-join":
                stream_id = msg.get("streamId")
                viewer_id = msg.get("viewerId")
                role = "viewer"
                if stream_id and viewer_id:
                    _viewer_ws[(stream_id, viewer_id)] = websocket
                    pilot = _pilot_ws.get(stream_id)
                    if pilot:
                        await pilot.send_text(json.dumps({
                            "type": "join-request",
                            "streamId": stream_id,
                            "viewerId": viewer_id,
                        }))

            elif t == "offer":
                target = _viewer_ws.get((msg.get("streamId"), msg.get("viewerId")))
                if target:
                    await target.send_text(raw)

            elif t == "answer":
                target = _pilot_ws.get(msg.get("streamId"))
                if target:
                    await target.send_text(raw)

            elif t == "ice-pilot":
                target = _viewer_ws.get((msg.get("streamId"), msg.get("viewerId")))
                if target:
                    await target.send_text(raw)

            elif t == "ice-viewer":
                target = _pilot_ws.get(msg.get("streamId"))
                if target:
                    await target.send_text(raw)

            elif t == "stream-ended":
                sid = msg.get("streamId")
                for (s, _v), ws in list(_viewer_ws.items()):
                    if s == sid:
                        try:
                            await ws.send_text(raw)
                        except Exception:
                            pass

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if role == "pilot" and stream_id:
            _pilot_ws.pop(stream_id, None)
            # Remove orphaned stream record if pilot disconnected without calling DELETE
            try:
                with get_conn() as db:
                    db.execute("DELETE FROM streams WHERE id=?", (stream_id,))
            except Exception:
                pass
        elif role == "viewer" and stream_id and viewer_id:
            _viewer_ws.pop((stream_id, viewer_id), None)

@app.get("/api/streams")
def get_streams():
    with get_conn() as db:
        rows = db.execute("SELECT * FROM streams ORDER BY started_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/streams")
def create_stream(data: dict, authorization: str | None = Header(None)):
    user = require_auth(authorization)
    sid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat(timespec="seconds")
    callsign = user.get("callsign") or user["username"]
    with get_conn() as db:
        db.execute(
            "INSERT INTO streams (id, callsign, title, started_at) VALUES (?,?,?,?)",
            (sid, callsign, data.get("title", ""), now),
        )
    return {"id": sid, "started_at": now}


@app.delete("/api/streams/{stream_id}")
def delete_stream(stream_id: str, authorization: str | None = Header(None)):
    require_auth(authorization)
    with get_conn() as db:
        db.execute("DELETE FROM streams WHERE id=?", (stream_id,))
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
