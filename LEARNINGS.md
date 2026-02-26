# LEARNINGS.md — Mistake Log & Rule Updates

Every time I get something wrong, it gets logged here with the correction.
Rules evolve based on evidence, not assumption.

Format: newest at top.

---

## Active Rules (Current Best Understanding)

### Content Detection
- R1: A high viral_score moment with a weak lead-in is NOT a good clip — trim to the actual hook
- R2: Word-level caption timing matters; captions that lag 200ms+ behind speech break immersion
- R3: Visual energy alone doesn't predict virality — emotional narrative arc matters more
- R4: Don't cut mid-breath or mid-thought unless it's intentional pattern interrupt

### Pipeline
- R5: Always validate Claude API JSON response structure before passing downstream — strict parsing fails silently on malformed output
- R6: Scene threshold calibration is per-video, not universal — talking head content needs lower threshold than high-cut edited videos
- R7: FFmpeg caption burn-in is blocking; flag this early in batch jobs

### Communication
- R8: State assumptions before asking clarifying questions — don't ask open-ended questions when I can narrow it to 2-3 options
- R9: When the user asks "why isn't this working," check the config and output logs before suggesting code changes

---

## Mistake Log

### [2026-02-24] — Initial entry
No mistakes logged yet. Rules above are priors, not confirmed learnings.
They will be updated or removed as evidence accumulates.

---

## Retired Rules (Proven Wrong)
_(moved here when a rule gets disproven — don't delete, track the reasoning)_

