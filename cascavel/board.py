"""Cairo drawing for the Cascavel board."""

from __future__ import annotations

import math

import cairo

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk  # noqa: E402

from .game import Cell, Game  # noqa: E402

# COLORS              R           G           B           A
BLANK_DOT          = (0x9A / 255, 0x99 / 255, 0x96 / 255, 0.62)
APPLE              = (0xE0 / 255, 0x1B / 255, 0x24 / 255, 1.0)
FALLBACK_WALL_FILL = (0x3A / 255, 0x3A / 255, 0x3D / 255, 1.0) # fallback colors used if the theme does not provide a wall fill color.
WALL_FILL_COLOR    = "window_fg_color"
WALL_FILL_ALPHA    = 0.25
PLAYER_COLORS = (
    (0x35 / 255, 0x84 / 255, 0xE4 / 255, 1.0),  # blue for player 1,
    (0x33 / 255, 0xD1 / 255, 0x7A / 255, 1.0),  # green for player 2
)

# we are faking drop shadows for walls here
WALL_SHADOW_PASSES = (
    (2.4, 3.0, 0.035),
    (1.5, 2.0, 0.050),
    (0.7, 1.0, 0.065),
)

TAU = math.tau


class GameBoard(Gtk.DrawingArea):
    """Draws a :class:`Game` as a square grid of tiles."""

    def __init__(self) -> None:
        super().__init__()
        self.set_draw_func(self._draw)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_focusable(True)
        self.set_size_request(280, 280)
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Game board"])

        self._game: Game | None = None
        self._background: cairo.ImageSurface | None = None
        self._background_key: tuple | None = None
        self._wall_fill_cache: tuple | None = None

        # repaint structural colors whenever the theme changes
        style_manager = Adw.StyleManager.get_default()
        if style_manager is not None:
            style_manager.connect("notify::dark", self._on_style_changed)
            style_manager.connect(
                "notify::high-contrast", self._on_style_changed
            )
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.connect(
                "notify::gtk-theme-name", self._on_style_changed
            )

    def _on_style_changed(self, *_args: object) -> None:
        self._wall_fill_cache = None
        self._background = None
        self._background_key = None
        self.queue_draw()

    def set_game(self, game: Game | None) -> None:
        self._game = game
        self._background = None
        self._background_key = None
        self.queue_draw()

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context,
        width: int,
        height: int,
    ) -> None:
        game = self._game
        if game is None or width <= 0 or height <= 0:
            return

        grid = game.grid_size
        tile = min(width, height) / grid
        board_size = tile * grid
        offset_x = (width - board_size) / 2
        offset_y = (height - board_size) / 2

        self._draw_background(
            cr, width, height, game, tile, offset_x, offset_y
        )
        self._draw_apples(cr, game, tile, offset_x, offset_y)

        for index, snake in enumerate(game.snakes):
            self._draw_snake(
                cr,
                snake.body,
                PLAYER_COLORS[index % len(PLAYER_COLORS)],
                tile,
                offset_x,
                offset_y,
            )

    # BACKGROUND (dots and walls)

    def _resolve_color(
        self, name: str, fallback: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        context = self.get_style_context()
        found, rgba = context.lookup_color(name)
        if not found:
            return fallback
        return (rgba.red, rgba.green, rgba.blue, rgba.alpha)

    def _wall_fill(self) -> tuple[float, float, float, float]:
        """Return the wall fill colour for the current theme."""
        if self._wall_fill_cache is None:
            fill = self._resolve_color(WALL_FILL_COLOR, FALLBACK_WALL_FILL)
            self._wall_fill_cache = (
                fill[0],
                fill[1],
                fill[2],
                WALL_FILL_ALPHA,
            )
        return self._wall_fill_cache

    def _draw_background(
        self,
        cr: cairo.Context,
        width: int,
        height: int,
        game: Game,
        tile: float,
        offset_x: float,
        offset_y: float,
    ) -> None:
        scale = max(1, self.get_scale_factor())
        wall_fill = self._wall_fill()
        key = (int(width), int(height), scale, wall_fill)

        if self._background is None or self._background_key != key:
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )
            bg = cairo.Context(surface)
            bg.scale(scale, scale)
            self._paint_background(
                bg, game, tile, offset_x, offset_y, wall_fill
            )
            self._background = surface
            self._background_key = key

        cr.save()
        cr.scale(1 / scale, 1 / scale)
        cr.set_source_surface(self._background, 0, 0)
        cr.paint()
        cr.restore()

    def _paint_background(
        self,
        cr: cairo.Context,
        game: Game,
        tile: float,
        offset_x: float,
        offset_y: float,
        wall_fill: tuple[float, float, float, float],
    ) -> None:
        grid = game.grid_size
        dot_radius = max(0.9, tile * 0.08)

        cr.new_path()
        for y in range(grid):
            for x in range(grid):
                if (x, y) in game.walls:
                    continue
                # each dot must be its own sub-path; otherwise cairo joins
                # consecutive arcs with straight lines.
                cr.new_sub_path()
                cr.arc(
                    offset_x + (x + 0.5) * tile,
                    offset_y + (y + 0.5) * tile,
                    dot_radius,
                    0,
                    TAU,
                )
        cr.set_source_rgba(*BLANK_DOT)
        cr.fill()

        radius = max(2.2, min(8.0, tile * 0.30))

        self._draw_wall_shadows(
            cr, game, tile, offset_x, offset_y, radius
        )

        # fill the connected silhouette once. filling tile by tile would
        # double-composite the translucent fill where neighbours overlap,
        # leaving seams between them.
        cr.new_path()
        self._add_wall_union_path(
            cr, game, tile, offset_x, offset_y, radius, 0.0, 0.0
        )
        cr.set_source_rgba(*wall_fill)
        cr.fill()

    def _draw_wall_shadows(
        self,
        cr: cairo.Context,
        game: Game,
        tile: float,
        offset_x: float,
        offset_y: float,
        radius: float,
    ) -> None:
        shadow_scale = max(0.5, min(1.15, tile / 12.0))
        for grow, offset, alpha in WALL_SHADOW_PASSES:
            cr.new_path()
            self._add_wall_union_path(
                cr,
                game,
                tile,
                offset_x,
                offset_y,
                radius,
                grow * shadow_scale,
                offset * shadow_scale,
            )
            cr.set_source_rgba(0, 0, 0, alpha)
            cr.fill()

    def _add_wall_union_path(
        self,
        cr: cairo.Context,
        game: Game,
        tile: float,
        offset_x: float,
        offset_y: float,
        radius: float,
        grow: float,
        shadow_offset: float,
    ) -> None:
        """Append every wall tile to one path.

        Filling the whole silhouette at once means overlapping neighbours
        do not make translucent fills or shadows darker in the middle of a
        wall group.
        """
        walls = game.walls
        for x, y in walls:
            left = (x - 1, y) in walls
            right = (x + 1, y) in walls
            top = (x, y - 1) in walls
            bottom = (x, y + 1) in walls

            px = offset_x + x * tile
            py = offset_y + y * tile + shadow_offset

            x0 = px - grow - (0.5 if left else 0)
            x1 = px + tile + grow + (0.5 if right else 0)
            y0 = py - grow - (0.5 if top else 0)
            y1 = py + tile + grow + (0.5 if bottom else 0)

            corner = radius + grow
            tl = corner if (not left and not top) else 0
            tr = corner if (not right and not top) else 0
            br = corner if (not right and not bottom) else 0
            bl = corner if (not left and not bottom) else 0

            self._rounded_rect(
                cr, x0, y0, x1 - x0, y1 - y0, tl, tr, br, bl
            )

    @staticmethod
    def _rounded_rect(
        cr: cairo.Context,
        x: float,
        y: float,
        width: float,
        height: float,
        tl: float,
        tr: float,
        br: float,
        bl: float,
    ) -> None:
        cr.move_to(x + tl, y)
        cr.line_to(x + width - tr, y)
        if tr:
            cr.arc(x + width - tr, y + tr, tr, -0.5 * math.pi, 0)
        cr.line_to(x + width, y + height - br)
        if br:
            cr.arc(x + width - br, y + height - br, br, 0, 0.5 * math.pi)
        cr.line_to(x + bl, y + height)
        if bl:
            cr.arc(x + bl, y + height - bl, bl, 0.5 * math.pi, math.pi)
        cr.line_to(x, y + tl)
        if tl:
            cr.arc(x + tl, y + tl, tl, math.pi, 1.5 * math.pi)
        cr.close_path()

    # APPLES AND SNAKES

    def _draw_apples(
        self,
        cr: cairo.Context,
        game: Game,
        tile: float,
        offset_x: float,
        offset_y: float,
    ) -> None:
        cr.set_source_rgba(*APPLE)
        for x, y in game.apples:
            cr.new_sub_path()
            cr.arc(
                offset_x + (x + 0.5) * tile,
                offset_y + (y + 0.5) * tile,
                max(1.8, tile * 0.30),
                0,
                TAU,
            )
            cr.fill()

    def _draw_snake(
        self,
        cr: cairo.Context,
        body: list[Cell],
        color: tuple[float, float, float, float],
        tile: float,
        offset_x: float,
        offset_y: float,
    ) -> None:
        if not body:
            return

        # a teleport breaks the body into visually separate runs
        runs: list[list[Cell]] = []
        run: list[Cell] = [body[0]]
        for cell in body[1:]:
            previous = run[-1]
            if (
                abs(cell[0] - previous[0]) + abs(cell[1] - previous[1])
                == 1
            ):
                run.append(cell)
            else:
                runs.append(run)
                run = [cell]
        runs.append(run)

        line_width = max(2.0, tile * 0.72)
        cr.set_source_rgba(*color)
        cr.set_line_width(line_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        for segment in runs:
            if len(segment) == 1:
                x, y = segment[0]
                cr.new_sub_path()
                cr.arc(
                    offset_x + (x + 0.5) * tile,
                    offset_y + (y + 0.5) * tile,
                    line_width / 2,
                    0,
                    TAU,
                )
                cr.fill()
                continue

            first_x, first_y = segment[0]
            cr.move_to(
                offset_x + (first_x + 0.5) * tile,
                offset_y + (first_y + 0.5) * tile,
            )
            for x, y in segment[1:]:
                cr.line_to(
                    offset_x + (x + 0.5) * tile,
                    offset_y + (y + 0.5) * tile,
                )
            cr.stroke()
