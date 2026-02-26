"""Module 4: Viral Moment Detection — Claude API scores and ranks clip-worthy segments."""

import json
import re
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

console = Console()

# System prompt that encodes the "doomscroller instinct" into AI instructions
VIRAL_DETECTOR_PROMPT = """You are an expert short-form content analyst specializing in TikTok, Instagram Reels, and YouTube Shorts. You've studied thousands of viral clips and understand exactly what makes someone stop scrolling.

You will receive:
1. A transcript of a long-form video with timestamps
2. A visual energy map showing scene change density
3. Metadata about the source video

Your job: identify the TOP clip-worthy moments that would perform best as standalone short-form clips (15-60 seconds).

## WHAT MAKES A CLIP GO VIRAL

### The Hook (First 1-3 seconds of the clip)
- Starts MID-SENTENCE on a bold, controversial, or shocking statement
- Opens with extreme emotion (anger, shock, hype, disbelief)
- Begins with a question that creates instant curiosity
- DO NOT start clips at the natural beginning of a topic — start at the PEAK

### The Content (Middle)
- Has a clear emotional arc (buildup → peak → reaction)
- Contains quotable one-liners people would comment or share
- Features conflict, debate, hot takes, or unexpected revelations
- Shows genuine reactions (laughter, shock, anger) — not scripted moments
- Has fast pacing with no dead air or filler

### The Ending
- Ends on a cliffhanger, punchline, or mic-drop moment
- OR ends right after a peak reaction (cut while energy is HIGH)
- NEVER let the clip trail off into boring territory

### Visual Energy Correlation
- High scene change density often correlates with exciting moments
- But a single person delivering a powerful monologue with LOW scene changes can also be viral
- Use visual energy as a SIGNAL, not the only factor

## RED FLAGS — SKIP THESE MOMENTS
- Long explanations or tutorials (boring for short-form)
- Inside jokes that only make sense with full context
- Sponsor segments or self-promotion
- Moments that need setup — if you need to explain "what happened before", it's not a good clip
- Dead air, "umm", filler, or low-energy conversation

## OUTPUT FORMAT

Return a JSON array of clip candidates, ranked by viral potential (best first):

```json
[
  {
    "rank": 1,
    "start_time": "MM:SS",
    "end_time": "MM:SS", 
    "start_seconds": 125.5,
    "end_seconds": 163.2,
    "duration": 37.7,
    "hook": "The exact opening line/moment that would make someone stop scrolling",
    "viral_score": 92,
    "why_viral": "Short explanation of why this would go viral",
    "emotional_trigger": "shock|humor|controversy|hype|motivation|cringe|wholesome",
    "suggested_caption": "Text overlay for the first 3 seconds to maximize hook",
    "clip_text": "The key transcript excerpt for this segment"
  }
]
```

IMPORTANT RULES:
- Return exactly {num_clips} clips
- viral_score is 0-100 (be harsh — only truly viral moments get 80+)
- Clips MUST be between {min_duration} and {max_duration} seconds
- Clips should NOT overlap
- start_time should begin 1-2 seconds BEFORE the hook moment (for visual context)
- Prefer clips that work WITHOUT knowing who the speaker is
- The "hook" field should be the EXACT words from the transcript that open the clip
"""


def detect_viral_moments(
    transcript_formatted: str,
    energy_map_formatted: str,
    video_metadata: dict,
    config: dict,
) -> list:
    """
    Send transcript + energy data to Claude API and get ranked viral moments.
    
    Args:
        transcript_formatted: Timestamped transcript from transcriber
        energy_map_formatted: Energy map from scene_analyzer
        video_metadata: Dict with title, channel, duration, url
        config: App configuration
    
    Returns list of clip candidates ranked by viral potential.
    """
    import anthropic

    api_key = config["anthropic"]["api_key"]
    model = config["anthropic"]["model"]
    clips_config = config["clips"]

    if not api_key or api_key == "YOUR_ANTHROPIC_API_KEY_HERE":
        raise ValueError(
            "Anthropic API key not configured. "
            "Edit config/config.yaml and add your API key."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Build the system prompt with config values
    # Note: can't use .format() here — the prompt contains JSON curly braces that
    # Python would try to interpret as format placeholders
    system = (
        VIRAL_DETECTOR_PROMPT
        .replace("{num_clips}", str(clips_config["clips_per_video"]))
        .replace("{min_duration}", str(clips_config["min_duration"]))
        .replace("{max_duration}", str(clips_config["max_duration"]))
    )

    # Build the user message with all context
    user_message = f"""## VIDEO METADATA
- Title: {video_metadata.get('title', 'Unknown')}
- Channel: {video_metadata.get('channel', 'Unknown')}
- Duration: {video_metadata.get('duration', 0)} seconds
- URL: {video_metadata.get('url', 'N/A')}

## VISUAL ENERGY MAP
{energy_map_formatted}

## FULL TRANSCRIPT WITH TIMESTAMPS
{transcript_formatted}

---

Analyze this video and return the top {clips_config['clips_per_video']} viral clip candidates as a JSON array. Be ruthless — only pick moments that would genuinely make someone stop scrolling."""

    console.print(f"[cyan]🧠 Sending to Claude ({model}) for viral moment detection...[/cyan]")
    console.print(f"[dim]   Transcript length: {len(transcript_formatted)} chars[/dim]")

    def _is_retryable(exc) -> bool:
        import anthropic as _anthropic
        if isinstance(exc, _anthropic.RateLimitError):
            return True
        if isinstance(exc, _anthropic.APIStatusError) and exc.status_code >= 500:
            return True
        return False

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )
    def _call_api():
        return client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

    response = _call_api()

    # Parse the response
    response_text = response.content[0].text

    # Extract JSON from response — try code block first, then regex fallback
    json_str = response_text
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
    else:
        # No code block — find the JSON array directly
        match = re.search(r'\[[\s\S]*\]', json_str)
        if match:
            json_str = match.group(0)

    try:
        clips = json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse Claude response as JSON: {e}\n"
            f"Raw response (first 500 chars):\n{response_text[:500]}"
        )

    if not isinstance(clips, list):
        raise ValueError(
            f"Expected a JSON array from Claude, got {type(clips).__name__}. "
            f"Raw response (first 500 chars):\n{response_text[:500]}"
        )

    # Validate and log results
    console.print(f"\n[green]🎯 Found {len(clips)} viral candidates:[/green]\n")
    for clip in clips:
        score = clip.get("viral_score", 0)
        emoji = "🔥" if score >= 80 else "⚡" if score >= 60 else "💡"
        console.print(
            f"  {emoji} #{clip['rank']} [bold]{clip['hook'][:60]}...[/bold]"
        )
        console.print(
            f"     Score: {score}/100 | "
            f"{clip['start_time']} → {clip['end_time']} "
            f"({clip['duration']:.0f}s) | "
            f"Trigger: {clip['emotional_trigger']}"
        )
        console.print(f"     Why: {clip['why_viral']}")
        console.print()

    return clips


def save_clip_metadata(clips: list, video_metadata: dict, output_path: str):
    """Save clip detection results to JSON."""
    from pathlib import Path
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "video": video_metadata,
        "clips": clips,
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    console.print(f"[green]💾 Clip metadata saved:[/green] {output_path}")
