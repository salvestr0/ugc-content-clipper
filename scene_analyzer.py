"""Module 3: Scene Analysis — Detect visual energy shifts using PySceneDetect."""

from pathlib import Path
from rich.console import Console

console = Console()


def detect_scenes(video_path: str, threshold: float = 30.0, min_scene_length: float = 1.0) -> list:
    """
    Detect scene changes in a video.
    
    High scene change density = high visual energy (reactions, fast cuts, chaos).
    This data helps Claude identify exciting moments.
    
    Args:
        video_path: Path to video file
        threshold: Detection sensitivity (lower = more sensitive)
        min_scene_length: Minimum seconds between scene changes
    
    Returns list of dicts with:
        - time: timestamp in seconds
        - frame: frame number
    """
    from scenedetect import detect, ContentDetector, AdaptiveDetector

    console.print(f"[cyan]🎬 Analyzing scenes...[/cyan]")

    scene_list = detect(
        video_path,
        ContentDetector(threshold=threshold, min_scene_len=int(min_scene_length * 30)),
    )

    scenes = []
    for i, scene in enumerate(scene_list):
        start_time = scene[0].get_seconds()
        end_time = scene[1].get_seconds()
        scenes.append({
            "scene_num": i + 1,
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(end_time - start_time, 2),
        })

    console.print(f"[green]✅ Detected {len(scenes)} scenes[/green]")

    return scenes


def compute_energy_map(scenes: list, video_duration: float, window_size: float = 30.0) -> list:
    """
    Compute a 'visual energy' score across the video timeline.
    
    Breaks the video into windows and counts scene changes per window.
    More scene changes = more visual energy = more likely to be exciting.
    
    Args:
        scenes: Output from detect_scenes
        video_duration: Total video duration in seconds  
        window_size: Size of analysis window in seconds
    
    Returns list of dicts with:
        - start: window start time
        - end: window end time
        - scene_count: number of scene changes in this window
        - energy_score: normalized energy score (0-1)
    """
    if not scenes:
        return []

    windows = []
    max_count = 0

    t = 0
    while t < video_duration:
        window_end = min(t + window_size, video_duration)
        
        # Count scene changes that start within this window
        count = sum(
            1 for s in scenes
            if s["start"] >= t and s["start"] < window_end
        )
        max_count = max(max_count, count)
        
        windows.append({
            "start": round(t, 2),
            "end": round(window_end, 2),
            "scene_count": count,
        })
        t += window_size

    # Normalize energy scores
    if max_count > 0:
        for w in windows:
            w["energy_score"] = round(w["scene_count"] / max_count, 2)
    else:
        for w in windows:
            w["energy_score"] = 0

    # Log the high-energy windows
    high_energy = [w for w in windows if w["energy_score"] >= 0.6]
    if high_energy:
        console.print(f"[yellow]⚡ High-energy segments:[/yellow]")
        for w in high_energy:
            console.print(
                f"  [{w['start']:.0f}s - {w['end']:.0f}s] "
                f"energy: {w['energy_score']:.0%} ({w['scene_count']} scene changes)"
            )

    return windows


def analyze_audio_energy(
    video_path: str,
    video_duration: float,
    window_size: float = 30.0,
) -> list:
    """
    Analyze audio loudness across the video timeline using librosa.

    Returns windows in the same format as compute_energy_map so they
    can be merged with the visual energy map before sending to Claude.
    """
    import librosa
    import numpy as np

    console.print(f"[cyan]🔊 Analyzing audio energy...[/cyan]")

    try:
        # Load mono audio — librosa uses ffmpeg to decode video files
        y, sr = librosa.load(video_path, sr=None, mono=True)

        # RMS energy per frame
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        times = librosa.frames_to_time(
            range(len(rms)), sr=sr, hop_length=hop_length
        )

        windows = []
        max_rms = 0.0
        t = 0.0
        while t < video_duration:
            window_end = min(t + window_size, video_duration)
            mask = (times >= t) & (times < window_end)
            avg_rms = float(np.mean(rms[mask])) if mask.any() else 0.0
            max_rms = max(max_rms, avg_rms)
            windows.append({"start": round(t, 2), "end": round(window_end, 2), "rms": avg_rms})
            t += window_size

        if max_rms > 0:
            for w in windows:
                w["energy_score"] = round(w["rms"] / max_rms, 2)
        else:
            for w in windows:
                w["energy_score"] = 0.0

        console.print(f"[green]✅ Audio energy analyzed ({len(windows)} windows)[/green]")
        return windows

    except Exception as e:
        console.print(f"[yellow]⚠️  Audio energy analysis skipped: {e}[/yellow]")
        return []


def merge_energy_maps(visual: list, audio: list) -> list:
    """
    Merge visual (scene change) and audio (RMS) energy maps.
    Takes the max of the two scores per window so either signal can surface a moment.
    """
    if not audio:
        return visual

    audio_by_start = {w["start"]: w["energy_score"] for w in audio}
    merged = []
    for w in visual:
        audio_score = audio_by_start.get(w["start"], 0.0)
        merged.append({
            **w,
            "visual_energy": w["energy_score"],
            "audio_energy": round(audio_score, 2),
            "energy_score": round(max(w["energy_score"], audio_score), 2),
        })
    return merged


def format_energy_for_ai(energy_map: list) -> str:
    """Format energy map data for Claude API prompt."""
    has_audio = any("audio_energy" in w for w in energy_map)

    if has_audio:
        lines = ["Combined Visual + Audio Energy Map (per 30s window):"]
        for w in energy_map:
            bar = "█" * int(w["energy_score"] * 10)
            lines.append(
                f"  [{w['start']:.0f}s-{w['end']:.0f}s] {bar} {w['energy_score']:.0%}"
                f" (visual:{w['visual_energy']:.0%} audio:{w['audio_energy']:.0%})"
            )
    else:
        lines = ["Visual Energy Map (scene change density per 30s window):"]
        for w in energy_map:
            bar = "█" * int(w["energy_score"] * 10)
            lines.append(
                f"  [{w['start']:.0f}s-{w['end']:.0f}s] {bar} {w['energy_score']:.0%}"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scenes = detect_scenes(sys.argv[1])
        # Estimate duration from last scene
        if scenes:
            est_duration = scenes[-1]["end"]
            energy = compute_energy_map(scenes, est_duration)
            print(format_energy_for_ai(energy))
    else:
        print("Usage: python scene_analyzer.py <video_path>")
