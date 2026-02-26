"""HTML page routes — serve Jinja2 templates."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.database import get_db, get_job, list_jobs, get_clips_for_job, get_clip, list_watchlist

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = await get_db()
    try:
        jobs = await list_jobs(db)
    finally:
        await db.close()
    return _templates(request).TemplateResponse("index.html", {"request": request, "jobs": jobs})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    db = await get_db()
    try:
        job = await get_job(db, job_id)
        if not job:
            return RedirectResponse("/")
        clips = await get_clips_for_job(db, job_id)
    finally:
        await db.close()
    return _templates(request).TemplateResponse(
        "job_detail.html", {"request": request, "job": job, "clips": clips}
    )


@router.get("/jobs/{job_id}/clips", response_class=HTMLResponse)
async def clips_page(request: Request, job_id: str):
    db = await get_db()
    try:
        job = await get_job(db, job_id)
        if not job:
            return RedirectResponse("/")
        clips = await get_clips_for_job(db, job_id)
    finally:
        await db.close()
    return _templates(request).TemplateResponse(
        "clips.html", {"request": request, "job": job, "clips": clips}
    )


@router.get("/clips/{clip_id}/edit", response_class=HTMLResponse)
async def clip_edit(request: Request, clip_id: str):
    db = await get_db()
    try:
        clip = await get_clip(db, clip_id)
        if not clip:
            return RedirectResponse("/")
        job = await get_job(db, clip["job_id"])
    finally:
        await db.close()
    return _templates(request).TemplateResponse(
        "clip_edit.html", {"request": request, "clip": clip, "job": job}
    )


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    from config_loader import load_config

    class DotDict(dict):
        """Allow dot-access in Jinja templates."""
        __getattr__ = dict.__getitem__

    def to_dot(d):
        if isinstance(d, dict):
            return DotDict({k: to_dot(v) for k, v in d.items()})
        return d

    config = to_dot(load_config())
    return _templates(request).TemplateResponse(
        "config.html", {"request": request, "config": config}
    )


@router.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    db = await get_db()
    try:
        channels = await list_watchlist(db)
    finally:
        await db.close()
    return _templates(request).TemplateResponse(
        "watchlist.html", {"request": request, "channels": channels}
    )
