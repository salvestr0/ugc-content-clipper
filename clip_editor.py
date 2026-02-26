"""Module 5: Auto-Editing — FFmpeg clips, crops to 9:16, adds animated captions."""

import subprocess
import json
import io
from pathlib import Path
from rich.console import Console

import ffmpeg
from PIL import Image

console = Console()


def get_video_dimensions(video_path: str) -> tuple:
    """Get video width and height using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])

    return 1920, 1080  # fallback


def generate_ass_captions(
    words: list,
    clip_start: float,
    clip_end: float,
    config: dict,
) -> str:
    """
    Generate .ass subtitle file with word-by-word highlight animation.

    Groups words into chunks and highlights the active word group,
    similar to the TikTok/CapCut caption style.
    """
    cap_config = config.get("captions", {})
    font = cap_config.get("font", "Arial-Bold")
    font_size = cap_config.get("font_size", 90)
    primary_color = cap_config.get("primary_color", "&H00FFFFFF")
    outline_color = cap_config.get("outline_color", "&H00000000")
    outline_width = cap_config.get("outline_width", 4)
    words_per_group = cap_config.get("words_per_group", 3)
    highlight_color = cap_config.get("highlight_color", "&H0000FFFF")

    # Filter words that fall within the clip range
    clip_words = [
        w for w in words
        if w["start"] >= clip_start and w["end"] <= clip_end
    ]

    if not clip_words:
        return None

    # ASS header
    ass_content = f"""[Script Info]
Title: Viral Clipper Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary_color},&H000000FF,{outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,{outline_width},0,2,40,40,250,1
Style: Highlight,{font},{font_size},{highlight_color},&H000000FF,{outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,{outline_width},0,2,40,40,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Group words into chunks
    groups = []
    for i in range(0, len(clip_words), words_per_group):
        group = clip_words[i:i + words_per_group]
        groups.append(group)

    # Generate dialogue lines with karaoke-style highlighting
    for group in groups:
        group_start = group[0]["start"] - clip_start
        group_end = group[-1]["end"] - clip_start
        group_text = " ".join(w["word"] for w in group).upper()

        # Format timestamps for ASS (H:MM:SS.CC)
        start_ts = _seconds_to_ass_time(group_start)
        end_ts = _seconds_to_ass_time(group_end)

        ass_content += f"Dialogue: 0,{start_ts},{end_ts},Highlight,,0,0,0,,{group_text}\n"

    return ass_content


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.CC)."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_thumbnail(
    video_path: str,
    start_seconds: float,
    output_path: str,
) -> str | None:
    """
    Extract a thumbnail frame using ffmpeg-python and process with Pillow.
    Saves a 270x480 JPEG (9:16) alongside the clip.
    Returns the thumbnail path, or None on failure.
    """
    thumb_path = str(output_path).replace(".mp4", "_thumb.jpg")
    seek_time = start_seconds + 2.0  # skip 2s in for a better frame

    try:
        out, _ = (
            ffmpeg
            .input(video_path, ss=seek_time)
            .output("pipe:", vframes=1, format="image2", vcodec="mjpeg")
            .run(capture_stdout=True, capture_stderr=True)
        )

        img = Image.open(io.BytesIO(out))
        w, h = img.size

        # Crop to 9:16 from centre
        target_aspect = 9 / 16
        if w / h > target_aspect:
            new_w = int(h * target_aspect)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_aspect)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        img = img.resize((270, 480), Image.LANCZOS)
        img.save(thumb_path, "JPEG", quality=85)
        return thumb_path

    except Exception as e:
        console.print(f"[yellow]⚠️  Thumbnail generation failed: {e}[/yellow]")
        return None


def create_clip(
    video_path: str,
    clip_data: dict,
    words: list,
    output_dir: str,
    config: dict,
    clip_index: int = 1,
) -> str:
    """
    Create a single clip from source video using ffmpeg-python.

    - Clips the video segment
    - Crops/pads to 9:16 vertical
    - Burns in animated captions
    - Generates a thumbnail
    - Outputs ready-to-post MP4

    Returns path to the output clip.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start = clip_data["start_seconds"]
    end = clip_data["end_seconds"]
    rank = clip_data.get("rank", clip_index)
    score = clip_data.get("viral_score", 0)

    # Output filename
    safe_hook = "".join(
        c for c in clip_data.get("hook", "clip")[:40] if c.isalnum() or c in " -_"
    ).strip()
    safe_hook = safe_hook.replace(" ", "_") if safe_hook else f"clip_{rank}"
    output_filename = f"{rank:02d}_{score}pts_{safe_hook}.mp4"
    output_path = output_dir / output_filename

    console.print(f"[cyan]✂️  Clipping #{rank}: {start:.1f}s → {end:.1f}s[/cyan]")

    src_width, src_height = get_video_dimensions(video_path)
    target_w, target_h = 1080, 1920
    src_aspect = src_width / src_height
    target_aspect = target_w / target_h  # 0.5625

    # Build input stream with fast seek
    stream = ffmpeg.input(video_path, ss=start, to=end)
    v = stream.video
    a = stream.audio

    # Crop to 9:16
    if src_aspect > target_aspect:
        crop_w = int(src_height * target_aspect)
        crop_x = (src_width - crop_w) // 2
        v = v.filter("crop", crop_w, src_height, crop_x, 0)
    else:
        crop_h = int(src_width / target_aspect)
        crop_y = (src_height - crop_h) // 2
        v = v.filter("crop", src_width, crop_h, 0, crop_y)

    v = v.filter("scale", target_w, target_h)

    # Captions
    ass_path = None
    if config.get("captions", {}).get("enabled", True):
        ass_content = generate_ass_captions(words, start, end, config)
        if ass_content:
            ass_path = output_dir / f"_temp_subs_{rank}.ass"
            ass_path.write_text(ass_content, encoding="utf-8")
            # Escape path for FFmpeg filter syntax (colon is a delimiter)
            escaped = str(ass_path.absolute()).replace("\\", "/").replace(":", "\\:")
            v = v.filter("ass", escaped)

    # Encode
    out_config = config.get("output", {})
    try:
        (
            ffmpeg
            .output(
                v, a, str(output_path),
                vcodec="libx264",
                preset="medium",
                video_bitrate=out_config.get("video_bitrate", "5M"),
                acodec="aac",
                audio_bitrate=out_config.get("audio_bitrate", "192k"),
                r=out_config.get("fps", 30),
                movflags="+faststart",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        console.print(f"[red]❌ FFmpeg error for clip #{rank}:[/red]")
        console.print(f"[red]{e.stderr.decode()[-500:]}[/red]")
        return None
    finally:
        if ass_path and ass_path.exists():
            ass_path.unlink()

    console.print(f"[green]✅ Clip saved:[/green] {output_path}")

    # Generate thumbnail
    generate_thumbnail(video_path, start, str(output_path))

    return str(output_path)


def process_all_clips(
    video_path: str,
    clips: list,
    words: list,
    output_dir: str,
    config: dict,
) -> list:
    """
    Process all detected viral moments into ready-to-post clips.

    Returns list of output file paths.
    """
    console.print(f"\n[bold cyan]🎬 Creating {len(clips)} clips...[/bold cyan]\n")

    output_paths = []
    for i, clip_data in enumerate(clips, 1):
        path = create_clip(
            video_path=video_path,
            clip_data=clip_data,
            words=words,
            output_dir=output_dir,
            config=config,
            clip_index=i,
        )
        if path:
            output_paths.append(path)

    console.print(f"\n[bold green]🎉 Created {len(output_paths)}/{len(clips)} clips successfully![/bold green]")
    console.print(f"[green]📁 Output directory:[/green] {output_dir}")

    return output_paths


if __name__ == "__main__":
    print("This module is used by main.py — run main.py to process videos.")
