# 🎬 Viral Clipper — Automated UGC Clip Detection Pipeline

Automated pipeline that takes long-form YouTube videos, detects viral-worthy moments using AI, and outputs ready-to-post short-form clips with captions.

## Architecture

```
YouTube URL → Download → Transcribe → AI Viral Detection → Auto-Clip → Ready to Post
  (yt-dlp)    (faster-whisper)   (Claude API)         (FFmpeg)
```

## Modules

1. **Source Ingestion** — Downloads videos from YouTube via yt-dlp
2. **Transcription** — Word-level timestamps via faster-whisper
3. **Scene Analysis** — Visual energy detection via PySceneDetect
4. **Viral Moment Detection** — Claude API scores and ranks clip-worthy segments
5. **Auto-Editing** — FFmpeg clips, crops to 9:16, adds animated captions

## Setup

### 1. Install system dependencies
```bash
# FFmpeg (required for video processing)
sudo apt install ffmpeg

# Python 3.10+
python3 --version
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API keys
```bash
cp config/config.example.yaml config/config.yaml
# Edit config.yaml and add your Anthropic API key
```

### 4. Run the pipeline
```bash
# Process a single video
python src/main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Process a channel's latest videos
python src/main.py --channel "CHANNEL_URL" --latest 3

# Process with custom number of clips
python src/main.py --url "VIDEO_URL" --clips 10
```

## Output

Clips are saved to `output/clips/` as ready-to-post 9:16 MP4s with burned-in captions.
Metadata (timestamps, scores, reasons) saved to `output/metadata/`.

## Configuration

Edit `config/config.yaml` to customize:
- Target clip duration (default: 30-60 seconds)
- Caption style (font, color, position)
- Number of clips per video
- Source channels watchlist
- Anthropic API model selection
