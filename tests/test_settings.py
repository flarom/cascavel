from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cascavel.game import DEFAULT_SIZE, DEFAULT_SPEED, MAX_SPEED, GameOptions
from cascavel.settings import (
    SETTINGS_VERSION,
    SettingsStore,
    default_settings_path,
)


class SettingsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "cascavel" / "settings.json"
        self.store = SettingsStore(self.path)

    def test_missing_file_uses_defaults(self) -> None:
        options = self.store.load()

        self.assertEqual(options, GameOptions())
        self.assertEqual(options.grid_size, 16)
        self.assertEqual(options.speed, DEFAULT_SPEED)
        self.assertFalse(options.border_collision)
        self.assertFalse(options.wall_generation)

    def test_round_trip(self) -> None:
        options = GameOptions(
            grid_size=64,
            speed=13,
            border_collision=True,
            wall_generation=True,
        )

        self.assertTrue(self.store.save(options))
        self.assertTrue(self.path.exists())
        self.assertEqual(self.store.load(), options)

        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["version"], SETTINGS_VERSION)
        self.assertEqual(saved["grid_size"], 64)

    def test_invalid_values_fall_back_or_are_clamped(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "grid_size": 1000,
                    "speed": 0,
                    "border_collision": "yes",
                    "wall_generation": 1,
                }
            ),
            encoding="utf-8",
        )

        options = self.store.load()

        self.assertEqual(options.grid_size, DEFAULT_SIZE)
        self.assertEqual(options.speed, 1)
        self.assertFalse(options.border_collision)
        self.assertFalse(options.wall_generation)

    def test_speed_is_clamped_to_the_supported_range(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps({"speed": MAX_SPEED + 100}),
            encoding="utf-8",
        )

        self.assertEqual(self.store.load().speed, MAX_SPEED)

    def test_corrupt_file_uses_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not valid json", encoding="utf-8")

        self.assertEqual(self.store.load(), GameOptions())

    def test_default_path_uses_xdg_config_home(self) -> None:
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": "/tmp/cascavel-test-config"},
        ):
            self.assertEqual(
                default_settings_path(),
                Path("/tmp/cascavel-test-config/cascavel/settings.json"),
            )


if __name__ == "__main__":
    unittest.main()
