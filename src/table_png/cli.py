"""Command line entry point: `table-png`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .fonts import EMOJI_FONT_ENV, FONT_ENV, FontError
from .inputs import FORMATS, InputError, read_source
from .render import DEFAULT_ROWS_PER_PAGE, DEFAULT_WIDTH, RenderOptions, render_table
from .theme import THEMES


class JsonArgumentParser(argparse.ArgumentParser):
    """argparse that reports errors through the JSON contract instead of exiting."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise ValueError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog="table-png",
        description=(
            "Render a small table as a PNG image with correct Korean, Chinese and "
            "Japanese text, for places that cannot show a Markdown table."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="input file, or - for stdin (default: stdin)",
    )
    parser.add_argument(
        "--in",
        dest="input_option",
        default=None,
        metavar="PATH",
        help="input file (same as the positional argument; kept for existing scripts)",
    )
    parser.add_argument(
        "-o", "--out", required=True, help="output PNG path (pagination adds -001, -002, ...)"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        default="auto",
        help="input format (default: auto)",
    )
    parser.add_argument("--title", default="", help="heading drawn above the table")
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"image width in pixels, clamped to 720-1600 (default: {DEFAULT_WIDTH})",
    )
    parser.add_argument(
        "--font-size", type=int, default=30, help="body text size in pixels (default: 30)"
    )
    parser.add_argument(
        "--rows-per-page",
        type=int,
        default=DEFAULT_ROWS_PER_PAGE,
        help=f"rows per image before pagination (default: {DEFAULT_ROWS_PER_PAGE})",
    )
    parser.add_argument(
        "--theme",
        choices=sorted(THEMES),
        default="light",
        help="colour theme (default: light)",
    )
    parser.add_argument(
        "--font", default=None, help=f"path to a CJK-capable font (or set {FONT_ENV})"
    )
    parser.add_argument(
        "--emoji-font",
        default=None,
        help=f"path to a colour emoji font (or set {EMOJI_FONT_ENV})",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the machine-readable result object"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        source = args.input_option or args.input or "-"
        table = read_source(source, args.format)
        options = RenderOptions(
            width=args.width,
            font_size=args.font_size,
            rows_per_page=args.rows_per_page,
            theme=args.theme,
            title=args.title,
            font_path=args.font,
            emoji_font_path=args.emoji_font,
        )
        result = render_table(table, Path(args.out), options)
    except (ValueError, OSError, FontError, InputError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        pages = result["png"]
        for path in pages if isinstance(pages, list) else [pages]:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
