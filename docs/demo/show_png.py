"""Render a PNG in a true-colour terminal for the recorded README demo."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    image = Image.open(Path(sys.argv[1])).convert("RGB")
    width = 120
    height = max(1, round(image.height * width / image.width / 2))
    image.thumbnail((width, height * 2))
    for y in range(0, image.height, 2):
        for x in range(image.width):
            top = image.getpixel((x, y))
            bottom = image.getpixel((x, min(y + 1, image.height - 1)))
            print(f"\033[38;2;{top[0]};{top[1]};{top[2]}m\033[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m▀", end="")
        print("\033[0m")
    print("\033[0m")


if __name__ == "__main__":
    main()
