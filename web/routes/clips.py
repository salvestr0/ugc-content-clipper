"""Clip API routes — review, update, rerender."""

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse

from web.database import get_db, get_clip, update_clip, get_job

router = APIRouter()


@router.get("/clips/{clip_id}")
async def get_clip_detail(clip_id: str):
    db = await get_db()
    try:
        clip = await get_clip(db, clip_id)
        if not clip:
            return JSONResponse({"error": "Clip not found"}, status_code=404)
    finally:
        await db.close()
    return clip


@router.patch("/clips/{clip_id}")
async def update_clip_route(request: Request, clip_id: str):
    form = await request.form()
    updates = {}
    if "status" in form:
        updates["status"] = form["status"]
    if "user_start_override" in form:
        updates["user_start_override"] = float(form["user_start_override"])
    if "user_end_override" in form:
        updates["user_end_override"] = float(form["user_end_override"])

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    db = await get_db()
    try:
        await update_clip(db, clip_id, **updates)
        clip = await get_clip(db, clip_id)
        job = await get_job(db, clip["job_id"])
    finally:
        await db.close()

    # Return refreshed clip card HTML for htmx outerHTML swap.
    # clip_card.html renders <div class="clip-card ... " id="clip-{id}"> so the
    # swap correctly replaces the element targeted by #clip-{id}.
    templates = request.app.state.templates
    card_html = templates.get_template("_partials/clip_card.html").render(
        clip=clip, job=job, request=request
    )
    return HTMLResponse(card_html)


@router.post("/clips/{clip_id}/rerender")
async def rerender_clip(request: Request, clip_id: str):
    form = await request.form()
    start_seconds = float(form["start_seconds"])
    end_seconds = float(form["end_seconds"])

    if end_seconds <= start_seconds:
        return HTMLResponse('<p class="toast toast-error">End must be after start.</p>')

    db = await get_db()
    try:
        clip = await get_clip(db, clip_id)
        if not clip:
            return HTMLResponse('<p class="toast toast-error">Clip not found.</p>')

        job = await get_job(db, clip["job_id"])
        if not job:
            return HTMLResponse('<p class="toast toast-error">Job not found.</p>')

        # Save the overrides
        await update_clip(db, clip_id,
                          user_start_override=start_seconds,
                          user_end_override=end_seconds)
    finally:
        await db.close()

    # Re-render in background thread
    try:
        from config_loader import load_config
        config = json.loads(job["config_json"]) if job.get("config_json") else load_config()

        # Load transcript words for captions
        from pathlib import Path
        transcript_path = Path("output/metadata") / f"{job['video_id']}_transcript.json"
        words = []
        if transcript_path.exists():
            with open(transcript_path, encoding="utf-8") as f:
                transcript = json.load(f)
                words = transcript.get("words", [])

        # Build clip_data with overridden timestamps
        clip_data = {
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "duration": end_seconds - start_seconds,
            "rank": clip["rank"],
            "viral_score": clip["viral_score"],
            "hook": clip["hook"],
            "emotional_trigger": clip["emotional_trigger"],
        }

        video_path = f"output/source/{job['video_id']}.mp4"

        from clip_editor import create_clip as make_clip
        output_path = await asyncio.to_thread(
            make_clip,
            video_path=video_path,
            clip_data=clip_data,
            words=words,
            output_dir=job["output_dir"] or f"output/clips/{job['video_id']}",
            config=config,
            clip_index=clip["rank"],
        )

        if output_path:
            db2 = await get_db()
            try:
                await update_clip(db2, clip_id, output_path=output_path)
            finally:
                await db2.close()
            return HTMLResponse('<p class="toast toast-success">Re-rendered successfully. Refresh to see updated clip.</p>')
        else:
            return HTMLResponse('<p class="toast toast-error">FFmpeg failed. Check server logs.</p>')

    except Exception as e:
        return HTMLResponse(f'<p class="toast toast-error">Error: {e}</p>')
