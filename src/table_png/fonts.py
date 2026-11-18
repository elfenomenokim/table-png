"""Font discovery and glyph coverage for the platforms this tool runs on.

The renderer needs two things from a font: Korean (CJK) glyphs and, when the
table contains emoji, a colour emoji font. Nothing is bundled; every path here
is a font the operating system already ships, and the first one that loads
wins. `--font` / `TABLE_PNG_FONT` and `--emoji-font` / `TABLE_PNG_EMOJI_FONT`
skip the search.
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

FONT_ENV = "TABLE_PNG_FONT"
EMOJI_FONT_ENV = "TABLE_PNG_EMOJI_FONT"

BASE_FONT_SIZE = 30
EMOJI_FONT_SIZE = 160
EMOJI_FALLBACK = "◻"

# (path, regular face index, bold face index): a collection can carry both.
MACOS_TEXT_FONTS = (
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0, 6),
    ("/System/Library/Fonts/PingFang.ttc", 0, 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0, 0),
)
LINUX_TEXT_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
)
WINDOWS_TEXT_FONTS = (
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\YuGothM.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
)

MACOS_EMOJI_FONTS = ("/System/Library/Fonts/Apple Color Emoji.ttc",)
LINUX_EMOJI_FONTS = (
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto-emoji/NotoColorEmoji.ttf",
    "/usr/share/fonts/google-noto-emoji/NotoColorEmoji.ttf",
)
WINDOWS_EMOJI_FONTS = (r"C:\Windows\Fonts\seguiemj.ttf",)

MACOS_SYMBOL_FONTS = (
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)
LINUX_SYMBOL_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
)
WINDOWS_SYMBOL_FONTS = (
    r"C:\Windows\Fonts\seguisym.ttf",
    r"C:\Windows\Fonts\arial.ttf",
)

# Some bitmap-only emoji fonts accept one strike size only.
_EMOJI_SIZES = (EMOJI_FONT_SIZE, 136, 128, 109, 96, 64, 32)

_EMOJI_OVERRIDE: str | None = None


class FontError(ValueError):
    """No usable font was found on this machine."""


def _is_windows() -> bool:
    return os.name == "nt"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _fc_match(pattern: str, requires: tuple[int, ...] = ()) -> str | None:
    """Ask fontconfig for a file, when fontconfig is installed.

    fontconfig always answers with some font, so `requires` names codepoints the
    match must actually map; otherwise the answer is discarded.
    """
    binary = shutil.which("fc-match")
    if not binary:
        return None
    import subprocess

    try:
        completed = subprocess.run(
            [binary, "-f", "%{file}", pattern],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = completed.stdout.strip()
    if completed.returncode != 0 or not path or not Path(path).is_file():
        return None
    if requires:
        mapped = font_cmap(path, 0)
        if not all(codepoint in mapped for codepoint in requires):
            return None
    return path


def _bold_sibling(path: str) -> str | None:
    """Return the bold file next to a regular one, when the family has one."""
    stem, suffix = os.path.splitext(path)
    names = []
    if "Regular" in stem:
        names.append(stem.replace("Regular", "Bold") + suffix)
    if path.endswith("malgun.ttf"):
        names.append(path[: -len("malgun.ttf")] + "malgunbd.ttf")
    if path.endswith("NanumGothic.ttf"):
        names.append(path[: -len("NanumGothic.ttf")] + "NanumGothicBold.ttf")
    for name in names:
        if Path(name).is_file():
            return name
    return None


def text_font_candidates(override: str | None = None) -> list[tuple[str, int, int]]:
    """Ordered (path, regular index, bold index) candidates for this machine."""
    candidates: list[tuple[str, int, int]] = []
    if override:
        candidates.append((override, 0, 0))
    if _is_macos():
        candidates.extend(MACOS_TEXT_FONTS)
        candidates.extend((path, 0, 0) for path in LINUX_TEXT_FONTS)
        candidates.extend((path, 0, 0) for path in WINDOWS_TEXT_FONTS)
    elif _is_windows():
        candidates.extend((path, 0, 0) for path in WINDOWS_TEXT_FONTS)
        candidates.extend(MACOS_TEXT_FONTS)
        candidates.extend((path, 0, 0) for path in LINUX_TEXT_FONTS)
    else:
        candidates.extend((path, 0, 0) for path in LINUX_TEXT_FONTS)
        found = _fc_match("sans-serif:lang=ko", requires=(0xAC00,))
        if found is None:
            found = _fc_match("Noto Sans CJK KR", requires=(0xAC00,))
        if found:
            candidates.append((found, 0, 0))
        candidates.extend(MACOS_TEXT_FONTS)
        candidates.extend((path, 0, 0) for path in WINDOWS_TEXT_FONTS)
    return candidates


def _try_font(path: str, size: int, index: int) -> ImageFont.FreeTypeFont | None:
    if not Path(path).is_file():
        return None
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return None


def load_fonts(
    font_size: int = BASE_FONT_SIZE, override: str | None = None
) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Return (regular, bold, title) fonts, or raise FontError."""
    override = override or os.environ.get(FONT_ENV) or None
    if override and not Path(override).is_file():
        raise FontError(
            f"font file not found: {override}; pass --font with an existing "
            f"CJK-capable font, or unset {FONT_ENV}"
        )
    title_size = max(font_size + 2, round(font_size * 1.4))
    for path, regular_index, bold_index in text_font_candidates(override):
        regular = _try_font(path, font_size, regular_index)
        if regular is None:
            continue
        bold_path = _bold_sibling(path) or path
        bold = (
            _try_font(bold_path, font_size, bold_index)
            or _try_font(path, font_size, bold_index)
            or regular
        )
        title = (
            _try_font(bold_path, title_size, bold_index)
            or _try_font(path, title_size, bold_index)
            or bold
        )
        return regular, bold, title
    raise FontError(
        "no CJK-capable font found on this system; install one "
        "(for example fonts-noto-cjk) or pass --font /path/to/font.ttf "
        f"(or set {FONT_ENV})"
    )



@lru_cache(maxsize=32)
def is_colour_font(path: str) -> bool:
    """True when the font carries colour glyphs (CBDT, sbix or COLR); monochrome fonts such as
    DejaVu Sans map a few emoji codepoints but draw them as outlines and miss most of them."""
    try:
        data = Path(path).read_bytes()
        face = _sfnt_face_offset(data, 0)
    except (OSError, ValueError, IndexError):
        return False
    for tag in (b"CBDT", b"sbix", b"COLR"):
        try:
            _sfnt_table(data, face, tag)
            return True
        except (ValueError, IndexError):
            continue
    return False

def emoji_font_candidates(override: str | None = None) -> list[str]:
    if override is not None:
        return [override]
    if _is_macos():
        return list(MACOS_EMOJI_FONTS) + list(LINUX_EMOJI_FONTS) + list(WINDOWS_EMOJI_FONTS)
    if _is_windows():
        return list(WINDOWS_EMOJI_FONTS) + list(MACOS_EMOJI_FONTS) + list(LINUX_EMOJI_FONTS)
    found = _fc_match("Noto Color Emoji", requires=(0x1F600,))
    if found is None:
        found = _fc_match("emoji", requires=(0x1F600,))
    paths = list(LINUX_EMOJI_FONTS)
    if found:
        paths.insert(0, found)
    return paths + list(MACOS_EMOJI_FONTS) + list(WINDOWS_EMOJI_FONTS)


@lru_cache(maxsize=8)
def _load_emoji_font_for(override: str | None) -> ImageFont.FreeTypeFont | None:
    if override and not Path(override).is_file():
        # A missing emoji font is not fatal: the table still renders, without
        # colour emoji. Say so once instead of silently ignoring the request.
        print(
            f"table-png: emoji font not found: {override}; "
            "rendering emoji as monochrome glyphs",
            file=sys.stderr,
        )
    for path in emoji_font_candidates(override):
        if not path or not Path(path).is_file():
            continue
        if path != override and not is_colour_font(path):
            continue  # an explicit --emoji-font is trusted; discovered fonts must be colour fonts
        for size in _EMOJI_SIZES:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def set_emoji_font_override(path: str | None) -> None:
    """Force one emoji font for this process (used by --emoji-font)."""
    global _EMOJI_OVERRIDE
    _EMOJI_OVERRIDE = path or None


def emoji_font_override() -> str | None:
    return _EMOJI_OVERRIDE


def load_emoji_font(override: str | None = None) -> ImageFont.FreeTypeFont | None:
    """Return a colour emoji font, or None when this machine has none."""
    if override is None:
        override = _EMOJI_OVERRIDE or os.environ.get(EMOJI_FONT_ENV, "") or None
    return _load_emoji_font_for(override)


def symbol_font_paths() -> tuple[str, ...]:
    if _is_macos():
        return MACOS_SYMBOL_FONTS + LINUX_SYMBOL_FONTS + WINDOWS_SYMBOL_FONTS
    if _is_windows():
        return WINDOWS_SYMBOL_FONTS + MACOS_SYMBOL_FONTS + LINUX_SYMBOL_FONTS
    return LINUX_SYMBOL_FONTS + MACOS_SYMBOL_FONTS + WINDOWS_SYMBOL_FONTS


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _sfnt_face_offset(data: bytes, index: int) -> int:
    if data[:4] != b"ttcf":
        if index != 0:
            raise ValueError("font face index is outside a non-collection font")
        return 0
    count = _u32(data, 8)
    if index < 0 or index >= count:
        raise ValueError("font face index is outside the collection")
    return _u32(data, 12 + index * 4)


def _sfnt_table(data: bytes, face_offset: int, tag: bytes) -> tuple[int, int]:
    table_count = _u16(data, face_offset + 4)
    for record in range(table_count):
        offset = face_offset + 12 + record * 16
        if data[offset : offset + 4] == tag:
            table_offset = _u32(data, offset + 8)
            table_length = _u32(data, offset + 12)
            if table_offset + table_length > len(data):
                raise ValueError("font table extends beyond the file")
            return table_offset, table_length
    raise ValueError(f"font has no {tag.decode()} table")


def _cmap_format_4(data: bytes, offset: int, limit: int) -> set[int]:
    length = _u16(data, offset + 2)
    table_end = min(limit, offset + length)
    segment_count = _u16(data, offset + 6) // 2
    end_codes = offset + 14
    start_codes = end_codes + 2 * segment_count + 2
    deltas = start_codes + 2 * segment_count
    range_offsets = deltas + 2 * segment_count
    mapped: set[int] = set()
    for segment in range(segment_count):
        start = _u16(data, start_codes + 2 * segment)
        end = _u16(data, end_codes + 2 * segment)
        delta = _u16(data, deltas + 2 * segment)
        range_offset_position = range_offsets + 2 * segment
        range_offset = _u16(data, range_offset_position)
        for codepoint in range(start, min(end, 0xFFFE) + 1):
            if range_offset == 0:
                glyph = (codepoint + delta) & 0xFFFF
            else:
                glyph_position = (
                    range_offset_position + range_offset + 2 * (codepoint - start)
                )
                if glyph_position + 2 > table_end:
                    continue
                glyph = _u16(data, glyph_position)
                if glyph:
                    glyph = (glyph + delta) & 0xFFFF
            if glyph:
                mapped.add(codepoint)
    return mapped


def _cmap_format_12_or_13(data: bytes, offset: int, limit: int) -> set[int]:
    format_number = _u16(data, offset)
    length = _u32(data, offset + 4)
    table_end = min(limit, offset + length)
    group_count = _u32(data, offset + 12)
    mapped: set[int] = set()
    for group in range(group_count):
        group_offset = offset + 16 + group * 12
        if group_offset + 12 > table_end:
            break
        start = _u32(data, group_offset)
        end = min(_u32(data, group_offset + 4), 0x10FFFF)
        glyph = _u32(data, group_offset + 8)
        if format_number == 13:
            if glyph:
                mapped.update(range(start, end + 1))
        else:
            first = start + 1 if glyph == 0 else start
            if first <= end:
                mapped.update(range(first, end + 1))
    return mapped


@lru_cache(maxsize=16)
def font_cmap(path: str, index: int) -> frozenset[int]:
    """Codepoints a font actually maps, read from its cmap table."""
    try:
        data = Path(path).read_bytes()
        face_offset = _sfnt_face_offset(data, index)
        cmap_offset, cmap_length = _sfnt_table(data, face_offset, b"cmap")
        cmap_limit = cmap_offset + cmap_length
        record_count = _u16(data, cmap_offset + 2)
        mapped: set[int] = set()
        seen: set[int] = set()
        for record in range(record_count):
            record_offset = cmap_offset + 4 + record * 8
            platform = _u16(data, record_offset)
            if platform not in (0, 3):
                continue
            subtable_offset = cmap_offset + _u32(data, record_offset + 4)
            if subtable_offset in seen or subtable_offset + 2 > cmap_limit:
                continue
            seen.add(subtable_offset)
            format_number = _u16(data, subtable_offset)
            if format_number == 4:
                mapped.update(_cmap_format_4(data, subtable_offset, cmap_limit))
            elif format_number in (12, 13):
                mapped.update(_cmap_format_12_or_13(data, subtable_offset, cmap_limit))
        return frozenset(mapped)
    except (OSError, ValueError, struct.error):
        return frozenset()


def font_codepoints(font: ImageFont.ImageFont) -> frozenset[int]:
    path = getattr(font, "path", "")
    index = int(getattr(font, "index", 0))
    return font_cmap(str(path), index) if path else frozenset()


@lru_cache(maxsize=8)
def fallback_text_fonts(size: int) -> tuple[ImageFont.FreeTypeFont, ...]:
    """Symbol-capable text fonts used when the main font lacks a glyph."""
    loaded: list[ImageFont.FreeTypeFont] = []
    seen: set[str] = set()
    # Other installed CJK fonts first (the main font may lack kana or rare hanzi), then symbol fonts.
    paths = [path for path, _, _ in text_font_candidates(None)]
    if not _is_macos() and not _is_windows():
        for pattern, probe in (("sans-serif:lang=ja", 0x30FB), ("sans-serif:lang=zh-cn", 0x4E2D)):
            found = _fc_match(pattern, requires=(probe,))
            if found:
                paths.insert(0, found)
    paths += list(symbol_font_paths())
    for path in paths:
        if path in seen or len(loaded) >= 6:
            continue
        seen.add(path)
        font = _try_font(path, size, 0)
        if font is not None:
            loaded.append(font)
    return tuple(loaded)
