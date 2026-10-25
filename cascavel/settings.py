"""Persistent game settings for Cascavel."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .game import (
    MAX_SPEED,
    MIN_SPEED,
    SIZE_PRESETS,
    GameOptions,
)

SETTINGS_VERSION = 1
VALID_GRID_SIZES = tuple(size for _label, size in SIZE_PRESETS.values())


def default_settings_path() -> Path:
    """Return the per-user settings file location."""

    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        config_dir = Path(config_home).expanduser()
    else:
        config_dir = Path.home() / ".config"
    return config_dir / "cascavel" / "settings.json"


class SettingsStore:
    """Load and save game options in a small JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_settings_path()

    def load(self) -> GameOptions:
        options = GameOptions()
        data = self._read()
        if not isinstance(data, dict):
            return options

        grid_size = data.get("grid_size")
        if (
            isinstance(grid_size, int)
            and not isinstance(grid_size, bool)
            and grid_size in VALID_GRID_SIZES
        ):
            options.grid_size = grid_size

        speed = data.get("speed")
        if isinstance(speed, int) and not isinstance(speed, bool):
            options.speed = min(MAX_SPEED, max(MIN_SPEED, speed))

        border_collision = data.get("border_collision")
        if isinstance(border_collision, bool):
            options.border_collision = border_collision

        wall_generation = data.get("wall_generation")
        if isinstance(wall_generation, bool):
            options.wall_generation = wall_generation

        return options

    def save(self, options: GameOptions) -> bool:
        payload = {
            "version": SETTINGS_VERSION,
            "grid_size": options.grid_size,
            "speed": options.speed,
            "border_collision": options.border_collision,
            "wall_generation": options.wall_generation,
        }
        temporary = self.path.with_name(f".{self.path.name}.tmp")

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False

        return True

    def _read(self) -> object:
        try:
            contents = self.path.read_text(encoding="utf-8")
        except OSError:
            return None

        try:
            return json.loads(contents)
        except (TypeError, ValueError):
            return None
