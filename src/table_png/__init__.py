"""Render a small table as a PNG with correct Korean, Chinese and Japanese text."""

from __future__ import annotations

__version__ = "0.1.0"

from .inputs import Table, read_source, read_table  # noqa: E402
from .render import RenderOptions, render_table  # noqa: E402
from .theme import THEMES  # noqa: E402

__all__ = [
    "RenderOptions",
    "THEMES",
    "Table",
    "__version__",
    "read_source",
    "read_table",
    "render_table",
]
