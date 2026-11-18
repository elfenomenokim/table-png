# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses `MAJOR.MINOR.PATCH`.

## [0.1.3] - 2026-11-18

### Fixed

- A column that cannot hold one glyph plus padding is refused instead of produced clipped.
- A `--title` wider than the canvas is wrapped and the height reserves every line.

## [0.1.2] - 2026-11-18

### Changed

- Documentation release: the README, the Korean README and the demo recording were rewritten, and
  the version moved with them. No behaviour change.

## [0.1.1] - 2026-11-17

### Changed

- Windows 11 was checked. The README records what that run showed: flag emoji render as country
  letters and family emoji sequences render as separate faces.

## [0.1.0] - 2026-11-17

### Added

- Markdown, CSV and JSON input, light and dark themes, a title, pagination and `--json` output.
- `--width` clamped to 720–1600 px, with a page size of 40 rows by default.
- Korean and colour emoji render without a colour-font install.
