from __future__ import annotations

from pathlib import Path

from PIL import Image


PUBLIC_DIR = Path("web/public")
SUPPLIED_LOGO = PUBLIC_DIR / "ChatGPT Image Sep 28, 2026, 10_39_29 PM.png"
CANONICAL_PNG = PUBLIC_DIR / "shah-industries-logo.png"
WEBP_LOGO = PUBLIC_DIR / "shah-industries-logo.webp"


def main() -> None:
    if not SUPPLIED_LOGO.exists():
        raise FileNotFoundError(f"Supplied logo PNG not found: {SUPPLIED_LOGO}")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SUPPLIED_LOGO)
    image.save(CANONICAL_PNG, "PNG")
    image.save(WEBP_LOGO, "WEBP", lossless=True, quality=95, method=6)
    print(f"{CANONICAL_PNG} {image.size[0]}x{image.size[1]}")
    print(f"{WEBP_LOGO} {image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    main()
