"""
Quick test script — validate each module independently.

Usage:
    python src/test_pipeline.py download "YOUTUBE_URL"
    python src/test_pipeline.py transcribe "path/to/video.mp4"
    python src/test_pipeline.py scenes "path/to/video.mp4"
    python src/test_pipeline.py detect "path/to/transcript.json"
    python src/test_pipeline.py full "YOUTUBE_URL"
"""

import sys
import json
from rich.console import Console

console = Console()


def test_download(url: str):
    """Test Module 1: Download only."""
    from downloader import download_video
    result = download_video(url)
    console.print(f"\n[green]✅ Download test passed![/green]")
    console.print(json.dumps(result, indent=2))
    return result


def test_transcribe(video_path: str):
    """Test Module 2: Transcription only."""
    from transcriber import transcribe_video, create_transcript_for_ai
    
    result = transcribe_video(video_path, model_size="base")
    
    # Show formatted transcript preview
    formatted = create_transcript_for_ai(result["segments"])
    console.print(f"\n[green]✅ Transcription test passed![/green]")
    console.print(f"Segments: {len(result['segments'])}")
    console.print(f"Words: {len(result['words'])}")
    console.print(f"\nPreview (first 500 chars):\n{formatted[:500]}...")
    
    # Save for later use
    with open("output/metadata/test_transcript.json", "w") as f:
        json.dump(result, f, indent=2)
    console.print(f"\nSaved to output/metadata/test_transcript.json")
    
    return result


def test_scenes(video_path: str):
    """Test Module 3: Scene detection only."""
    from scene_analyzer import detect_scenes, compute_energy_map, format_energy_for_ai
    
    scenes = detect_scenes(video_path)
    
    if scenes:
        est_duration = scenes[-1]["end"]
        energy_map = compute_energy_map(scenes, est_duration)
        formatted = format_energy_for_ai(energy_map)
        console.print(f"\n{formatted}")
    
    console.print(f"\n[green]✅ Scene detection test passed![/green]")
    return scenes


def test_detect(transcript_path: str):
    """Test Module 4: Viral detection using saved transcript."""
    from config_loader import load_config
    from transcriber import create_transcript_for_ai
    from viral_detector import detect_viral_moments
    
    config = load_config()
    
    with open(transcript_path) as f:
        transcript = json.load(f)
    
    formatted = create_transcript_for_ai(transcript["segments"])
    
    # Minimal energy map for testing
    energy_formatted = "Visual Energy Map: (no scene data — testing transcript only)"
    
    clips = detect_viral_moments(
        transcript_formatted=formatted,
        energy_map_formatted=energy_formatted,
        video_metadata={"title": "Test", "channel": "Test", "duration": 0},
        config=config,
    )
    
    console.print(f"\n[green]✅ Viral detection test passed![/green]")
    console.print(json.dumps(clips, indent=2))
    return clips


if __name__ == "__main__":
    if len(sys.argv) < 3:
        console.print("[yellow]Usage:[/yellow]")
        console.print("  python src/test_pipeline.py download <youtube_url>")
        console.print("  python src/test_pipeline.py transcribe <video_path>")
        console.print("  python src/test_pipeline.py scenes <video_path>")
        console.print("  python src/test_pipeline.py detect <transcript.json>")
        sys.exit(1)

    command = sys.argv[1]
    arg = sys.argv[2]

    from pathlib import Path
    Path("output/metadata").mkdir(parents=True, exist_ok=True)
    Path("output/source").mkdir(parents=True, exist_ok=True)

    if command == "download":
        test_download(arg)
    elif command == "transcribe":
        test_transcribe(arg)
    elif command == "scenes":
        test_scenes(arg)
    elif command == "detect":
        test_detect(arg)
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
