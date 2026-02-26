"""Module 2: Transcription — Word-level timestamps via faster-whisper."""

import json
from pathlib import Path
from rich.console import Console
from rich.progress import Progress

console = Console()


def transcribe_video(
    video_path: str,
    model_size: str = "base",
    language: str = "en",
) -> dict:
    """
    Transcribe video with word-level timestamps.
    
    Args:
        video_path: Path to video/audio file
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
                    - tiny/base: fast, good for English content
                    - small: good balance
                    - medium/large-v3: best accuracy, slower
        language: Language code
    
    Returns dict with:
        - segments: list of segments with start, end, text
        - words: list of words with start, end, word, probability
        - full_text: complete transcript
    """
    from faster_whisper import WhisperModel

    console.print(f"[cyan]🎙️  Loading Whisper model ({model_size})...[/cyan]")
    
    # Use CPU — switch to "cuda" if you have a GPU
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    console.print(f"[cyan]📝 Transcribing...[/cyan]")
    
    segments_raw, info = model.transcribe(
        video_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,  # Voice activity detection to skip silence
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    console.print(f"[green]🌐 Detected language:[/green] {info.language} (probability: {info.language_probability:.2f})")

    segments = []
    words = []
    full_text_parts = []

    for segment in segments_raw:
        seg_data = {
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
        }
        segments.append(seg_data)
        full_text_parts.append(segment.text.strip())

        if segment.words:
            for word in segment.words:
                words.append({
                    "start": round(word.start, 2),
                    "end": round(word.end, 2),
                    "word": word.word.strip(),
                    "probability": round(word.probability, 3),
                })

    full_text = " ".join(full_text_parts)

    console.print(f"[green]✅ Transcribed:[/green] {len(segments)} segments, {len(words)} words")
    console.print(f"[green]⏱️  Audio duration:[/green] {info.duration:.1f}s")

    return {
        "segments": segments,
        "words": words,
        "full_text": full_text,
        "duration": info.duration,
        "language": info.language,
    }


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.ms format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 100)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:02d}"


def create_transcript_for_ai(segments: list, include_timestamps: bool = True) -> str:
    """
    Format transcript for sending to Claude API.
    Includes timestamps so Claude can reference specific moments.
    """
    lines = []
    for seg in segments:
        if include_timestamps:
            ts = format_timestamp(seg["start"])
            lines.append(f"[{ts}] {seg['text']}")
        else:
            lines.append(seg["text"])
    return "\n".join(lines)


def save_transcript(transcript_data: dict, output_path: str):
    """Save transcript data to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, indent=2)
    console.print(f"[green]💾 Transcript saved:[/green] {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = transcribe_video(sys.argv[1])
        print(f"\nFull text preview:\n{result['full_text'][:500]}...")
    else:
        print("Usage: python transcriber.py <video_path>")
