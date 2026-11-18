# Security policy

## Supported versions

Security fixes go into the latest release. Upgrade before reporting, in case the problem is
already fixed.

| Version | Supported |
| --- | --- |
| 0.1.3 | Yes |
| Older | No |

## Reporting a vulnerability

Report it privately, not in a public issue: use the
[Report a vulnerability](https://github.com/elfenomenokim/table-png/security/advisories/new) form on
the repository's Security tab.

Include the input, the flags, the version and what an attacker could do with the result. You get a
reply within a few days.

## In scope

- A file written outside the `--out` path, or a second file created beside the image without being
  asked for.
- Memory or CPU that grows without bound on a large input, so a table from an untrusted source can
  exhaust the process.
- A font path or a font name that loads a file the caller did not choose.
- Cell content that changes the drawing of another cell, or escapes the image bounds.

## Not a vulnerability

- Text from the table appearing in the image. The tool renders what you give it.
- A missing glyph, a fallback font or emoji drawn as letters. Install a CJK font and open an issue
  if the result is still wrong; it is a rendering bug.
- A rejected layout. Narrow columns and over-wide titles are refused on purpose.

## Disclosure

Once a fix is released, the advisory is published with credit to the reporter unless they prefer
otherwise.
