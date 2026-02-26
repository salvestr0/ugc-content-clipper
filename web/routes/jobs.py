"""Job API routes — submit, list, progress SSE."""

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from web.database import get_db, create_job, get_job, list_jobs, delete_job, get_clips_for_job
from web.models import JobCreate
from web.jobs import start_pipeline, cancel_pipeline
from config_loader import load_config

router = APIRouter()


@router.post("/jobs")
async def submit_job(request: Request):
    form = await request.form()
    url = form.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)

    config = load_config()
    config_json = json.dumps(config)

    db = await get_db()
    try:
        job = await create_job(db, url, config_json=config_json)
    finally:
        await db.close()

    # Start pipeline in background
    start_pipeline(job["id"], url, config)

    return JSONResponse({"id": job["id"], "status": "queued"})


@router.get("/jobs")
async def list_all_jobs(limit: int = 50, offset: int = 0):
    db = await get_db()
    try:
        jobs = await list_jobs(db, limit=limit, offset=offset)
    finally:
        await db.close()
    return jobs


@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str):
    db = await get_db()
    try:
        job = await get_job(db, job_id)
        if not job:
            return JSONResponse({"error": "Job not found"}, status_code=404)
        clips = await get_clips_for_job(db, job_id)
    finally:
        await db.close()
    return {"job": job, "clips": clips}


@router.get("/jobs/{job_id}/progress")
async def job_progress_sse(request: Request, job_id: str):
    """SSE endpoint — streams job status updates to the browser."""

    async def event_generator():
        last_status = None
        while True:
            if await request.is_disconnected():
                break

            db = await get_db()
            try:
                job = await get_job(db, job_id)
            finally:
                await db.close()

            if not job:
                yield {"event": "progress", "data": "<p>Job not found.</p>"}
                break

            if job["status"] != last_status:
                last_status = job["status"]
                # Render the progress bar partial
                templates = request.app.state.templates
                html = templates.get_template("_partials/progress_bar.html").render(
                    job=job, request=request
                )
                yield {"event": "progress", "data": html}

            if job["status"] in ("completed", "failed"):
                # Send one final update then close
                break

            await asyncio.sleep(1.5)

    return EventSourceResponse(event_generator())


@router.delete("/jobs/{job_id}")
async def delete_job_route(job_id: str):
    cancel_pipeline(job_id)
    db = await get_db()
    try:
        await delete_job(db, job_id)
    finally:
        await db.close()
    return JSONResponse({"ok": True})
