"""Config API routes — read and write config.yaml."""

import yaml
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config_loader import load_config

router = APIRouter()

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


@router.get("/config")
async def get_config():
    return load_config()


@router.put("/config")
async def save_config(request: Request):
    form = await request.form()

    # Rebuild nested config dict from flat form keys like "anthropic.api_key"
    config = {}
    for key, value in form.items():
        parts = key.split(".")
        if len(parts) == 2:
            section, field = parts
            if section not in config:
                config[section] = {}
            # Type coercion
            if value == "true":
                value = True
            elif value == "false":
                value = False
            else:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        pass
            config[section][field] = value

    # Handle unchecked checkboxes (they don't submit)
    if "captions" in config and "enabled" not in config["captions"]:
        config["captions"]["enabled"] = False

    # Write to YAML
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    return HTMLResponse('<p style="color:var(--pico-color-green-500);">Config saved.</p>')
