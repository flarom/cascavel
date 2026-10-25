"""The main application window and its three views."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .app_info import APP_NAME, ICON_NAME, VERSION  # noqa: E402
from .board import GameBoard  # noqa: E402
from .game import (  # noqa: E402
    DEFAULT_SIZE,
    DEATH_CRASH,
    DEATH_SELF,
    DEATH_WALL,
    DOWN,
    LEFT,
    MAX_SPEED,
    MIN_SPEED,
    RIGHT,
    SIZE_PRESETS,
    UP,
    Game,
)
from .settings import SettingsStore  # noqa: E402


class CascavelWindow(Adw.ApplicationWindow):
    def __init__(self, application: Gtk.Application) -> None:
        super().__init__(application=application)

        self._settings = SettingsStore()
        self.options = self._settings.load()
        self._game: Game | None = None
        self._players = 1
        self._tick_source = 0
        self._dialog_open = False
        self._closing = False

        self.set_title(APP_NAME)
        self.set_default_size(480, 522)
        self.set_size_request(480, 522)

        self._build_ui()
        self._install_input()
        self._show_title()

        self.connect("close-request", self._on_close_request)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._toolbar = Adw.ToolbarView()
        self._header = Adw.HeaderBar()
        self._window_title = Adw.WindowTitle(title=APP_NAME)
        self._header.set_title_widget(self._window_title)

        self._back_button = Gtk.Button(icon_name="go-previous-symbolic")
        self._back_button.add_css_class("flat")
        self._back_button.set_tooltip_text("Back")
        self._back_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Back"]
        )
        self._back_button.connect("clicked", self._on_back_clicked)

        self._left_controls = Gtk.Box(spacing=6)
        self._left_controls.append(self._back_button)
        self._header.pack_start(self._left_controls)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_button.set_tooltip_text("Main menu")
        menu_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Main menu"]
        )
        menu_button.set_menu_model(self._build_menu())
        self._menu_button = menu_button
        self._header.pack_end(menu_button)

        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=180,
            hexpand=True,
            vexpand=True,
        )
        self._stack.add_named(self._build_title_view(), "title")
        self._stack.add_named(self._build_game_view(), "game")

        self._toolbar.add_top_bar(self._header)
        self._toolbar.set_content(self._stack)
        self.set_content(self._toolbar)

    def _build_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("New game", "app.new-game")
        menu.append("New multiplayer game", "app.new-multiplayer-game")

        section = Gio.Menu()
        section.append("Preferences", "app.preferences")
        section.append("Keyboard shortcuts", "app.shortcuts")
        section.append("About Cascavel", "app.about")
        menu.append_section(None, section)

        return menu

    def _build_title_view(self) -> Gtk.Widget:
        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )

        centre = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            width_request=360,
        )

        logo = Gtk.Image.new_from_icon_name(ICON_NAME)
        logo.set_pixel_size(160)
        logo.set_halign(Gtk.Align.CENTER)
        panel.append(logo)

        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        new_game_button = Gtk.Button(label="New game")
        new_game_button.add_css_class("pill")
        new_game_button.set_size_request(-1, 44)
        new_game_button.connect("clicked", lambda _button: self.start_game(1))
        buttons.append(new_game_button)
        self._title_new_button = new_game_button

        multiplayer_button = Gtk.Button(label="New multiplayer game")
        multiplayer_button.add_css_class("pill")
        multiplayer_button.set_size_request(-1, 44)
        multiplayer_button.connect("clicked", lambda _button: self.start_game(2))
        buttons.append(multiplayer_button)

        panel.append(buttons)
        centre.append(panel)
        outer.append(centre)

        return outer

    def _build_game_view(self) -> Gtk.Widget:
        overlay = Gtk.Overlay(hexpand=True, vexpand=True)

        board_holder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=16,
        )

        aspect = Gtk.AspectFrame(ratio=1.0, obey_child=False)
        aspect.set_hexpand(True)
        aspect.set_vexpand(True)

        self._board = GameBoard()
        aspect.set_child(self._board)
        board_holder.append(aspect)
        overlay.set_child(board_holder)

        self._game_over_wrap = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
            visible=False,
        )

        panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            width_request=340,
        )
        panel.add_css_class("cascavel-popup")

        game_over_label = Gtk.Label(label="Ouch!")
        game_over_label.add_css_class("game-over-title")
        panel.append(game_over_label)
        self._game_over_title = game_over_label

        self._game_over_deaths = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            visible=False,
        )
        self._game_over_death_labels: list[Gtk.Label] = []
        for index in range(2):
            label = Gtk.Label(halign=Gtk.Align.CENTER)
            #label.add_css_class("cascavel-death-label")
            label.add_css_class("dimmed")
            label.set_visible(False)
            self._game_over_deaths.append(label)
            self._game_over_death_labels.append(label)
        panel.append(self._game_over_deaths)

        self._game_over_score = Gtk.Label()
        self._game_over_score.add_css_class("score-label")
        self._game_over_score.set_halign(Gtk.Align.CENTER)
        panel.append(self._game_over_score)

        game_over_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )

        back_button = Gtk.Button(icon_name="go-previous-symbolic")
        back_button.add_css_class("circular")
        back_button.set_size_request(48, 48)
        back_button.set_tooltip_text("Back")
        back_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Back"]
        )
        back_button.connect("clicked", self._on_back_clicked)
        game_over_buttons.append(back_button)

        self._game_over_new_button = Gtk.Button(label="Play again")
        self._game_over_new_button.add_css_class("pill")
        self._game_over_new_button.add_css_class("suggested-action")
        self._game_over_new_button.set_hexpand(True)
        self._game_over_new_button.set_size_request(-1, 48)
        self._game_over_new_button.connect(
            "clicked", lambda _button: self.start_game(self._players)
        )
        game_over_buttons.append(self._game_over_new_button)

        panel.append(game_over_buttons)
        self._game_over_wrap.append(panel)
        overlay.add_overlay(self._game_over_wrap)

        return overlay

    # VIEWS AND GAME LIFECYCLE

    def _show_title(self) -> None:
        self._stop_tick()
        self._stack.set_visible_child_name("title")
        self._game_over_wrap.set_visible(False)
        self._left_controls.set_visible(False)
        self._window_title.set_subtitle("")
        self._title_new_button.grab_focus()

    def start_game(self, players: int) -> None:
        self._stop_tick()
        self._players = players
        self._game = Game(self.options, players=players)
        self._board.set_game(self._game)
        self._game_over_wrap.set_visible(False)

        self._stack.set_visible_child_name("game")
        self._left_controls.set_visible(True)
        self._update_score_labels()

        self._board.grab_focus()
        if not self._dialog_open:
            self._start_tick()

    def _restart_game(self) -> None:
        self.start_game(self._players)

    def _show_game_over(self) -> None:
        if self._game is None:
            return

        for index in (1, 2):
            self._game_over_title.remove_css_class(f"cascavel-player-{index}")

        dead_players = (
            set(self._game.dead_players)
            if self._game.players == 2
            else set()
        )

        winner: int | None = None
        if len(dead_players) == 1:
            winner = 1 - next(iter(dead_players))

        if winner is not None:
            self._game_over_title.set_label(f"Player {winner + 1} wins!")
            self._game_over_title.add_css_class(
                f"cascavel-player-{winner + 1}"
            )
        else:
            self._game_over_title.set_label("Ouch!")

        for index, label in enumerate(self._game_over_death_labels):
            is_dead = index in dead_players
            if is_dead:
                label.set_label(self._death_message(index))
            label.set_visible(is_dead)
        self._game_over_deaths.set_visible(bool(dead_players))

        self._game_over_score.set_label(self._game.score_text())
        self._game_over_wrap.set_visible(True)
        self._game_over_new_button.grab_focus()

    def _death_message(self, player: int) -> str:
        if self._game is None:
            return ""

        reason = self._game.death_reasons.get(player)
        name = f"Player {player + 1}"

        if reason == DEATH_WALL:
            return f"{name} hit a wall"
        if reason == DEATH_CRASH:
            opponent = 2 if player == 0 else 1
            return f"{name} crashed into Player {opponent}"
        if reason == DEATH_SELF:
            return f"{name} bit its own tail"
        return f"{name} ran out of room"

    def _update_score_labels(self) -> None:
        if self._game is None:
            self._window_title.set_subtitle("")
            return

        text = self._game.score_text()
        self._window_title.set_subtitle(text)
        self._game_over_score.set_label(text)

    def _start_tick(self) -> None:
        # speed is expressed as moves per second, so convert it to the
        # millisecond interval expected by GLib.
        interval = max(1, round(1000 / max(1, self.options.speed)))
        self._tick_source = GLib.timeout_add(interval, self._on_tick)

    def _stop_tick(self) -> None:
        if self._tick_source:
            GLib.source_remove(self._tick_source)
            self._tick_source = 0

    def _on_tick(self) -> bool:
        if self._game is None or self._game.game_over:
            self._tick_source = 0
            return GLib.SOURCE_REMOVE

        self._game.step()
        self._board.queue_draw()
        self._update_score_labels()

        if self._game.game_over:
            self._tick_source = 0
            self._show_game_over()
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        self._show_title()

    def _on_restart_clicked(self, _button: Gtk.Button) -> None:
        self._restart_game()

    # INPUT

    def _install_input(self) -> None:
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

        one_finger = Gtk.GestureSwipe(n_points=1)
        one_finger.set_touch_only(False)
        one_finger.connect("swipe", self._on_swipe, 0)
        self._board.add_controller(one_finger)

        two_fingers = Gtk.GestureSwipe(n_points=2, touch_only=True)
        two_fingers.connect("swipe", self._on_swipe, 1)
        self._board.add_controller(two_fingers)

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if (
            self._game is None
            or self._game.game_over
            or self._dialog_open
            or self._stack.get_visible_child_name() != "game"
        ):
            return False

        if state & (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.SUPER_MASK
            | Gdk.ModifierType.META_MASK
        ):
            return False

        player_one_keys = {
            Gdk.KEY_w: UP,
            Gdk.KEY_W: UP,
            Gdk.KEY_a: LEFT,
            Gdk.KEY_A: LEFT,
            Gdk.KEY_s: DOWN,
            Gdk.KEY_S: DOWN,
            Gdk.KEY_d: RIGHT,
            Gdk.KEY_D: RIGHT,
        }
        if keyval in player_one_keys:
            self._game.turn(0, player_one_keys[keyval])
            return True

        player_two_keys = {
            Gdk.KEY_Up: UP,
            Gdk.KEY_KP_Up: UP,
            Gdk.KEY_Left: LEFT,
            Gdk.KEY_KP_Left: LEFT,
            Gdk.KEY_Down: DOWN,
            Gdk.KEY_KP_Down: DOWN,
            Gdk.KEY_Right: RIGHT,
            Gdk.KEY_KP_Right: RIGHT,
        }
        if keyval in player_two_keys:
            player = 1 if self._game.players == 2 else 0
            self._game.turn(player, player_two_keys[keyval])
            return True

        return False

    def _on_swipe(
        self,
        _gesture: Gtk.GestureSwipe,
        velocity_x: float,
        velocity_y: float,
        gesture_player: int,
    ) -> None:
        if (
            self._game is None
            or self._game.game_over
            or self._dialog_open
            or self._stack.get_visible_child_name() != "game"
        ):
            return

        if abs(velocity_x) >= abs(velocity_y):
            if velocity_x == 0:
                return
            direction = RIGHT if velocity_x > 0 else LEFT
        else:
            direction = DOWN if velocity_y > 0 else UP

        player = 0 if self._game.players == 1 else gesture_player
        self._game.turn(player, direction)

    # DIALOGS

    def show_preferences(self) -> None:
        dialog = Adw.PreferencesDialog()
        dialog.set_title("Preferences")

        page = Adw.PreferencesPage()
        page.set_title("Gameplay")

        # Gameplay
        gameplayGroup = Adw.PreferencesGroup()
        gameplayGroup.set_title("Gameplay")

        speed_row = Adw.SpinRow.new_with_range(MIN_SPEED, MAX_SPEED, 1)
        speed_row.set_title("Speed")
        speed_row.set_subtitle("In moves per second")
        speed_row.set_digits(0)
        speed_row.set_value(self.options.speed)
        speed_row.connect("notify::value", self._on_speed_changed)
        gameplayGroup.add(speed_row)

        # Board
        boardGroup = Adw.PreferencesGroup()
        boardGroup.set_title("Board")

        size_values = [value for _label, value in SIZE_PRESETS.values()]
        size_row = Adw.ComboRow()
        size_row.set_title("Size")
        size_row.set_model(
            Gtk.StringList.new(
                [label for label, _value in SIZE_PRESETS.values()]
            )
        )
        try:
            selected_size = size_values.index(self.options.grid_size)
        except ValueError:
            selected_size = size_values.index(DEFAULT_SIZE)
        size_row.set_selected(selected_size)
        size_row.connect(
            "notify::selected", self._on_size_changed, size_values
        )
        boardGroup.add(size_row)

        walls_row = Adw.SwitchRow()
        walls_row.set_title("Wall generation")
        walls_row.set_active(self.options.wall_generation)
        walls_row.connect("notify::active", self._on_wall_generation_changed)
        boardGroup.add(walls_row)

        border_row = Adw.SwitchRow()
        border_row.set_title("Border collision")
        border_row.set_subtitle(
            "End the game at the board edge instead of wrapping around"
        )
        border_row.set_active(self.options.border_collision)
        border_row.connect("notify::active", self._on_border_collision_changed)
        boardGroup.add(border_row)

        page.add(gameplayGroup)
        page.add(boardGroup)
        dialog.add(page)
        self._present_dialog(dialog)

    def _on_size_changed(
        self,
        row: Adw.ComboRow,
        _pspec: object,
        size_values: list[int],
    ) -> None:
        selected = row.get_selected()
        if 0 <= selected < len(size_values):
            self.options.grid_size = size_values[selected]
            self._save_options()

    def _on_speed_changed(
        self, row: Adw.SpinRow, _pspec: object
    ) -> None:
        self.options.speed = int(round(row.get_value()))
        self._save_options()

    def _on_border_collision_changed(
        self, row: Adw.SwitchRow, _pspec: object
    ) -> None:
        self.options.border_collision = row.get_active()
        self._save_options()

    def _on_wall_generation_changed(
        self, row: Adw.SwitchRow, _pspec: object
    ) -> None:
        self.options.wall_generation = row.get_active()
        self._save_options()

    def _save_options(self) -> None:
        self._settings.save(self.options)

    def _present_dialog(self, dialog: Adw.Dialog) -> None:
        # do not let the snake run into a wall while the player is reading a
        # dialog. the game resumes when the dialog closes.
        self._dialog_open = True
        self._stop_tick()
        dialog.connect("closed", self._on_dialog_closed)
        dialog.present(self)

    def _on_dialog_closed(self, _dialog: Adw.Dialog) -> None:
        self._dialog_open = False
        if self._closing:
            return
        if (
            self._game is not None
            and not self._game.game_over
            and self._stack.get_visible_child_name() == "game"
            and not self._tick_source
        ):
            self._start_tick()

    def show_shortcuts(self) -> None:
        dialog = Adw.ShortcutsDialog()
        dialog.set_title("Keyboard Shortcuts")

        general = Adw.ShortcutsSection(title="General")
        general.add(
            Adw.ShortcutsItem(title="New game", accelerator="<Control>n")
        )
        general.add(
            Adw.ShortcutsItem(title="New multiplayer game", accelerator="<Control>m")
        )
        general.add(
            Adw.ShortcutsItem(title="Preferences", accelerator="<Control>comma")
        )
        general.add(
            Adw.ShortcutsItem(
                title="Keyboard shortcuts", accelerator="<Control>question"
            )
        )
        dialog.add(general)

        player_one = Adw.ShortcutsSection(title="Player 1")
        for title, accelerator in (
            ("Move up", "W"),
            ("Move left", "A"),
            ("Move down", "S"),
            ("Move right", "D"),
        ):
            player_one.add(
                Adw.ShortcutsItem(title=title, accelerator=accelerator)
            )
        dialog.add(player_one)

        player_two = Adw.ShortcutsSection(title="Player 2")
        for title, accelerator in (
            ("Move up", "Up"),
            ("Move left", "Left"),
            ("Move down", "Down"),
            ("Move right", "Right"),
        ):
            player_two.add(
                Adw.ShortcutsItem(title=title, accelerator=accelerator)
            )
        dialog.add(player_two)

        self._present_dialog(dialog)

    def show_about(self) -> None:
        dialog = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=ICON_NAME,
            version=VERSION,
            developer_name="Flarom",
            website="https://flarom.neocities.org/arcade/cascavel",
            developers=["Flarom https://flarom.neocities.org/"],
            copyright="""© 2020-2025 Flarom.

This application has absolutely no warranty. See the GNU General Public License, version 3 or later, for details.""",
        )
        self._present_dialog(dialog)

    # TEARDOWN

    def _on_close_request(self, _window: Adw.ApplicationWindow) -> bool:
        self._closing = True
        self._stop_tick()
        self._save_options()
        return False
