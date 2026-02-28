"""Configuration loader for Viral Clipper."""

import os
import yaml
from pathlib import Path


DEFAULT_CONFIG = {
    "anthropic": {
        "api_key": "",
        "model": "claude-sonnet-4-20250514",
    },
    "clips": {
        "min_duration": 15,
        "max_duration": 60,
        "target_duration": 35,
        "clips_per_video": 5,
    },
    "output": {
        "resolution": "1080x1920",
        "fps": 30,
        "video_bitrate": "5M",
        "audio_bitrate": "192k",
    },
    "captions": {
        "enabled": True,
        "font": "Arial-Bold",
        "font_size": 22,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 3,
        "position": "center",
        "words_per_group": 3,
        "highlight_color": "&H0000FFFF",
    },
    "scene_detection": {
        "threshold": 30.0,
        "min_scene_length": 1.0,
    },
}


def load_config(config_path: str = None) -> dict:
    """Load config from yaml file, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()

    if config_path is None:
        config_path = Path(__file__).parent / "config" / "config.yaml"
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        # Deep merge
        for key, value in user_config.items():
            if isinstance(value, dict) and key in config:
                config[key].update(value)
            else:
                config[key] = value

    # Env var takes precedence over config file
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        config["anthropic"]["api_key"] = env_key

    return config
