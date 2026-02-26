"""Background scheduler — auto-checks watchlist channels on a fixed interval."""

import asyncio
import json
from rich.console import Console
from apscheduler.schedulers.asyncio import AsyncIOScheduler

console = Console()
_scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start the APScheduler and register the watchlist check job."""
    _scheduler.add_job(
        _check_all_watchlist,
        trigger="interval",
        hours=6,
        id="watchlist_auto_check",
        replace_existing=True,
        misfire_grace_time=300,  # allow up to 5 min late start
    )
    _scheduler.start()
    console.print("[green]⏰ Scheduler started — watchlist checked every 6 hours[/green]")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


async def _check_all_watchlist():
    """Fetch latest videos from all enabled watchlist channels and queue jobs."""
    from web.database import get_db, list_watchlist, create_job, update_watchlist, now_iso
    from web.jobs import start_pipeline
    from config_loader import load_config

    console.print("[cyan]⏰ Auto-checking watchlist channels...[/cyan]")

    db = await get_db()
    try:
        channels = await list_watchlist(db)
        enabled = [c for c in channels if c["enabled"]]

        if not enabled:
            console.print("[dim]No enabled watchlist channels.[/dim]")
            return

        config = load_config()
        config_json = json.dumps(config)
        total_queued = 0

        for ch in enabled:
            try:
                from downloader import get_latest_videos
                urls = await asyncio.to_thread(
                    get_latest_videos, ch["channel_url"], count=3
                )
                for url in urls:
                    job = await create_job(db, url, config_json=config_json)
                    start_pipeline(job["id"], url, config)
                    total_queued += 1

                await update_watchlist(db, ch["id"], last_checked_at=now_iso())
                console.print(
                    f"[green]  ✓ {ch['channel_name'] or ch['channel_url'][:40]}"
                    f" — queued {len(urls)} jobs[/green]"
                )
            except Exception as e:
                console.print(
                    f"[red]  ✗ {ch['channel_name'] or ch['channel_url'][:40]}: {e}[/red]"
                )
    finally:
        await db.close()

    console.print(f"[green]⏰ Watchlist check complete — {total_queued} jobs queued[/green]")
