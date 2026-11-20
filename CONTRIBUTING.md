# Contributing to table-png

Fixes and reports are welcome. You do not need to ask before opening a pull request for a bug fix.

## Before you start

- **A wrong render:** open an [issue](https://github.com/elfenomenokim/table-png/issues/new/choose)
  with the input file, the flags, the output PNG and your platform. Attach the image: a clipped
  cell or a missing glyph is easier to see than to describe.
- **A layout change:** describe the case that fails today. Column widths, wrapping and pagination
  are one design, not four independent knobs.
- **A security problem:** do not open a public issue. See [SECURITY.md](SECURITY.md).

## Set up

```sh
git clone https://github.com/elfenomenokim/table-png
cd table-png
python3 -m pip install -e .
table-png docs/demo/status.md --out /tmp/table-check.png --title "Check"
```

There is no test runner. The check is the image: open it once and look at the header row, the
numbers and any CJK text. Pillow is the only runtime dependency.

## What a good patch has

- **The input and the flags** that show the bug, and the image after the fix.
- **A rejection instead of a clipped image.** If a layout cannot fit one glyph in a column, or a
  title wider than the canvas, fail with a message rather than returning a plausible PNG.
- **A line under Unreleased** in [CHANGELOG.md](CHANGELOG.md) when a user will notice.
- **The platforms you did not test** written in the pull request. The `tests` workflow runs the
  install and render smoke check on Ubuntu, macOS and Windows with Python 3.9 and 3.13; visual glyph
  inspection stays manual.

## Review

Every pull request runs an automatic DeepSeek review. Ask for another pass with `@codex review` or
`@claude review` in a comment. If a finding looks wrong, say why in the pull request.

## Style

Keep parsing, font choice and drawing in their current modules, and keep demo inputs synthetic:
made-up service rows, never a user's table.

## Licence

Contributions are licensed under the MIT licence in [LICENSE](LICENSE).
