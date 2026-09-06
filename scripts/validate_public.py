#!/usr/bin/env python3
"""Validate public repository presentation without network access."""

from __future__ import annotations

import struct
from pathlib import Path

PNG_HEADER_BYTES = 24
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_HERO_WIDTH = 1200
MIN_HERO_HEIGHT = 600
MIN_HERO_RATIO = 1.8
MAX_HERO_RATIO = 2.2


class InvalidHeroError(ValueError):
    """Raised when the configured hero is not a PNG image."""


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG dimensions from its fixed IHDR location."""
    payload = path.read_bytes()[:PNG_HEADER_BYTES]
    if len(payload) != PNG_HEADER_BYTES or payload[:8] != PNG_SIGNATURE:
        raise InvalidHeroError
    return struct.unpack(">II", payload[16:PNG_HEADER_BYTES])


def main() -> int:
    """Validate required files, hero linkage, and public-facing language."""
    root = Path(__file__).resolve().parents[1]
    required = [
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "docs/architecture.md",
        "docs/guru-benchmark-review.md",
        "docs/onboarding.md",
        "docs/raycast.md",
        "docs/vision.json",
        "assets/hero.png",
    ]
    missing = [item for item in required if not (root / item).is_file()]
    if missing:
        print("missing public files: " + ", ".join(missing))
        return 1

    readme = (root / "README.md").read_text(encoding="utf-8")
    first_screen = "\n".join(readme.splitlines()[:15])
    if 'src="assets/hero.png"' not in first_screen:
        print("README does not render the hero near the top")
        return 1
    width, height = png_dimensions(root / "assets" / "hero.png")
    if (
        width < MIN_HERO_WIDTH
        or height < MIN_HERO_HEIGHT
        or not MIN_HERO_RATIO <= width / height <= MAX_HERO_RATIO
    ):
        print(f"hero dimensions are unsuitable: {width}x{height}")
        return 1

    public_docs = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    forbidden = ("todo", "tbd", "placeholder", "coming soon")
    for document in public_docs:
        lowered = document.read_text(encoding="utf-8").casefold()
        for marker in forbidden:
            if marker in lowered:
                print(f"stale public marker {marker!r} in {document.relative_to(root)}")
                return 1
    print(f"public presentation: valid; hero={width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
