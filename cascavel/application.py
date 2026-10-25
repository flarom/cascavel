"""Cascavel application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .app_info import APP_ID, APP_NAME, ASSETS_DIR, ICON_NAME  # noqa: E402
from .window import CascavelWindow  # noqa: E402


class CascavelApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window: CascavelWindow | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)

        display = Gdk.Display.get_default()
        if display is not None:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icon_theme.add_search_path(str(ASSETS_DIR))

            provider = Gtk.CssProvider()
            provider.load_from_path(str(ASSETS_DIR / "style.css"))
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        Gtk.Window.set_default_icon_name(ICON_NAME)
        GLib.set_application_name(APP_NAME)

        self._install_actions()
        self.set_accels_for_action("app.new-game", ["<Control>n"])
        self.set_accels_for_action("app.new-multiplayer-game", ["<Control>m"])
        self.set_accels_for_action(
            "app.preferences", ["<Control>comma"]
        )
        self.set_accels_for_action(
            "app.shortcuts", ["<Control>question", "<Control>slash"]
        )

    def do_activate(self) -> None:
        window = self._ensure_window()
        window.present()

    def _ensure_window(self) -> CascavelWindow:
        if self._window is None:
            self._window = CascavelWindow(self)
            self._window.connect("destroy", self._on_window_destroyed)
        return self._window

    def _on_window_destroyed(self, _window: CascavelWindow) -> None:
        self._window = None

    def _install_actions(self) -> None:
        actions = (
            ("new-game", self._on_new_game),
            ("new-multiplayer-game", self._on_new_multiplayer_game),
            ("preferences", self._on_preferences),
            ("shortcuts", self._on_shortcuts),
            ("about", self._on_about),
        )

        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _on_new_game(
        self, _action: Gio.SimpleAction, _parameter: object
    ) -> None:
        window = self._ensure_window()
        window.present()
        window.start_game(1)

    def _on_new_multiplayer_game(
        self, _action: Gio.SimpleAction, _parameter: object
    ) -> None:
        window = self._ensure_window()
        window.present()
        window.start_game(2)

    def _on_preferences(
        self, _action: Gio.SimpleAction, _parameter: object
    ) -> None:
        window = self._ensure_window()
        window.present()
        window.show_preferences()

    def _on_shortcuts(
        self, _action: Gio.SimpleAction, _parameter: object
    ) -> None:
        window = self._ensure_window()
        window.present()
        window.show_shortcuts()

    def _on_about(
        self, _action: Gio.SimpleAction, _parameter: object
    ) -> None:
        window = self._ensure_window()
        window.present()
        window.show_about()


def main(argv: list[str] | None = None) -> int:
    app = CascavelApplication()
    return app.run(argv if argv is not None else sys.argv)
