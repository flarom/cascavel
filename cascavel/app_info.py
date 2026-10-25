"""Application constants."""

from __future__ import annotations

from pathlib import Path

APP_ID = "io.github.cascavel.Cascavel"
APP_NAME = "Cascavel"
ICON_NAME = "cascavel"
VERSION = "0.1.0"

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR.parent / "assets"
