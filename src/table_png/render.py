"""Draw a table as one or more PNG pages."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .fonts import (
    BASE_FONT_SIZE,
    EMOJI_FALLBACK,
    fallback_text_fonts,
    font_codepoints,
    load_emoji_font,
    load_fonts,
    set_emoji_font_override,
)
from .inputs import Table
from .theme import Theme, get_theme

MIN_WIDTH = 720
MAX_WIDTH = 1600
DEFAULT_WIDTH = 1080
DEFAULT_ROWS_PER_PAGE = 40


class Geometry:
    """Spacing derived from the font size, so every size stays balanced."""

    __slots__ = ("font_size", "title_size", "pad_x", "pad_y", "margin", "line_gap")

    def __init__(
        self,
        font_size: int,
        title_size: int,
        pad_x: int,
        pad_y: int,
        margin: int,
        line_gap: int,
    ) -> None:
        self.font_size = font_size
        self.title_size = title_size
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.margin = margin
        self.line_gap = line_gap


def geometry_for(font_size: int) -> Geometry:
    return Geometry(
        font_size=font_size,
        title_size=max(font_size + 2, round(font_size * 1.4)),
        pad_x=round(font_size * 0.6),
        pad_y=round(font_size * 0.4),
        margin=round(font_size * 0.8),
        line_gap=round(font_size / 6),
    )


class RenderOptions:
    """Everything the caller can change about one render."""

    __slots__ = (
        "width",
        "font_size",
        "rows_per_page",
        "theme",
        "title",
        "font_path",
        "emoji_font_path",
    )

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        font_size: int = BASE_FONT_SIZE,
        rows_per_page: int = DEFAULT_ROWS_PER_PAGE,
        theme: str = "light",
        title: str = "",
        font_path: str | None = None,
        emoji_font_path: str | None = None,
    ) -> None:
        self.width = width
        self.font_size = font_size
        self.rows_per_page = rows_per_page
        self.theme = theme
        self.title = title
        self.font_path = font_path
        self.emoji_font_path = emoji_font_path


def _plain_text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _is_emoji_base(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x00A9 <= codepoint <= 0x00AE
        or codepoint in (0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299)
        or 0x2190 <= codepoint <= 0x23FF
        or 0x25A0 <= codepoint <= 0x27BF
        or 0x2934 <= codepoint <= 0x2935
        or 0x2B00 <= codepoint <= 0x2BFF
        or 0x1F000 <= codepoint <= 0x1FAFF
        or 0x1FC00 <= codepoint <= 0x1FFFD
    )


def _is_emoji_modifier(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint in (0xFE0E, 0xFE0F, 0x20E3)
        or 0x1F3FB <= codepoint <= 0x1F3FF
        or 0xE0020 <= codepoint <= 0xE007F
    )


def _may_contain_emoji(text: str) -> bool:
    return any(
        _is_emoji_base(character)
        or character == "\u200d"
        or ord(character) == 0x20E3
        for character in text
    )


@lru_cache(maxsize=2048)
def _graphemeish_clusters(text: str) -> tuple[str, ...]:
    if not _may_contain_emoji(text):
        return tuple(text)
    clusters: list[str] = []
    index = 0
    while index < len(text):
        cluster = text[index]
        index += 1
        if 0x1F1E6 <= ord(cluster) <= 0x1F1FF and index < len(text):
            if 0x1F1E6 <= ord(text[index]) <= 0x1F1FF:
                cluster += text[index]
                index += 1
        while index < len(text):
            character = text[index]
            if _is_emoji_modifier(character):
                cluster += character
                index += 1
                continue
            if character == "\u200d" and index + 1 < len(text):
                cluster += character + text[index + 1]
                index += 2
                continue
            break
        clusters.append(cluster)
    return tuple(clusters)


def _cluster_is_emoji(cluster: str) -> bool:
    return any(_is_emoji_base(character) or ord(character) == 0x20E3 for character in cluster)


@lru_cache(maxsize=2048)
def _text_runs(text: str) -> tuple[tuple[bool, str], ...]:
    if not _may_contain_emoji(text):
        return ((False, text),) if text else ()
    runs: list[tuple[bool, str]] = []
    for cluster in _graphemeish_clusters(text):
        emoji = _cluster_is_emoji(cluster)
        if not emoji and runs and not runs[-1][0]:
            runs[-1] = (False, runs[-1][1] + cluster)
        else:
            runs.append((emoji, cluster))
    return tuple(runs)


def _significant_codepoints(cluster: str) -> tuple[int, ...]:
    return tuple(
        ord(character)
        for character in cluster
        if character != "\u200d" and not _is_emoji_modifier(character)
    )


def _text_cluster(cluster: str) -> str:
    return "".join(character for character in cluster if ord(character) not in (0xFE0E, 0xFE0F))


def _font_supports(font: ImageFont.ImageFont, cluster: str) -> bool:
    codepoints = _significant_codepoints(cluster)
    cmap = font_codepoints(font)
    return bool(codepoints) and all(codepoint in cmap for codepoint in codepoints)


def _emoji_supports(cluster: str) -> bool:
    font = load_emoji_font()
    if font is None:
        return False
    codepoints = _significant_codepoints(cluster)
    return bool(codepoints) and codepoints[0] in font_codepoints(font)


def _text_font(cluster: str, primary: ImageFont.ImageFont) -> ImageFont.ImageFont | None:
    size = int(getattr(primary, "size", BASE_FONT_SIZE))
    for font in (primary, *fallback_text_fonts(size)):
        if _font_supports(font, cluster):
            return font
    return None


@lru_cache(maxsize=256)
def _emoji_asset(cluster: str, line_height: int) -> Image.Image | None:
    if not _emoji_supports(cluster):
        return None
    font = load_emoji_font()
    if font is None:
        return None
    try:
        box = font.getbbox(cluster)
        padding = 16
        width = max(1, box[2] - box[0] + 2 * padding)
        height = max(1, box[3] - box[1] + 2 * padding)
        source = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        source_draw = ImageDraw.Draw(source)
        source_draw.text(
            (padding - box[0], padding - box[1]),
            cluster,
            font=font,
            embedded_color=True,
        )
        alpha_box = source.getchannel("A").getbbox()
        if alpha_box is None:
            return None
        cropped = source.crop(alpha_box)
        target_height = max(1, line_height - max(1, line_height // 10))
        target_width = max(1, round(cropped.width * target_height / cropped.height))
        return cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
    except (OSError, ValueError):
        return None


def _append_resolved(
    runs: list[tuple[str, Any, ImageFont.ImageFont | None]],
    kind: str,
    value: Any,
    font: ImageFont.ImageFont | None,
) -> None:
    if kind == "text" and runs and runs[-1][0] == "text" and runs[-1][2] is font:
        runs[-1] = ("text", runs[-1][1] + value, font)
    else:
        runs.append((kind, value, font))



def _append_plain(
    runs: list[tuple[str, Any, ImageFont.ImageFont | None]],
    text: str,
    primary: ImageFont.ImageFont,
) -> None:
    """Plain text, with characters the main font lacks (kana in a Korean font, rare hanzi,
    symbols) drawn from the first installed font that has them."""
    cmap = font_codepoints(primary)
    for character in text:
        font: ImageFont.ImageFont | None = primary
        if not character.isspace() and ord(character) not in cmap:
            font = _text_font(character, primary) or primary
        _append_resolved(runs, "text", character, font)


_EMOJI_HINT_SHOWN = False


def _emoji_font_hint() -> None:
    global _EMOJI_HINT_SHOWN
    if _EMOJI_HINT_SHOWN:
        return
    _EMOJI_HINT_SHOWN = True
    import sys

    print(
        "table-png: no colour emoji font found; emoji are drawn as boxes. "
        "Install one (Linux: fonts-noto-color-emoji) or pass --emoji-font.",
        file=sys.stderr,
    )

def _resolved_runs(
    text: str,
    primary: ImageFont.ImageFont,
    line_height: int,
) -> tuple[tuple[str, Any, ImageFont.ImageFont | None], ...]:
    if not text:
        return ()
    cmap = font_codepoints(primary)
    if not _may_contain_emoji(text):
        if all(character.isspace() or ord(character) in cmap for character in text):
            return (("text", text, primary),)
        plain: list[tuple[str, Any, ImageFont.ImageFont | None]] = []
        _append_plain(plain, text, primary)
        return tuple(plain)
    resolved: list[tuple[str, Any, ImageFont.ImageFont | None]] = []
    for emoji, run in _text_runs(text):
        if not emoji:
            _append_plain(resolved, run, primary)
            continue
        if _emoji_supports(run):
            asset = _emoji_asset(run, line_height)
            if asset is not None:
                _append_resolved(resolved, "emoji", asset, None)
                continue
        text_value = _text_cluster(run)
        selected_font = _text_font(text_value, primary)
        if selected_font is None:
            if load_emoji_font() is None:
                _emoji_font_hint()
            _append_resolved(resolved, "fallback", EMOJI_FALLBACK, primary)
        else:
            _append_resolved(resolved, "text", text_value, selected_font)
    return tuple(resolved)


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    line_height: int,
) -> int:
    width = 0
    for kind, value, selected_font in _resolved_runs(text, font, line_height):
        if kind == "emoji":
            width += value.width
        else:
            width += _plain_text_width(draw, value, selected_font or font)
    return width


def _draw_text(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_height: int,
) -> None:
    x, y = position
    for kind, value, selected_font in _resolved_runs(text, font, line_height):
        if kind == "emoji":
            image.paste(value, (x, y + max(0, (line_height - value.height) // 2)), value)
            x += value.width
            continue
        run_font = selected_font or font
        draw.text((x, y), value, font=run_font, fill=fill)
        x += _plain_text_width(draw, value, run_font)


def _hard_chunks(text: str, limit: int = 400) -> list[str]:
    """Split on explicit newlines, and cap pathological runs so wrapping terminates."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        clusters = _graphemeish_clusters(paragraph)
        lines.extend("".join(clusters[pos : pos + limit]) for pos in range(0, len(clusters), limit))
    return lines or [""]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    line_height: int,
) -> list[str]:
    wrapped: list[str] = []
    for chunk in _hard_chunks(text):
        remaining = list(_graphemeish_clusters(chunk))
        if not remaining:
            wrapped.append("")
            continue
        while remaining:
            low, high, best = 1, len(remaining), 1
            while low <= high:
                mid = (low + high) // 2
                if _text_width(draw, "".join(remaining[:mid]), font, line_height) <= max_width:
                    best = mid
                    low = mid + 1
                else:
                    high = mid - 1
            split_at = best
            if best < len(remaining):
                whitespace = max(
                    (index for index, value in enumerate(remaining[:best]) if value.isspace()),
                    default=-1,
                )
                if whitespace >= max(1, best // 2):
                    split_at = whitespace
            line = "".join(remaining[:split_at]).rstrip()
            wrapped.append(line or "".join(remaining[:best]))
            remaining = remaining[split_at:]
            while remaining and remaining[0].isspace():
                remaining.pop(0)
    return wrapped or [""]


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, gap: int) -> int:
    box = draw.textbbox((0, 0), "가Ag", font=font)
    return box[3] - box[1] + gap


def _column_widths(
    draw: ImageDraw.ImageDraw,
    headers: list[str],
    rows: list[list[str]],
    regular: ImageFont.ImageFont,
    bold: ImageFont.ImageFont,
    canvas_width: int,
    geometry: Geometry,
) -> list[int]:
    available = canvas_width - 2 * geometry.margin
    count = len(headers)
    regular_line = _line_height(draw, regular, geometry.line_gap)
    bold_line = _line_height(draw, bold, geometry.line_gap)
    floor = min(110, max(36, available // max(1, count * 2)))
    demand: list[int] = []
    for column, header in enumerate(headers):
        samples = [(header, bold)] + [(row[column], regular) for row in rows]
        widest = max(
            (
                _text_width(draw, part, font, bold_line if font is bold else regular_line)
                for text, font in samples
                for part in _hard_chunks(text)
            ),
            default=0,
        )
        demand.append(max(floor, widest + 2 * geometry.pad_x))

    # A column first gets what its widest unbreakable word needs, up to an equal
    # share of the canvas, so a short column never wraps by a few pixels. What
    # is left over goes to the columns whose content still does not fit.
    share = max(floor, available // count)
    base = [min(value, share) for value in demand]
    if sum(base) >= available:
        widths = [available // count] * count
    else:
        extra = available - sum(base)
        weights = [max(1, value - start) for value, start in zip(demand, base)]
        weight_total = sum(weights)
        widths = [
            start + (extra * weight // weight_total)
            for start, weight in zip(base, weights)
        ]
    widths[-1] += available - sum(widths)
    return widths


def _page_path(output: Path, page: int, page_count: int) -> Path:
    if page_count == 1:
        return output
    suffix = output.suffix or ".png"
    return output.with_name(f"{output.stem}-{page:03d}{suffix}")


def _render_page(
    output: Path,
    title: str,
    table: Table,
    theme: Theme,
    width: int,
    fonts: tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont],
    geometry: Geometry,
) -> int:
    regular, bold, title_font = fonts
    measure_image = Image.new("RGB", (width, 32), theme.background)
    measure = ImageDraw.Draw(measure_image)
    col_widths = _column_widths(
        measure, table.headers, table.rows, regular, bold, width, geometry
    )
    regular_line = _line_height(measure, regular, geometry.line_gap)
    bold_line = _line_height(measure, bold, geometry.line_gap)
    header_lines = [
        _wrap_text(
            measure,
            value,
            bold,
            max(1, col_widths[index] - 2 * geometry.pad_x),
            bold_line,
        )
        for index, value in enumerate(table.headers)
    ]
    body_lines = [
        [
            _wrap_text(
                measure,
                value,
                regular,
                max(1, col_widths[index] - 2 * geometry.pad_x),
                regular_line,
            )
            for index, value in enumerate(row)
        ]
        for row in table.rows
    ]
    header_height = max(len(lines) for lines in header_lines) * bold_line + 2 * geometry.pad_y
    row_heights = [
        max(len(lines) for lines in row) * regular_line + 2 * geometry.pad_y
        for row in body_lines
    ]
    title_height = 0
    title_line = 0
    if title:
        title_line = _line_height(measure, title_font, geometry.line_gap)
        title_height = title_line + round(geometry.font_size * 0.6)
    height = 2 * geometry.margin + title_height + header_height + sum(row_heights)

    image = Image.new("RGB", (width, height), theme.background)
    draw = ImageDraw.Draw(image)
    y = geometry.margin
    if title:
        _draw_text(
            image,
            draw,
            (geometry.margin, y),
            title,
            title_font,
            theme.header_text,
            title_line,
        )
        y += title_height

    def draw_row(
        lines_by_cell: list[list[str]],
        row_height: int,
        fill: tuple[int, int, int],
        font: ImageFont.ImageFont,
        line_height: int,
        header: bool = False,
    ) -> None:
        nonlocal y
        x = geometry.margin
        for column, lines in enumerate(lines_by_cell):
            cell_width = col_widths[column]
            draw.rectangle(
                (x, y, x + cell_width, y + row_height),
                fill=fill,
                outline=theme.grid,
                width=1,
            )
            for line_index, line in enumerate(lines):
                text_width = _text_width(draw, line, font, line_height)
                cell_align = "c" if header else table.align[column]
                if cell_align == "r":
                    text_x = x + cell_width - geometry.pad_x - text_width
                elif cell_align == "c":
                    text_x = x + (cell_width - text_width) // 2
                else:
                    text_x = x + geometry.pad_x
                text_y = y + geometry.pad_y + line_index * line_height
                _draw_text(
                    image,
                    draw,
                    (text_x, text_y),
                    line,
                    font,
                    theme.header_text if header else theme.body_text,
                    line_height,
                )
            x += cell_width
        y += row_height

    draw_row(header_lines, header_height, theme.header_fill, bold, bold_line, header=True)
    for index, lines_by_cell in enumerate(body_lines):
        draw_row(
            lines_by_cell,
            row_heights[index],
            theme.zebra_fill if index % 2 else theme.background,
            regular,
            regular_line,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=False)
    return height


def clamp_width(width: int) -> int:
    return max(MIN_WIDTH, min(MAX_WIDTH, width))


def render_table(
    table: Table,
    output_path: Path,
    options: RenderOptions | None = None,
) -> dict[str, Any]:
    """Render every page and return the JSON result contract."""
    options = options or RenderOptions()
    set_emoji_font_override(options.emoji_font_path)
    _emoji_asset.cache_clear()
    theme = get_theme(options.theme)
    width = clamp_width(options.width)
    font_size = max(8, options.font_size)
    rows_per_page = max(1, options.rows_per_page)
    geometry = geometry_for(font_size)
    fonts = load_fonts(font_size, options.font_path)
    output_path = Path(output_path).expanduser().resolve()
    rows = table.rows
    pages = [
        Table(table.headers, rows[index : index + rows_per_page], table.align)
        for index in range(0, len(rows), rows_per_page)
    ] or [Table(table.headers, [], table.align)]
    page_count = len(pages)
    paths: list[str] = []
    heights: list[int] = []
    for page_number, page in enumerate(pages, start=1):
        page_path = _page_path(output_path, page_number, page_count)
        page_title = options.title
        if page_title and page_count > 1:
            page_title = f"{page_title} ({page_number}/{page_count})"
        height = _render_page(page_path, page_title, page, theme, width, fonts, geometry)
        paths.append(str(page_path))
        heights.append(height)
    return {
        "ok": True,
        "png": paths[0] if page_count == 1 else paths,
        "width": width,
        "height": heights[0] if page_count == 1 else heights,
        "rows": len(rows),
    }


def colour_emoji_available() -> bool:
    """True when a colour emoji font loaded and Pillow draws it in colour."""
    font = load_emoji_font()
    if font is None:
        return False
    try:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(image).text((0, 0), "😀", font=font, embedded_color=True)
    except (OSError, ValueError):
        return False
    colours = {
        pixel[:3]
        for pixel in image.getdata()
        if pixel[3] > 0 and max(pixel[:3]) - min(pixel[:3]) >= 70
    }
    return len(colours) >= 5


__all__ = [
    "DEFAULT_ROWS_PER_PAGE",
    "DEFAULT_WIDTH",
    "Geometry",
    "MAX_WIDTH",
    "MIN_WIDTH",
    "RenderOptions",
    "clamp_width",
    "colour_emoji_available",
    "geometry_for",
    "render_table",
]
