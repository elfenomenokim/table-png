"""Read a table from JSON, a Markdown pipe table, or CSV.

Every format ends up as the same `Table` value, so the renderer never needs to
know where the cells came from.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

FORMATS = ("auto", "json", "markdown", "csv")

_DELIMITER_ROW = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")
_ALIGNMENT_CELL = re.compile(r"^\s*(:?)-+(:?)\s*$")


class Table:
    """Headers, rows and per-column alignment, already plain text."""

    __slots__ = ("headers", "rows", "align")

    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        align: list[str] | None = None,
    ) -> None:
        self.headers = headers
        self.rows = rows
        self.align = align if align else ["l"] * len(headers)

    def __repr__(self) -> str:
        return f"Table({len(self.headers)} columns, {len(self.rows)} rows)"


class InputError(ValueError):
    """The input could not be read as a table."""


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    raise InputError("cells must be strings, numbers, booleans, or null")


def table_from_payload(payload: Any) -> Table:
    """Validate the JSON schema {"headers": [...], "rows": [[...]], "align": [...]}."""
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    headers_raw = payload.get("headers")
    rows_raw = payload.get("rows")
    if not isinstance(headers_raw, list) or not headers_raw:
        raise InputError("headers must be a non-empty array")
    if not isinstance(rows_raw, list):
        raise InputError("rows must be an array")

    headers = [cell_text(value) for value in headers_raw]
    rows: list[list[str]] = []
    for index, row in enumerate(rows_raw):
        if not isinstance(row, list) or len(row) != len(headers):
            raise InputError(f"row {index + 1} must contain {len(headers)} cells")
        rows.append([cell_text(value) for value in row])

    align_raw = payload.get("align")
    if align_raw is None:
        return Table(headers, rows)
    if not isinstance(align_raw, list) or len(align_raw) != len(headers):
        raise InputError("align must contain one entry per header")
    align: list[str] = []
    for value in align_raw:
        if value not in ("l", "c", "r"):
            raise InputError("align entries must be l, c, or r")
        align.append(value)
    return Table(headers, rows, align)


def _split_pipe_row(line: str) -> list[str]:
    """Split one GFM row on unescaped pipes, keeping escaped ones literal."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text) and text[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if character == "|":
            cells.append("".join(current))
            current = []
            index += 1
            continue
        current.append(character)
        index += 1
    cells.append("".join(current))
    return [cell.strip() for cell in cells]


def _strip_inline_markup(text: str) -> str:
    """Drop the Markdown that cannot render inside a PNG cell."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    return text.strip()


def _markdown_align(cell: str) -> str:
    match = _ALIGNMENT_CELL.match(cell)
    if not match:
        return "l"
    left, right = match.group(1) == ":", match.group(2) == ":"
    if left and right:
        return "c"
    if right:
        return "r"
    return "l"


def _find_markdown_table(lines: list[str]) -> int | None:
    """Index of the first header line that is followed by a |---| delimiter row, outside code fences."""
    fence = False
    for index, line in enumerate(lines[:-1]):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence or "|" not in line:
            continue
        nxt = lines[index + 1]
        if "|" in nxt and _DELIMITER_ROW.match(nxt):
            return index
    return None


def looks_like_markdown(text: str) -> bool:
    return _find_markdown_table(text.splitlines()) is not None


def table_from_markdown(text: str) -> Table:
    """Read the first pipe table in the text; prose, headings and later tables are ignored."""
    lines = text.splitlines()
    start = _find_markdown_table(lines)
    if start is None:
        raise InputError("no Markdown table found (a header row followed by a |---|---| delimiter row)")
    headers = [_strip_inline_markup(cell) for cell in _split_pipe_row(lines[start])]
    align = [_markdown_align(cell) for cell in _split_pipe_row(lines[start + 1])]
    if len(align) != len(headers):
        raise InputError("the delimiter row must have one cell per header")
    rows: list[list[str]] = []
    for number, line in enumerate(lines[start + 2:], start=start + 3):
        if not line.strip() or "|" not in line:
            break  # a blank or pipe-less line ends the table (GFM)
        cells = [_strip_inline_markup(cell) for cell in _split_pipe_row(line)]
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        if len(cells) > len(headers):
            raise InputError(
                f"Markdown line {number} has {len(cells)} cells but the header has {len(headers)}"
            )
        rows.append(cells)
    return Table(headers, rows, align)


def table_from_csv(text: str, delimiter: str | None = None) -> Table:
    """Parse CSV (or TSV when the first line is tab-separated)."""
    if delimiter is None:
        first_line = next((line for line in text.splitlines() if line.strip()), "")
        delimiter = "\t" if "\t" in first_line and "," not in first_line else ","
    import csv

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        records = [record for record in reader if any(cell.strip() for cell in record)]
    except csv.Error as exc:
        raise InputError(f"CSV could not be parsed: {exc}") from None
    if not records:
        raise InputError("CSV input is empty")
    headers = [cell.strip() for cell in records[0]]
    rows: list[list[str]] = []
    for number, record in enumerate(records[1:], start=2):
        cells = [cell.strip() for cell in record]
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        if len(cells) > len(headers):
            raise InputError(
                f"CSV record {number} has {len(cells)} fields but the header has {len(headers)}"
            )
        rows.append(cells)
    return Table(headers, rows)


def detect_format(text: str, name: str = "") -> str:
    """Guess the format from the content first, then the file extension."""
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
            return "json"
        except ValueError:
            pass  # e.g. Markdown that starts with a [link]
    if looks_like_markdown(text):
        return "markdown"
    suffix = Path(name).suffix.lower()
    if suffix in (".md", ".markdown"):
        return "markdown"
    if suffix in (".csv", ".tsv"):
        return "csv"
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if "\t" in first_line or "," in first_line:
        return "csv"
    return "json"


def read_table(text: str, fmt: str = "auto", name: str = "") -> Table:
    if fmt not in FORMATS:
        raise InputError(f"unknown format '{fmt}'; choose one of: {', '.join(FORMATS)}")
    resolved = detect_format(text, name) if fmt == "auto" else fmt
    if resolved == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"JSON could not be parsed: {exc}") from None
        return table_from_payload(payload)
    if resolved == "markdown":
        return table_from_markdown(text)
    table = table_from_csv(text)
    if fmt == "auto" and not table.rows:
        raise InputError(
            "no table found: give JSON, a Markdown pipe table or CSV with a header and at least one row"
        )
    return table


def read_source(source: str, fmt: str = "auto") -> Table:
    """Read from a file path, or from stdin when source is '-'."""
    if source == "-":
        import sys

        return read_table(sys.stdin.read(), fmt, name="")
    path = Path(source).expanduser()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputError(f"input file not found: {source}") from None
    except OSError as exc:
        raise InputError(f"input file could not be read: {exc}") from None
    return read_table(text, fmt, name=str(path))


def iter_plain_cells(table: Table) -> Iterable[str]:
    yield from table.headers
    for row in table.rows:
        yield from row
