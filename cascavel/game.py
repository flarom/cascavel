"""Core game model for Cascavel.

This module intentionally has no GTK dependency so it can be tested
without a display server.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

Cell = tuple[int, int]
Direction = tuple[int, int]

UP: Direction = (0, -1)
DOWN: Direction = (0, 1)
LEFT: Direction = (-1, 0)
RIGHT: Direction = (1, 0)

DIRECTIONS = (UP, DOWN, LEFT, RIGHT)

SIZE_PRESETS: dict[str, tuple[str, int]] = {
    "small": ("Small", 16),
    "medium": ("Medium", 32),
    "large": ("Large", 64),
}

DEFAULT_SIZE = 16
INITIAL_LENGTH = 4

DEFAULT_SPEED = 8
MIN_SPEED = 1
MAX_SPEED = 16

# An apple with walls on three or four sides can be impossible to reach.
MAX_APPLE_WALL_NEIGHBORS = 2

# Why a snake died. ``None`` means the game ended without a collision (for
# example, because there was no room left to spawn an apple).
DEATH_WALL = "wall"
DEATH_CRASH = "crash"
DEATH_SELF = "self"


@dataclass
class GameOptions:
    """Options selected on the title and preferences screens."""

    grid_size: int = DEFAULT_SIZE
    speed: int = DEFAULT_SPEED
    border_collision: bool = False
    wall_generation: bool = False


class Snake:
    """A snake's body, direction and buffered turns."""

    def __init__(self, body: list[Cell], direction: Direction) -> None:
        # The head is the first cell.
        self.body = list(body)
        self.direction = direction
        self.pending: deque[Direction] = deque()
        self.score = 0
        self.alive = True


class Game:
    """A single game of Snake for one or two players."""

    def __init__(
        self,
        options: GameOptions,
        players: int = 1,
        seed: int | None = None,
    ) -> None:
        if players not in (1, 2):
            raise ValueError("players must be 1 or 2")

        self.options = options
        self.grid_size = options.grid_size
        self.players = players
        self.border_collision = options.border_collision
        self.wall_generation = options.wall_generation
        self.rng = random.Random(seed)

        self.walls: set[Cell] = set()
        self.apples: list[Cell] = []
        self.game_over = False
        self.dead_players: list[int] = []
        self.death_reasons: dict[int, str] = {}

        self.snakes = self._create_snakes()
        if self.wall_generation:
            self._generate_walls()

        for _ in range(self.players):
            self._spawn_apple(min_head_distance=4)

    # SETUP

    def _create_snakes(self) -> list[Snake]:
        n = self.grid_size

        if self.players == 1:
            head_x = n // 2
            head_y = n // 2
            body = [(head_x - i, head_y) for i in range(INITIAL_LENGTH)]
            return [Snake(body, RIGHT)]

        # player one starts left of centre heading right. player two is the
        # same snake rotated 180 degrees, which keeps the two spawn areas
        # symmetric for wall generation.
        p1_head = (n // 4, n // 2 + 2)
        p1_body = [(p1_head[0] - i, p1_head[1]) for i in range(INITIAL_LENGTH)]
        p2_body = [(n - 1 - x, n - 1 - y) for x, y in p1_body]

        return [Snake(p1_body, RIGHT), Snake(p2_body, LEFT)]

    def _mirror_cell(self, cell: Cell) -> set[Cell]:
        """Return the four cells that make up the quad symmetry of *cell*."""
        n = self.grid_size
        x, y = cell
        return {
            (x, y),
            (n - 1 - x, y),
            (x, n - 1 - y),
            (n - 1 - x, n - 1 - y),
        }

    def _generate_walls(self) -> None:
        """Generate a sparse, quad-symmetric set of walls.

        Only the top-left quarter is generated.  Every accepted quarter cell
        is mirrored into the other three quarters, so the final set is always
        symmetric.  Cells close to the snakes' spawns are reserved.
        """
        n = self.grid_size
        if n < 16:
            return # too small

        half = n // 2
        target = max(8, round(half * half * 0.04))

        # Keep a safety margin around both spawns, but use a tighter one on
        # the smallest board.  A two-cell margin there would cover nearly the
        # whole quarter when two snakes are present, leaving only one possible
        # row for walls and producing the same layout every game.
        spawn_padding = 1 if n <= 16 else 2

        forbidden: set[Cell] = set()
        for snake in self.snakes:
            for x, y in snake.body:
                for dx in range(-spawn_padding, spawn_padding + 1):
                    for dy in range(-spawn_padding, spawn_padding + 1):
                        forbidden.add((x + dx, y + dy))

        candidates: set[Cell] = set()
        attempts = 0

        while len(candidates) < target and attempts < 150:
            attempts += 1

            seed_x = self.rng.randrange(2, half - 1)
            seed_y = self.rng.randrange(2, half - 1)
            seed = (seed_x, seed_y)
            if any(cell in forbidden for cell in self._mirror_cell(seed)):
                continue

            blob = [seed]
            x, y = seed
            blob_length = self.rng.randint(3, max(4, half // 4))

            for _ in range(blob_length):
                steps = [RIGHT, LEFT, DOWN, UP]
                self.rng.shuffle(steps)
                moved = False

                for dx, dy in steps:
                    nx, ny = x + dx, y + dy
                    if not (2 <= nx < half - 2 and 2 <= ny < half - 2):
                        continue
                    if (nx, ny) in blob:
                        continue
                    if any(
                        cell in forbidden
                        for cell in self._mirror_cell((nx, ny))
                    ):
                        continue

                    x, y = nx, ny
                    blob.append((x, y))
                    moved = True
                    break

                if not moved:
                    break

            candidates.update(blob)

        for cell in candidates:
            self.walls.update(self._mirror_cell(cell))

    def _wall_neighbor_count(self, cell: Cell) -> int:
        """Count walls directly next to *cell* in the four move directions."""
        x, y = cell
        return sum(
            (x + dx, y + dy) in self.walls for dx, dy in DIRECTIONS
        )

    def _spawn_apple(self, min_head_distance: int = 2) -> bool:
        """Place one apple on a free cell, if there is one."""
        n = self.grid_size
        occupied: set[Cell] = set(self.walls)
        for snake in self.snakes:
            occupied.update(snake.body)
        occupied.update(self.apples)

        free: list[Cell] = [
            (x, y)
            for y in range(n)
            for x in range(n)
            if (x, y) not in occupied
        ]
        if not free:
            return False

        # Do not place apples in pockets where three or more sides are
        # blocked by walls.  Even if one approach remains, the snake's body
        # can make it impossible to reach without crashing.
        free = [
            cell
            for cell in free
            if self._wall_neighbor_count(cell) <= MAX_APPLE_WALL_NEIGHBORS
        ]
        if not free:
            return False

        heads = [snake.body[0] for snake in self.snakes]
        farther = [
            cell
            for cell in free
            if all(
                abs(cell[0] - head[0]) + abs(cell[1] - head[1])
                >= min_head_distance
                for head in heads
            )
        ]
        if farther:
            free = farther

        self.apples.append(self.rng.choice(free))
        return True

    # GAMEPLAY

    def turn(self, player: int, direction: Direction) -> None:
        """Queue a direction change for *player* (0 or 1)."""
        if self.game_over or not 0 <= player < len(self.snakes):
            return
        if direction not in DIRECTIONS:
            return

        snake = self.snakes[player]
        last = snake.pending[-1] if snake.pending else snake.direction

        # ignore repeats and 180 degree turns.
        if direction == last or direction == (-last[0], -last[1]):
            return

        # a small queue makes quick, tight turns feel responsive without
        # letting input get too far ahead of the simulation. Ignore extra
        # input while the queue is full rather than dropping an earlier turn
        # (which could leave a 180 degree turn at the front of the queue).
        if len(snake.pending) >= 2:
            return
        snake.pending.append(direction)

    def step(self) -> None:
        """Advance the simulation by one move."""
        if self.game_over:
            return

        for snake in self.snakes:
            if snake.pending:
                snake.direction = snake.pending.popleft()

        heads: list[Cell] = []
        outside: list[bool] = []

        for snake in self.snakes:
            head_x, head_y = snake.body[0]
            dx, dy = snake.direction
            nx, ny = head_x + dx, head_y + dy

            is_outside = not (0 <= nx < self.grid_size and 0 <= ny < self.grid_size)
            if is_outside and not self.border_collision:
                nx %= self.grid_size
                ny %= self.grid_size

            heads.append((nx, ny))
            outside.append(is_outside)

        eating = [head in self.apples for head in heads]

        # bodies after the tails have moved: moving into a vacated tail cell
        # is legal.
        bodies = [
            set(snake.body if eats else snake.body[:-1])
            for snake, eats in zip(self.snakes, eating)
        ]

        dead_players: set[int] = set()
        reasons: dict[int, str] = {}
        for index, head in enumerate(heads):
            if (outside[index] and self.border_collision) or head in self.walls:
                dead_players.add(index)
                reasons[index] = DEATH_WALL
                continue
            for body_index, body in enumerate(bodies):
                if head in body:
                    dead_players.add(index)
                    reasons[index] = (
                        DEATH_SELF if body_index == index else DEATH_CRASH
                    )
                    break

        for i in range(len(heads)):
            for j in range(i):
                if heads[i] == heads[j]:
                    dead_players.add(i)
                    dead_players.add(j)
                    reasons.setdefault(i, DEATH_CRASH)
                    reasons.setdefault(j, DEATH_CRASH)

        if dead_players:
            self.game_over = True
            self.dead_players = sorted(dead_players)
            self.death_reasons = reasons
            for index in self.dead_players:
                self.snakes[index].alive = False
            return

        for snake, head, eats in zip(self.snakes, heads, eating):
            snake.body.insert(0, head)
            if not eats:
                snake.body.pop()
            else:
                snake.score += 1
                self.apples.remove(head)

        while len(self.apples) < self.players:
            if not self._spawn_apple():
                self.game_over = True
                break

    def score_text(self) -> str:
        if self.players == 1:
            return f"Score: {self.snakes[0].score}"
        return f"{self.snakes[0].score} × {self.snakes[1].score}"
