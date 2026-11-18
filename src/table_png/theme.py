"""Colour palettes. Light is the default; dark stays readable on a phone."""

from __future__ import annotations


class Theme:
    __slots__ = (
        "name",
        "background",
        "header_fill",
        "zebra_fill",
        "grid",
        "header_text",
        "body_text",
    )

    def __init__(
        self,
        name: str,
        background: tuple[int, int, int],
        header_fill: tuple[int, int, int],
        zebra_fill: tuple[int, int, int],
        grid: tuple[int, int, int],
        header_text: tuple[int, int, int],
        body_text: tuple[int, int, int],
    ) -> None:
        self.name = name
        self.background = background
        self.header_fill = header_fill
        self.zebra_fill = zebra_fill
        self.grid = grid
        self.header_text = header_text
        self.body_text = body_text

    def __repr__(self) -> str:
        return f"Theme({self.name!r})"


LIGHT = Theme(
    name="light",
    background=(255, 255, 255),
    header_fill=(241, 245, 249),
    zebra_fill=(248, 250, 252),
    grid=(203, 210, 218),
    header_text=(30, 41, 59),
    body_text=(71, 85, 105),
)

DARK = Theme(
    name="dark",
    background=(23, 26, 33),
    header_fill=(38, 44, 56),
    zebra_fill=(30, 34, 42),
    grid=(58, 66, 80),
    header_text=(236, 240, 247),
    body_text=(205, 213, 225),
)

THEMES = {"light": LIGHT, "dark": DARK}


def get_theme(name: str) -> Theme:
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(
            f"unknown theme '{name}'; choose one of: {', '.join(THEMES)}"
        ) from None
