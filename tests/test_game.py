from __future__ import annotations

import unittest

from cascavel.game import (
    DEFAULT_SIZE,
    DEFAULT_SPEED,
    DEATH_CRASH,
    DEATH_SELF,
    DEATH_WALL,
    DIRECTIONS,
    DOWN,
    LEFT,
    MAX_SPEED,
    MIN_SPEED,
    RIGHT,
    SIZE_PRESETS,
    UP,
    Game,
    GameOptions,
)


class GameSetupTests(unittest.TestCase):
    def test_size_presets(self) -> None:
        self.assertEqual(SIZE_PRESETS["small"], ("Small", 16))
        self.assertEqual(SIZE_PRESETS["medium"], ("Medium", 32))
        self.assertEqual(SIZE_PRESETS["large"], ("Large", 64))
        self.assertEqual(DEFAULT_SIZE, 16)

    def test_speed_option(self) -> None:
        options = GameOptions()
        self.assertEqual(options.speed, DEFAULT_SPEED)
        self.assertGreaterEqual(options.speed, MIN_SPEED)
        self.assertLessEqual(options.speed, MAX_SPEED)

    def test_single_player_setup(self) -> None:
        game = Game(GameOptions(), players=1, seed=1)

        self.assertEqual(game.players, 1)
        self.assertEqual(len(game.snakes), 1)
        self.assertEqual(len(game.apples), 1)
        self.assertEqual(game.snakes[0].score, 0)
        self.assertFalse(game.game_over)

    def test_multiplayer_setup(self) -> None:
        game = Game(GameOptions(), players=2, seed=1)

        self.assertEqual(len(game.snakes), 2)
        self.assertEqual(len(game.apples), 2)

        # Both snakes exist, point away from each other and do not overlap.
        first, second = game.snakes
        self.assertEqual(first.direction, RIGHT)
        self.assertEqual(second.direction, LEFT)
        self.assertFalse(set(first.body) & set(second.body))

    def test_apples_are_on_free_cells(self) -> None:
        game = Game(
            GameOptions(grid_size=32, wall_generation=True),
            players=2,
            seed=3,
        )

        occupied = set(game.walls)
        for snake in game.snakes:
            occupied.update(snake.body)

        self.assertEqual(len(game.apples), 2)
        self.assertEqual(len(set(game.apples)), 2)
        for apple in game.apples:
            self.assertNotIn(apple, occupied)


class MovementTests(unittest.TestCase):
    def _game_at_edge(self, border_collision: bool) -> Game:
        game = Game(
            GameOptions(grid_size=32, border_collision=border_collision),
            seed=5,
        )
        snake = game.snakes[0]
        snake.body = [(31, 10), (30, 10), (29, 10), (28, 10)]
        snake.direction = RIGHT
        game.apples = [(0, 0)]
        return game

    def test_wraps_when_border_collision_is_off(self) -> None:
        game = self._game_at_edge(border_collision=False)

        game.step()

        self.assertFalse(game.game_over)
        self.assertEqual(game.snakes[0].body[0], (0, 10))
        self.assertEqual(len(game.snakes[0].body), 4)

    def test_dies_when_border_collision_is_on(self) -> None:
        game = self._game_at_edge(border_collision=True)

        game.step()

        self.assertTrue(game.game_over)
        self.assertEqual(game.dead_players, [0])
        self.assertFalse(game.snakes[0].alive)
        self.assertEqual(game.death_reasons[0], DEATH_WALL)

    def test_walls_still_collide_without_border_collision(self) -> None:
        game = Game(GameOptions(grid_size=32), seed=5)
        snake = game.snakes[0]
        snake.body = [(9, 10), (8, 10), (7, 10), (6, 10)]
        snake.direction = RIGHT
        game.walls = {(10, 10)}
        game.apples = [(0, 0)]

        game.step()

        self.assertTrue(game.game_over)

    def test_eating_grows_the_snake_and_scores(self) -> None:
        game = Game(GameOptions(grid_size=32), seed=5)
        snake = game.snakes[0]
        snake.body = [(10, 10), (9, 10), (8, 10), (7, 10)]
        snake.direction = RIGHT
        game.apples = [(11, 10)]

        game.step()

        self.assertFalse(game.game_over)
        self.assertEqual(snake.score, 1)
        self.assertEqual(len(snake.body), 5)
        self.assertEqual(snake.body[0], (11, 10))
        self.assertEqual(len(game.apples), 1)
        self.assertNotIn((11, 10), game.apples)

    def test_reverse_turns_are_ignored(self) -> None:
        game = Game(GameOptions(grid_size=32), seed=5)
        snake = game.snakes[0]
        snake.body = [(10, 10), (9, 10), (8, 10), (7, 10)]
        snake.direction = RIGHT
        game.apples = [(0, 0)]

        game.turn(0, LEFT)
        self.assertEqual(len(snake.pending), 0)

        game.turn(0, UP)
        self.assertEqual(len(snake.pending), 1)
        game.step()
        self.assertEqual(snake.body[0], (10, 9))

    def test_self_collision_ends_the_game(self) -> None:
        game = Game(GameOptions(grid_size=32), seed=5)
        snake = game.snakes[0]
        snake.body = [(5, 5), (5, 6), (4, 6), (4, 5), (4, 4)]
        snake.direction = LEFT
        game.apples = [(0, 0)]

        game.step()

        self.assertTrue(game.game_over)
        self.assertEqual(game.death_reasons[0], DEATH_SELF)

    def test_head_on_collision_ends_the_game(self) -> None:
        game = Game(GameOptions(grid_size=32), players=2, seed=5)
        first, second = game.snakes
        first.body = [(10, 10), (9, 10), (8, 10), (7, 10)]
        first.direction = RIGHT
        second.body = [(12, 10), (13, 10), (14, 10), (15, 10)]
        second.direction = LEFT
        game.apples = [(0, 0), (31, 31)]

        game.step()

        self.assertTrue(game.game_over)
        self.assertEqual(game.dead_players, [0, 1])
        self.assertEqual(game.death_reasons[0], DEATH_CRASH)
        self.assertEqual(game.death_reasons[1], DEATH_CRASH)
        self.assertFalse(first.alive)
        self.assertFalse(second.alive)

    def test_dead_players_identifies_the_colliding_snake(self) -> None:
        game = Game(GameOptions(grid_size=32), players=2, seed=5)
        first, second = game.snakes
        first.body = [(5, 5), (5, 6), (4, 6), (4, 5), (4, 4)]
        first.direction = LEFT
        second.body = [(20, 20), (19, 20), (18, 20), (17, 20)]
        second.direction = RIGHT
        game.apples = [(0, 0), (31, 31)]

        game.step()

        self.assertTrue(game.game_over)
        self.assertEqual(game.dead_players, [0])
        self.assertFalse(first.alive)
        self.assertTrue(second.alive)

    def test_turn_queue_does_not_overflow_into_a_reverse(self) -> None:
        game = Game(GameOptions(grid_size=32), seed=5)
        snake = game.snakes[0]
        snake.body = [(10, 10), (9, 10), (8, 10), (7, 10)]
        snake.direction = RIGHT
        game.apples = [(0, 0)]

        game.turn(0, UP)
        game.turn(0, LEFT)
        # The queue is full; this must not push a 180 degree turn to the
        # front by evicting the first queued turn.
        game.turn(0, DOWN)
        self.assertEqual(list(snake.pending), [UP, LEFT])

        game.step()
        self.assertEqual(snake.body[0], (10, 9))
        game.step()
        self.assertEqual(snake.body[0], (9, 9))
        self.assertFalse(game.game_over)

    def test_score_text(self) -> None:
        single = Game(GameOptions(), players=1, seed=1)
        single.snakes[0].score = 7
        self.assertEqual(single.score_text(), "Score: 7")

        multi = Game(GameOptions(), players=2, seed=1)
        multi.snakes[0].score = 3
        multi.snakes[1].score = 5
        self.assertEqual(multi.score_text(), "3 × 5")


class AppleSpawnTests(unittest.TestCase):
    @staticmethod
    def _wall_neighbors(game: Game, cell: tuple[int, int]) -> int:
        x, y = cell
        return sum(
            (x + dx, y + dy) in game.walls for dx, dy in DIRECTIONS
        )

    def _game_with_only_these_free_cells(
        self, free_cells: set[tuple[int, int]]
    ) -> Game:
        size = 16
        game = Game(GameOptions(grid_size=size), players=1, seed=1)
        game.apples = []
        game.walls = {(4, 5), (5, 4), (6, 5)}
        game.snakes[0].body = [
            (x, y)
            for y in range(size)
            for x in range(size)
            if (x, y) not in free_cells
        ]
        return game

    def test_apple_is_not_placed_in_a_three_wall_pocket(self) -> None:
        unsafe = (5, 5)
        safe = (10, 10)
        game = self._game_with_only_these_free_cells({unsafe, safe})

        self.assertGreaterEqual(self._wall_neighbors(game, unsafe), 3)
        self.assertTrue(game._spawn_apple(min_head_distance=0))

        self.assertEqual(game.apples, [safe])

    def test_no_apple_is_spawned_when_only_wall_pockets_remain(self) -> None:
        game = self._game_with_only_these_free_cells({(5, 5)})

        self.assertFalse(game._spawn_apple(min_head_distance=0))
        self.assertEqual(game.apples, [])

    def test_initial_apples_avoid_wall_pockets(self) -> None:
        # These seeds previously placed an apple in a pocket with three
        # adjacent walls.
        for size, seed in ((16, 539), (32, 932), (64, 99)):
            game = Game(
                GameOptions(grid_size=size, wall_generation=True),
                players=2,
                seed=seed,
            )
            for apple in game.apples:
                self.assertLessEqual(
                    self._wall_neighbors(game, apple),
                    2,
                    f"unsafe apple at {apple} on a {size}x{size} board",
                )


class WallGenerationTests(unittest.TestCase):
    def test_small_multiplayer_walls_vary(self) -> None:
        # With a two-cell spawn margin the 16x16 two-player board had only
        # one possible row of walls, so every game looked identical.
        layouts = {
            tuple(
                sorted(
                    Game(
                        GameOptions(grid_size=16, wall_generation=True),
                        players=2,
                        seed=seed,
                    ).walls
                )
            )
            for seed in range(10)
        }
        self.assertGreater(len(layouts), 1)

    def test_walls_are_quad_symmetric(self) -> None:
        size = 32
        game = Game(
            GameOptions(grid_size=size, wall_generation=True),
            players=2,
            seed=11,
        )

        self.assertTrue(game.walls)
        for x, y in game.walls:
            mirrors = {
                (x, y),
                (size - 1 - x, y),
                (x, size - 1 - y),
                (size - 1 - x, size - 1 - y),
            }
            self.assertTrue(mirrors <= game.walls)

    def test_walls_are_generated_away_from_spawns(self) -> None:
        game = Game(
            GameOptions(grid_size=64, wall_generation=True),
            players=2,
            seed=13,
        )

        for snake in game.snakes:
            self.assertFalse(set(snake.body) & game.walls)

    def test_walls_do_not_grow_forever(self) -> None:
        # Regression guard for the random walk loop.
        for size in (32, 64, 128):
            game = Game(
                GameOptions(grid_size=size, wall_generation=True),
                players=2,
                seed=size,
            )
            self.assertLess(len(game.walls), size * size // 4)


if __name__ == "__main__":
    unittest.main()
