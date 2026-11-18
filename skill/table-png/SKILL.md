---
name: table-png
description: Render a table as a PNG image when the destination cannot show a Markdown table (chat message, phone notification, bot reply, slide, PDF, social post, image-only field). Use for tables that must arrive as a picture with correct Korean, Chinese or Japanese text and colour emoji. Do not use when the destination already renders Markdown, or when the user asked for text.
---

# table-png

Turn a table into a PNG that renders correctly everywhere, CJK text and colour emoji included.

## When this skill applies

The destination shows Markdown as literal pipes, or drops tables entirely: a chat message, a push notification, a bot reply, an image-only field, a slide, a PDF, a social post.

If the destination renders Markdown (GitHub, most wikis, Markdown-enabled chat), send the table as text. If the user asked for text, send text.

## Steps

1. Write the table to a file, or pipe it. Markdown pipe table, CSV and JSON all work; the format is detected, and `--format` forces one.
2. Run the CLI:

   ```console
   $ table-png table.md --out table.png --json
   ```

   Useful options: `--title "제목"`, `--theme dark`, `--width 720` for a narrow chat column, `--width 1600` for a slide.
3. Read the JSON result. Exit code 0 with `"ok":true` means the file was written. When `png` is an array, the table paginated — attach every page, in order.
4. Open the image once and confirm the header row, the numbers and any CJK text are visible and not clipped.
5. Attach the PNG to the destination. Do not also paste the Markdown table.

## Install

```console
$ pipx install table-png
```

`uvx table-png …` runs it without installing. On a minimal Linux image with no CJK font, install one first (`apt install fonts-noto-cjk fonts-noto-color-emoji`).

## Notes

- Input defaults to stdin, so `some-command --format markdown | table-png - --out out.png` works.
- Width is clamped to 720–1600 px; `--font-size` scales padding and title with the text.
- Overrides: `--font PATH` / `TABLE_PNG_FONT`, `--emoji-font PATH` / `TABLE_PNG_EMOJI_FONT`.
- A failure prints `{"error":"…"}` and exits 1. "no CJK-capable font found" means install a font or pass `--font`.
- Do not use it for hundreds of rows; pagination produces many files. Summarize first.
