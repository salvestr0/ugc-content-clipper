"""Watchlist API routes — CRUD for monitored channels."""

import asyncio
import html
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse

from web.database import (
    get_db, add_watchlist, list_watchlist, delete_watchlist, update_watchlist,
    create_job, now_iso,
)
from web.jobs import start_pipeline
from config_loader import load_config

router = APIRouter()


@router.get("/watchlist")
async def get_watchlist():
    db = await get_db()
    try:
        channels = await list_watchlist(db)
    finally:
        await db.close()
    return channels


@router.post("/watchlist")
async def add_channel(request: Request):
    form = await request.form()
    channel_url = form.get("channel_url", "").strip()
    channel_name = form.get("channel_name", "").strip()

    if not channel_url:
        return JSONResponse({"error": "Channel URL is required"}, status_code=400)

    db = await get_db()
    try:
        wid = await add_watchlist(db, channel_url, channel_name or None)
        channels = await list_watchlist(db)
    finally:
        await db.close()

    # Return a table row for htmx
    ch = next((c for c in channels if c["id"] == wid), None)
    if ch:
        ch_id = html.escape(ch['id'])
        ch_name = html.escape(ch['channel_name'] or '—')
        ch_url = html.escape(ch['channel_url'])
        ch_url_short = html.escape(ch['channel_url'][:40])
        return HTMLResponse(f"""
        <tr id="wl-{ch_id}">
            <td>{ch_name}</td>
            <td><a href="{ch_url}" target="_blank">{ch_url_short}...</a></td>
            <td>Yes</td>
            <td>Never</td>
            <td>
                <fieldset role="group">
                    <button class="outline small"
                            hx-post="/api/watchlist/{ch_id}/check"
                            hx-target="#wl-{ch_id}"
                            hx-swap="outerHTML">Check Now</button>
                    <button class="outline secondary small"
                            hx-delete="/api/watchlist/{ch_id}"
                            hx-target="#wl-{ch_id}"
                            hx-swap="delete"
                            hx-confirm="Remove this channel?">Remove</button>
                </fieldset>
            </td>
        </tr>
        """)

    return JSONResponse({"id": wid})


@router.delete("/watchlist/{wid}")
async def remove_channel(wid: str):
    db = await get_db()
    try:
        await delete_watchlist(db, wid)
    finally:
        await db.close()
    return JSONResponse({"ok": True})


@router.post("/watchlist/{wid}/check")
async def check_channel(wid: str):
    """Fetch latest videos from channel and queue jobs for them."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM watchlist WHERE id=?", (wid,))
        row = await cursor.fetchone()
        if not row:
            return JSONResponse({"error": "Channel not found"}, status_code=404)

        ch = dict(row)
        channel_url = ch["channel_url"]

        # Fetch latest videos in a thread
        from downloader import get_latest_videos
        urls = await asyncio.to_thread(get_latest_videos, channel_url, count=3)

        # Queue jobs for each video
        config = load_config()
        config_json = json.dumps(config)
        job_ids = []
        for url in urls:
            job = await create_job(db, url, config_json=config_json)
            start_pipeline(job["id"], url, config)
            job_ids.append(job["id"])

        # Update last checked
        await update_watchlist(db, wid, last_checked_at=now_iso())
    finally:
        await db.close()

    ch_id = html.escape(ch['id'])
    ch_name = html.escape(ch['channel_name'] or '—')
    ch_url = html.escape(ch['channel_url'])
    ch_url_short = html.escape(ch['channel_url'][:40])
    return HTMLResponse(f"""
    <tr id="wl-{ch_id}">
        <td>{ch_name}</td>
        <td><a href="{ch_url}" target="_blank">{ch_url_short}...</a></td>
        <td>Yes</td>
        <td>Just now</td>
        <td>
            <span>Queued {len(job_ids)} jobs</span>
            <fieldset role="group">
                <button class="outline small"
                        hx-post="/api/watchlist/{ch_id}/check"
                        hx-target="#wl-{ch_id}"
                        hx-swap="outerHTML">Check Now</button>
                <button class="outline secondary small"
                        hx-delete="/api/watchlist/{ch_id}"
                        hx-target="#wl-{ch_id}"
                        hx-swap="delete"
                        hx-confirm="Remove this channel?">Remove</button>
            </fieldset>
        </td>
    </tr>
    """)
