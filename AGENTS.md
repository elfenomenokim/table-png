# AGENTS.md — table-png

Instructions for an AI agent asked to put a table somewhere that cannot show a Markdown table.

## Repository work

- Python package: `src/table_png/`; CLI: `src/table_png/cli.py`; renderer: `src/table_png/render.py`.
- Run from this directory with `python -m table_png --help` or install the checkout with `python -m pip install -e .`.
- The only runtime dependency is Pillow. Keep parsing, font choice and drawing in their current modules.
- No test or lint command is configured in this repository. Do not claim additional platform coverage from a local macOS run.
- Preserve explicit font selection and the current failure message when a CJK font cannot be found.
- Demo inputs belong under `docs/demo/`; use made-up service rows and do not put user tables in committed examples.

## When to use it

Use it when the destination renders Markdown as plain text or drops tables: a chat message, a phone notification, a bot reply, an image-only field, a slide, a PDF, a social post, an issue comment that strips tables.

Do not use it when the destination already renders Markdown (GitHub, most wikis, most chat clients with Markdown on), or when the user asked for text. Do not use it to make a picture of something that is not a table.

## Install

```console
$ pipx install table-png
```

If `pipx` is unavailable, `uvx table-png …` runs it without installing, and `pip install table-png` works inside an existing environment. Python 3.9+ and Pillow are required; `pipx`/`uv` fetch both.

On a minimal Linux image with no CJK font, install one first: `apt install fonts-noto-cjk fonts-noto-color-emoji`.

## Use

```console
$ table-png table.md --out table.png --theme dark --title "제목"
```

- Input: a file path, or `-` for stdin (the default). JSON, Markdown pipe table, or CSV; `--format` forces one when detection would guess wrong.
- Output: `--out` is required. More than `--rows-per-page` rows (default 40) produce `table-001.png`, `table-002.png`, … — attach every page.
- Ask for the machine-readable result with `--json`: `{"ok":true,"png":…,"width":…,"height":…,"rows":…}`. `png` and `height` are arrays when paginated. On failure the exit code is 1 and the object is `{"error":"…"}`.
- Width is clamped to 720–1600 px. For a narrow chat column, `--width 720`; for a slide, `--width 1600`.

## Verify before you attach

1. The command exited 0 and printed a path.
2. The file exists and is larger than a few hundred bytes.
3. Open the image once and check that the header row, the numbers and any CJK text are visible and not clipped.

## Do not

- Do not paste the Markdown table into the message as well; send the image instead of both.
- Do not invent fonts or set `--font` to a font you have not checked exists. If the run fails with "no CJK-capable font found", install one or pass a real path.
- Do not use the tool for tables over a few hundred rows; pagination produces many files. Summarize first.
- Do not treat the rendered image as a data source later; keep the original table.

- If columns cannot fit their text at the chosen width, increase `--width` or reduce the columns.
