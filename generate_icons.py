"""
Generate PWA icons from SVG source.
Run: python generate_icons.py
Requires: pip install Pillow cairosvg
"""
import os

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
ICONS_DIR = os.path.join(os.path.dirname(__file__), "web", "public", "icons")
SVG_PATH = os.path.join(ICONS_DIR, "icon.svg")


def generate():
    os.makedirs(ICONS_DIR, exist_ok=True)

    # Try cairosvg first, fall back to creating simple PNGs with Pillow
    try:
        import cairosvg
        for size in SIZES:
            output = os.path.join(ICONS_DIR, f"icon-{size}.png")
            cairosvg.svg2png(
                url=SVG_PATH,
                write_to=output,
                output_width=size,
                output_height=size,
            )
            print(f"  ✓ icon-{size}.png")
        print("Done! Icons generated from SVG.")
        return
    except ImportError:
        pass

    # Fallback: create simple colored icons with Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont

        for size in SIZES:
            img = Image.new("RGBA", (size, size), (15, 15, 35, 255))
            draw = ImageDraw.Draw(img)

            # Draw a purple circle
            margin = size // 8
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill=(124, 58, 237, 255),
            )

            # Draw mic icon (simple rectangle + arc)
            cx, cy = size // 2, size // 2
            w = size // 6
            h = size // 3
            draw.rounded_rectangle(
                [cx - w, cy - h, cx + w, cy + w],
                radius=w,
                fill=(255, 255, 255, 230),
            )

            output = os.path.join(ICONS_DIR, f"icon-{size}.png")
            img.save(output, "PNG")
            print(f"  ✓ icon-{size}.png (Pillow fallback)")

        print("Done! Icons generated with Pillow.")
    except ImportError:
        # Create minimal placeholder files
        print("Neither cairosvg nor Pillow available.")
        print("Install one: pip install Pillow")
        print("Creating placeholder files...")
        for size in SIZES:
            output = os.path.join(ICONS_DIR, f"icon-{size}.png")
            if not os.path.exists(output):
                # Write a minimal 1x1 PNG as placeholder
                import struct, zlib
                def create_png(width, height):
                    def chunk(ctype, data):
                        c = ctype + data
                        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                    raw = b""
                    for _ in range(height):
                        raw += b"\x00" + b"\x0f\x0f\x23\xff" * width
                    return (
                        b"\x89PNG\r\n\x1a\n"
                        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                        + chunk(b"IDAT", zlib.compress(raw))
                        + chunk(b"IEND", b"")
                    )
                with open(output, "wb") as f:
                    f.write(create_png(size, size))
                print(f"  ✓ icon-{size}.png (placeholder)")


if __name__ == "__main__":
    print("Generating PWA icons...")
    generate()
