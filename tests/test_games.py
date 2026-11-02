"""The game library — what an installation is made of.

The DLC, the mods, the saves and the screenshots of a game are measured
apart from the game files, so the space each of them takes is known.
"""

from __future__ import annotations

from pathlib import Path

from diskgoup.core.games import (
    CATEGORY_DLC,
    CATEGORY_GAME_FILES,
    CATEGORY_MODS,
    CATEGORY_SAVES,
    CATEGORY_SCREENSHOTS,
    _measure_game,
)


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


def test_the_categories_of_a_game_are_measured_apart(tmp_path: Path) -> None:
    install = tmp_path / "Elden Ring"
    _write(install / "game.bin", 100)
    _write(install / "dlc" / "pack.bin", 200)
    _write(install / "mods" / "mod.bin", 300)
    _write(install / "saved games" / "save.bin", 400)
    _write(install / "screenshots" / "shot.png", 500)

    game = _measure_game("Elden Ring", "Steam", install, "1245620")

    sizes = {name: entry.size for name, entry in game.categories.items()}
    assert sizes[CATEGORY_GAME_FILES] == 100
    assert sizes[CATEGORY_DLC] == 200
    assert sizes[CATEGORY_MODS] == 300
    assert sizes[CATEGORY_SAVES] == 400
    assert sizes[CATEGORY_SCREENSHOTS] == 500


def test_the_categories_add_up_to_the_whole_game(tmp_path: Path) -> None:
    install = tmp_path / "Hades"
    _write(install / "game.bin", 100)
    _write(install / "dlc" / "pack.bin", 200)

    game = _measure_game("Hades", "Steam", install, "1145360")

    assert sum(entry.size for entry in game.categories.values()) == game.size
    assert sum(entry.files for entry in game.categories.values()) == game.files


def test_the_saves_and_the_dlc_are_protected(tmp_path: Path) -> None:
    install = tmp_path / "Stardew Valley"
    _write(install / "game.bin", 100)
    _write(install / "dlc" / "pack.bin", 150)
    _write(install / "saves" / "save.bin", 200)
    _write(install / "mods" / "mod.bin", 300)

    game = _measure_game("Stardew Valley", "Steam", install, "413150")

    assert game.categories[CATEGORY_SAVES].protected is True
    assert game.categories[CATEGORY_DLC].protected is True
    assert game.categories[CATEGORY_MODS].protected is False
