# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Viral Clipper — an automated pipeline that takes long-form YouTube videos, detects viral-worthy moments using Claude API, and outputs ready-to-post 9:16 short-form clips with animated captions.

## Pipeline Architecture

```
YouTube URL → Download (yt-dlp) → Transcribe (faster-whisper) → Scene Analysis (PySceneDetect)
  → Viral Detection (Claude API) → Auto-Edit & Caption (FFmpeg) → Output MP4s
```

Each stage is a standalone module in the project root:
- `downloader.py` → `transcriber.py` → `scene_analyzer.py` → `viral_detector.py` → `clip_editor.py`
- `main.py` orchestrates the full pipeline
- `config_loader.py` manages YAML config with hardcoded defaults (DefaultConfig dict)

Data flows as dicts/JSON between stages. Transcripts and clip metadata are serialized to JSON in `output/metadata/`. Final clips go to `output/clips/`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
python main.py --channel "CHANNEL_URL" --latest 3
python main.py --url "VIDEO_URL" --clips 10

# Test individual modules
python test_pipeline.py download "YOUTUBE_URL"
python test_pipeline.py transcribe "path/to/video.mp4"
python test_pipeline.py scenes "path/to/video.mp4"
python test_pipeline.py detect "path/to/transcript.json"
```

System requirements: Python 3.10+, FFmpeg, yt-dlp.

## Configuration

Config lives at `config/config.yaml` (copy from `config/config.example.yaml`). Key settings: Anthropic API key/model, clip duration bounds (15-60s, target 35s), output resolution (1080x1920), caption styling, scene detection threshold.

## Model Selection (Token Cost Optimization)

Route tasks to the cheapest model that can handle them. Use the `model` parameter on Task tool calls and switch models between tasks accordingly.

**Haiku** — lightweight, low-cost tasks:
- Cron jobs, scheduled/repetitive automation
- File listing, glob/grep searches, simple lookups
- Summarizing short text, formatting output
- Git status checks, simple bash commands
- Reading and relaying file contents without analysis

**Sonnet** — mid-tier, everyday tasks:
- Casual conversation, Q&A, explanations
- Writing or editing config files, YAML, markdown
- Small single-file edits with clear instructions
- Code review of straightforward changes
- Running and interpreting test output

**Opus** — heavy lifting, high-complexity tasks:
- Writing new modules or significant code changes
- Multi-file refactors and architectural decisions
- Debugging complex issues, root cause analysis
- Prompt engineering and optimizing Claude API calls (e.g. `viral_detector.py`)
- Pipeline logic changes in `main.py`
- Any task requiring multi-step reasoning or cross-file understanding

When in doubt, start with Sonnet. Escalate to Opus only when the task involves complex logic, multi-file coordination, or deep reasoning.

## Key Conventions

- **CLI framework:** Click for argument parsing
- **Terminal UI:** Rich library for all console output (panels, tables, progress bars) — no stdlib logging
- **Claude integration:** Sends full transcript + visual energy map to Claude; expects strictly structured JSON back (viral_score, emotional_trigger, hook, timestamps)
- **Video output:** All clips are 9:16 vertical with word-level animated captions burned in via FFmpeg/pysubs2
- **Flat file structure:** All modules live in the project root, no src/ directory despite README references to `src/main.py`

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `LEARNINGS.md` with the pattern
- Write rules that prevent the same mistake from recurring
- Ruthlessly iterate on lessons until mistake rate drops
- Review `LEARNINGS.md` at session start for relevant context

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes, pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing tests without being told how

## Task Management

1. **Plan First:** Write plan to `tasks/todo.md` with checkable items
2. **Verify Plans:** Check in before starting implementation
3. **Track Progress:** Mark items complete as you go
4. **Explain Changes:** High-level summary at each step
5. **Document Results:** Add review section to `tasks/todo.md`
6. **Capture Lessons:** Update `LEARNINGS.md` after corrections

## Core Principles

- **Simplicity First:** Make every change as simple as possible. Impact minimal code.
- **Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.
