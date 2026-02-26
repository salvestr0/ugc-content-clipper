"""Pipeline runner — wraps existing modules with asyncio.to_thread for web use."""

import asyncio
import json
import re
import traceback
from pathlib import Path
from rich.console import Console

from web.database import get_db, update_job, create_clip

console = Console()

# Concurrency limit: max 2 simultaneous pipeline runs
_semaphore = asyncio.Semaphore(2)

# Track running tasks so we can cancel them
_running_tasks: dict[str, asyncio.Task] = {}


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL without making any network calls."""
    patterns = [
        r'[?&]v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _find_cached_video(source_dir: Path, video_id: str) -> Path | None:
    """Return path to an already-downloaded video file, or None."""
    for ext in ('.mp4', '.mkv', '.webm'):
        p = source_dir / f"{video_id}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _load_video_info_from_cache(video_path: Path, video_id: str, url: str, source_dir: Path) -> dict:
    """Load video metadata from yt-dlp's saved .info.json, with fallback."""
    info_json = source_dir / f"{video_id}.info.json"
    if info_json.exists():
        with open(info_json) as f:
            raw = json.load(f)
        return {
            "filepath": str(video_path),
            "title": raw.get("title", video_id),
            "video_id": video_id,
            "duration": raw.get("duration", 0),
            "channel": raw.get("channel", raw.get("uploader", "Unknown")),
            "url": url,
        }
    return {
        "filepath": str(video_path),
        "title": video_id,
        "video_id": video_id,
        "duration": 0,
        "channel": "Unknown",
        "url": url,
    }


async def run_pipeline(job_id: str, url: str, config: dict):
    """Run the full pipeline for a single video in a background task."""
    async with _semaphore:
        db = await get_db()
        try:
            await _run_stages(db, job_id, url, config)
        except asyncio.CancelledError:
            await update_job(db, job_id, status="failed", error="Cancelled by user")
        except Exception as e:
            tb = traceback.format_exc()
            console.print(f"[red]Pipeline error:[/red]\n{tb}")
            await update_job(db, job_id, status="failed", error=str(e)[:500])
        finally:
            _running_tasks.pop(job_id, None)
            await db.close()


async def _run_stages(db, job_id: str, url: str, config: dict):
    output_base = Path("output")
    source_dir = output_base / "source"
    metadata_dir = output_base / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Extract video_id from URL early so we can check caches before Stage 1
    video_id = _extract_video_id(url)

    # ── Stage 1: Download ──
    await update_job(db, job_id, status="downloading", stage=1)
    from downloader import download_video

    cached_video = _find_cached_video(source_dir, video_id) if video_id else None
    if cached_video:
        console.print(f"[yellow]⚡ Cached video found, skipping download:[/yellow] {cached_video}")
        video_info = _load_video_info_from_cache(cached_video, video_id, url, source_dir)
    else:
        video_info = await asyncio.to_thread(
            download_video, url, str(source_dir)
        )

    video_path = video_info["filepath"]
    video_id = video_info["video_id"]

    await update_job(
        db, job_id,
        video_id=video_id,
        video_title=video_info["title"],
        channel=video_info["channel"],
        duration_seconds=video_info["duration"],
        output_dir=str(output_base / "clips" / video_id),
    )

    # ── Stage 2: Transcribe ──
    await update_job(db, job_id, status="transcribing", stage=2)
    from transcriber import transcribe_video, create_transcript_for_ai, save_transcript

    transcript_path = metadata_dir / f"{video_id}_transcript.json"
    if transcript_path.exists():
        console.print(f"[yellow]⚡ Cached transcript found, skipping transcription:[/yellow] {transcript_path}")
        with open(transcript_path) as f:
            transcript = json.load(f)
    else:
        transcript = await asyncio.to_thread(transcribe_video, video_path, model_size="base")
        await asyncio.to_thread(
            save_transcript, transcript, str(transcript_path)
        )

    # ── Stage 3: Scene Analysis ──
    await update_job(db, job_id, status="analyzing_scenes", stage=3)
    from scene_analyzer import (
        detect_scenes, compute_energy_map, format_energy_for_ai,
        analyze_audio_energy, merge_energy_maps,
    )

    scenes_path = metadata_dir / f"{video_id}_scenes.json"
    audio_energy_path = metadata_dir / f"{video_id}_audio_energy.json"
    scene_config = config.get("scene_detection", {})

    if scenes_path.exists():
        console.print(f"[yellow]⚡ Cached scenes found, skipping scene detection:[/yellow] {scenes_path}")
        with open(scenes_path) as f:
            scenes = json.load(f)
    else:
        scenes = await asyncio.to_thread(
            detect_scenes, video_path,
            threshold=scene_config.get("threshold", 30.0),
            min_scene_length=scene_config.get("min_scene_length", 1.0),
        )
        with open(scenes_path, "w") as f:
            json.dump(scenes, f)

    if audio_energy_path.exists():
        console.print(f"[yellow]⚡ Cached audio energy found:[/yellow] {audio_energy_path}")
        with open(audio_energy_path) as f:
            audio_energy = json.load(f)
    else:
        audio_energy = await asyncio.to_thread(
            analyze_audio_energy, video_path, video_info["duration"]
        )
        if audio_energy:
            with open(audio_energy_path, "w") as f:
                json.dump(audio_energy, f)

    visual_energy = compute_energy_map(scenes, video_duration=video_info["duration"])
    energy_map = merge_energy_maps(visual_energy, audio_energy)

    # ── Stage 4: AI Viral Detection ──
    await update_job(db, job_id, status="detecting_viral", stage=4)
    from viral_detector import detect_viral_moments, save_clip_metadata

    transcript_formatted = create_transcript_for_ai(transcript["segments"])
    energy_formatted = format_energy_for_ai(energy_map)

    clips_path = metadata_dir / f"{video_id}_clips.json"
    if clips_path.exists():
        console.print(f"[yellow]⚡ Cached clips found, skipping viral detection:[/yellow] {clips_path}")
        with open(clips_path) as f:
            clips = json.load(f)["clips"]
    else:
        clips = await asyncio.to_thread(
            detect_viral_moments,
            transcript_formatted=transcript_formatted,
            energy_map_formatted=energy_formatted,
            video_metadata=video_info,
            config=config,
        )
        await asyncio.to_thread(
            save_clip_metadata, clips, video_info,
            str(clips_path),
        )

    # ── Stage 5: Create Clips ──
    await update_job(db, job_id, status="editing_clips", stage=5)
    from clip_editor import process_all_clips

    clip_dir = str(output_base / "clips" / video_id)
    output_paths = await asyncio.to_thread(
        process_all_clips,
        video_path=video_path,
        clips=clips,
        words=transcript["words"],
        output_dir=clip_dir,
        config=config,
    )

    # ── Store clips in DB ──
    for i, clip_data in enumerate(clips):
        clip_data["output_path"] = output_paths[i] if i < len(output_paths) else None
        await create_clip(db, job_id, clip_data)

    # ── Done ──
    await update_job(db, job_id, status="completed", stage=6)


def start_pipeline(job_id: str, url: str, config: dict):
    """Schedule the pipeline as an asyncio background task."""
    task = asyncio.create_task(run_pipeline(job_id, url, config))
    _running_tasks[job_id] = task
    return task


def cancel_pipeline(job_id: str):
    """Cancel a running pipeline task."""
    task = _running_tasks.get(job_id)
    if task and not task.done():
        task.cancel()
