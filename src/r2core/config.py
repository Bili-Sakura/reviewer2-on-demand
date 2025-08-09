from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path("config/default.yaml")

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_mineru_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get MinerU-specific configuration settings."""
    if config is None:
        config = load_config()

    return config.get(
        "mineru", {"enabled": True, "keep_layout": True, "include_appendix": True}
    )
