"""
Viral Clipper — Main Pipeline Orchestrator

Takes a YouTube URL, downloads it, transcribes it, detects viral moments
using Claude AI, and outputs ready-to-post short-form clips.

Usage:
    python src/main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
    python src/main.py --url "VIDEO_URL" --clips 10
    python src/main.py --channel "CHANNEL_URL" --latest 3
"""

import click
import json
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config_loader import load_config
from downloader import download_video, get_latest_videos
from transcriber import transcribe_video, create_transcript_for_ai, save_transcript
from scene_analyzer import detect_scenes, compute_energy_map, format_energy_for_ai
from viral_detector import detect_viral_moments, save_clip_metadata
from clip_editor import process_all_clips

console = Console()


def process_video(url: str, config: dict, output_base: str = "output") -> dict:
    """
    Full pipeline for a single video.
    
    Returns dict with results and paths.
    """
    output_base = Path(output_base)
    start_time = time.time()

    # ── Step 1: Download ──
    console.print(Panel("📡 Step 1/5: Downloading Video", style="bold cyan"))
    video_info = download_video(url, output_dir=str(output_base / "source"))
    video_path = video_info["filepath"]
    video_id = video_info["video_id"]

    # ── Step 2: Transcribe ──
    console.print(Panel("🎙️ Step 2/5: Transcribing Audio", style="bold cyan"))
    transcript = transcribe_video(
        video_path,
        model_size="base",  # Change to "small" or "medium" for better accuracy
    )
    
    # Save transcript for reference
    save_transcript(
        transcript,
        str(output_base / "metadata" / f"{video_id}_transcript.json"),
    )

    # ── Step 3: Scene Analysis ──
    console.print(Panel("🎬 Step 3/5: Analyzing Visual Energy", style="bold cyan"))
    scene_config = config.get("scene_detection", {})
    scenes = detect_scenes(
        video_path,
        threshold=scene_config.get("threshold", 30.0),
        min_scene_length=scene_config.get("min_scene_length", 1.0),
    )
    energy_map = compute_energy_map(
        scenes,
        video_duration=video_info["duration"],
    )

    # ── Step 4: AI Viral Detection ──
    console.print(Panel("🧠 Step 4/5: AI Viral Moment Detection", style="bold cyan"))
    
    # Format data for Claude
    transcript_formatted = create_transcript_for_ai(transcript["segments"])
    energy_formatted = format_energy_for_ai(energy_map)

    clips = detect_viral_moments(
        transcript_formatted=transcript_formatted,
        energy_map_formatted=energy_formatted,
        video_metadata=video_info,
        config=config,
    )

    # Save clip metadata
    save_clip_metadata(
        clips,
        video_info,
        str(output_base / "metadata" / f"{video_id}_clips.json"),
    )

    # ── Step 5: Create Clips ──
    console.print(Panel("✂️ Step 5/5: Creating Clips", style="bold cyan"))
    clip_dir = str(output_base / "clips" / video_id)
    output_paths = process_all_clips(
        video_path=video_path,
        clips=clips,
        words=transcript["words"],
        output_dir=clip_dir,
        config=config,
    )

    # ── Summary ──
    elapsed = time.time() - start_time
    
    console.print()
    table = Table(title="📊 Pipeline Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Video", video_info["title"][:50])
    table.add_row("Channel", video_info["channel"])
    table.add_row("Duration", f"{video_info['duration'] // 60}m {video_info['duration'] % 60}s")
    table.add_row("Transcript Words", str(len(transcript["words"])))
    table.add_row("Scenes Detected", str(len(scenes)))
    table.add_row("Clips Created", f"{len(output_paths)}/{len(clips)}")
    table.add_row("Output Dir", clip_dir)
    table.add_row("Total Time", f"{elapsed:.1f}s")
    
    console.print(table)

    # Print posting checklist
    if output_paths:
        console.print("\n[bold yellow]📋 Posting Checklist:[/bold yellow]")
        for i, path in enumerate(output_paths, 1):
            clip = clips[i - 1] if i <= len(clips) else {}
            console.print(f"  {i}. [bold]{Path(path).name}[/bold]")
            console.print(f"     Hook: {clip.get('suggested_caption', 'N/A')}")
            console.print(f"     Score: {clip.get('viral_score', '?')}/100")
            console.print()

    return {
        "video_info": video_info,
        "clips": clips,
        "output_paths": output_paths,
        "elapsed": elapsed,
    }


@click.command()
@click.option("--url", help="Video URL to process (YouTube, Twitch VOD, or Kick.com VOD)")
@click.option("--channel", help="Channel URL to fetch latest past broadcasts from (YouTube, Twitch, or Kick.com)")
@click.option("--latest", default=1, help="Number of latest videos to process from channel")
@click.option("--clips", default=None, type=int, help="Override number of clips per video")
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
@click.option("--output", default="output", help="Output directory")
def main(url, channel, latest, clips, config_path, output):
    """🎬 Viral Clipper — Automated Short-Form Content Pipeline"""
    
    console.print(Panel(
        "[bold]🎬 Viral Clipper[/bold]\n"
        "Automated UGC Clip Detection Pipeline",
        style="bold magenta",
    ))

    # Load config
    config = load_config(config_path)
    
    # Override clips count if specified
    if clips:
        config["clips"]["clips_per_video"] = clips

    # Determine URLs to process
    urls = []
    if url:
        urls = [url]
    elif channel:
        console.print(f"[cyan]📺 Fetching latest {latest} videos from channel...[/cyan]")
        urls = get_latest_videos(channel, count=latest)
        console.print(f"[green]Found {len(urls)} videos[/green]")
    else:
        console.print("[red]❌ Please provide --url or --channel[/red]")
        return

    # Process each video
    all_results = []
    for i, video_url in enumerate(urls, 1):
        if len(urls) > 1:
            console.print(f"\n[bold]━━━ Video {i}/{len(urls)} ━━━[/bold]\n")
        
        try:
            result = process_video(video_url, config, output)
            all_results.append(result)
        except Exception as e:
            console.print(f"[red]❌ Error processing {video_url}: {e}[/red]")
            import traceback
            traceback.print_exc()

    # Final summary
    if len(all_results) > 1:
        total_clips = sum(len(r["output_paths"]) for r in all_results)
        total_time = sum(r["elapsed"] for r in all_results)
        console.print(f"\n[bold green]🎉 Done! Created {total_clips} clips in {total_time:.1f}s[/bold green]")


if __name__ == "__main__":
    main()
