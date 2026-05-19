"""Generate favicon.ico and apple-touch-icon.png from favicon.svg.

Requires: pip install cairosvg pillow
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
IMG_DIR = BASE / "assets" / "img"


def main() -> None:
    try:
        from cairosvg import svg2png
    except ImportError:
        print("Install dependencies: pip install cairosvg pillow")
        sys.exit(1)

    svg_path = IMG_DIR / "favicon.svg"
    if not svg_path.exists():
        print(f"[ERROR] missing source: {svg_path}")
        sys.exit(1)
    svg_data = svg_path.read_bytes()

    svg2png(
        bytestring=svg_data,
        write_to=str(IMG_DIR / "apple-touch-icon.png"),
        output_width=180,
        output_height=180,
    )
    print("Generated apple-touch-icon.png")

    svg2png(
        bytestring=svg_data,
        write_to=str(IMG_DIR / "favicon-32.png"),
        output_width=32,
        output_height=32,
    )
    print("Generated favicon-32.png — convert to favicon.ico with:")
    print("  python -c \"from PIL import Image; Image.open('assets/img/favicon-32.png').save('assets/img/favicon.ico')\"")


if __name__ == "__main__":
    main()
