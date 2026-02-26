"""SQLite database layer for Viral Clipper Web UI."""

import aiosqlite
import uuid
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / "data" / "clipper.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    video_id TEXT,
    video_title TEXT,
    channel TEXT,
    duration_seconds INTEGER,
    status TEXT NOT NULL DEFAULT 'queued',
    stage INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    config_json TEXT,
    output_dir TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    rank INTEGER,
    start_seconds REAL,
    end_seconds REAL,
    duration REAL,
    hook TEXT,
    viral_score INTEGER,
    why_viral TEXT,
    emotional_trigger TEXT,
    suggested_caption TEXT,
    clip_text TEXT,
    output_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    user_start_override REAL,
    user_end_override REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    channel_url TEXT NOT NULL UNIQUE,
    channel_name TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    created_at TEXT NOT NULL
);
"""


async def get_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Job helpers ──

async def create_job(db: aiosqlite.Connection, url: str, config_json: str = None) -> dict:
    job_id = new_id()
    ts = now_iso()
    await db.execute(
        "INSERT INTO jobs (id, url, status, stage, config_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (job_id, url, "queued", 0, config_json, ts, ts),
    )
    await db.commit()
    return {"id": job_id, "url": url, "status": "queued", "stage": 0, "created_at": ts}


async def update_job(db: aiosqlite.Connection, job_id: str, **fields):
    fields["updated_at"] = now_iso()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    await db.execute(f"UPDATE jobs SET {sets} WHERE id=?", vals)
    await db.commit()


async def get_job(db: aiosqlite.Connection, job_id: str) -> dict | None:
    cursor = await db.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_jobs(db: aiosqlite.Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def delete_job(db: aiosqlite.Connection, job_id: str):
    await db.execute("DELETE FROM clips WHERE job_id=?", (job_id,))
    await db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    await db.commit()


# ── Clip helpers ──

async def create_clip(db: aiosqlite.Connection, job_id: str, clip_data: dict) -> str:
    clip_id = new_id()
    ts = now_iso()
    await db.execute(
        """INSERT INTO clips
           (id, job_id, rank, start_seconds, end_seconds, duration,
            hook, viral_score, why_viral, emotional_trigger, suggested_caption, clip_text,
            output_path, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            clip_id, job_id,
            clip_data.get("rank"), clip_data.get("start_seconds"), clip_data.get("end_seconds"),
            clip_data.get("duration"), clip_data.get("hook"), clip_data.get("viral_score"),
            clip_data.get("why_viral"), clip_data.get("emotional_trigger"),
            clip_data.get("suggested_caption"), clip_data.get("clip_text"),
            clip_data.get("output_path"), "pending", ts,
        ),
    )
    await db.commit()
    return clip_id


async def get_clips_for_job(db: aiosqlite.Connection, job_id: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM clips WHERE job_id=? ORDER BY rank", (job_id,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_clip(db: aiosqlite.Connection, clip_id: str) -> dict | None:
    cursor = await db.execute("SELECT * FROM clips WHERE id=?", (clip_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_clip(db: aiosqlite.Connection, clip_id: str, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [clip_id]
    await db.execute(f"UPDATE clips SET {sets} WHERE id=?", vals)
    await db.commit()


# ── Watchlist helpers ──

async def add_watchlist(db: aiosqlite.Connection, channel_url: str, channel_name: str = None) -> str:
    wid = new_id()
    ts = now_iso()
    await db.execute(
        "INSERT INTO watchlist (id, channel_url, channel_name, enabled, created_at) VALUES (?,?,?,?,?)",
        (wid, channel_url, channel_name or "", 1, ts),
    )
    await db.commit()
    return wid


async def list_watchlist(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute("SELECT * FROM watchlist ORDER BY created_at DESC")
    return [dict(r) for r in await cursor.fetchall()]


async def delete_watchlist(db: aiosqlite.Connection, wid: str):
    await db.execute("DELETE FROM watchlist WHERE id=?", (wid,))
    await db.commit()


async def update_watchlist(db: aiosqlite.Connection, wid: str, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [wid]
    await db.execute(f"UPDATE watchlist SET {sets} WHERE id=?", vals)
    await db.commit()
