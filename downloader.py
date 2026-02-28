"""Module 1: Source Ingestion — Download videos from YouTube via yt-dlp."""

import re
import subprocess
import json
from pathlib import Path
from rich.console import Console

console = Console()

_YOUTUBE_URL_RE = re.compile(
    r'^https://(www\.youtube\.com/|m\.youtube\.com/|youtu\.be/|www\.youtube\.com/@)'
)


def _validate_youtube_url(url: str) -> None:
    """Raise ValueError if url is not a recognisable YouTube URL."""
    if not _YOUTUBE_URL_RE.match(url):
        raise ValueError(f"Invalid YouTube URL: {url!r}")


def get_video_info(url: str) -> dict:
    """Get video metadata without downloading."""
    _validate_youtube_url(url)
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies", str(Path(__file__).parent / "cookies.txt"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get video info: {result.stderr}")
    return json.loads(result.stdout)


def download_video(url: str, output_dir: str = "output/source") -> dict:
    """
    Download a YouTube video.

    Returns dict with:
        - filepath: path to downloaded video
        - title: video title
        - duration: video duration in seconds
        - channel: channel name
    """
    _validate_youtube_url(url)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # First get metadata
    console.print(f"[cyan]📡 Fetching video info...[/cyan]")
    info = get_video_info(url)

    title = info.get("title", "unknown")
    video_id = info.get("id", "unknown")
    duration = info.get("duration", 0)
    channel = info.get("channel", "unknown")

    console.print(f"[green]📹 Title:[/green] {title}")
    console.print(f"[green]⏱️  Duration:[/green] {duration}s ({duration // 60}m {duration % 60}s)")
    console.print(f"[green]📺 Channel:[/green] {channel}")

    # Download with optimal settings for clipping
    output_template = str(output_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        "--write-info-json",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies", str(Path(__file__).parent / "cookies.txt"),
        url,
    ]

    console.print(f"[cyan]⬇️  Downloading...[/cyan]")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Download failed: {result.stderr}")

    # Find the downloaded file
    video_path = output_dir / f"{video_id}.mp4"
    if not video_path.exists():
        # Try to find any file with the video ID
        matches = list(output_dir.glob(f"{video_id}.*"))
        video_files = [m for m in matches if m.suffix in ('.mp4', '.mkv', '.webm')]
        if video_files:
            video_path = video_files[0]
        else:
            raise FileNotFoundError(f"Downloaded file not found for {video_id}")

    console.print(f"[green]✅ Downloaded:[/green] {video_path}")

    return {
        "filepath": str(video_path),
        "title": title,
        "video_id": video_id,
        "duration": duration,
        "channel": channel,
        "url": url,
    }


def get_latest_videos(channel_url: str, count: int = 3) -> list[str]:
    """Get URLs of the latest N videos from a channel."""
    _validate_youtube_url(channel_url)
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(count),
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies", str(Path(__file__).parent / "cookies.txt"),
        f"{channel_url}/videos",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch channel: {result.stderr}")

    videos = []
    for line in result.stdout.strip().split("\n"):
        if line:
            data = json.loads(line)
            videos.append(f"https://www.youtube.com/watch?v={data['id']}")

    return videos


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        result = download_video(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python downloader.py <youtube_url>")
