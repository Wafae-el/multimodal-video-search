from pathlib import Path

from PIL import Image

from packages.media.frame_quality import FrameQuality


BASE = Path("/tmp/week4_quality")

BLACK = BASE / "black.jpg"
BRIGHT = BASE / "bright.jpg"
NORMAL = BASE / "normal.jpg"
LOW_RES = BASE / "low_res.jpg"


def create_test_images():
    BASE.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Completely black
    Image.new(
        "RGB",
        (640, 360),
        (0, 0, 0),
    ).save(BLACK)

    # Completely white
    Image.new(
        "RGB",
        (640, 360),
        (255, 255, 255),
    ).save(BRIGHT)

    # Normal image with texture
    image = Image.new(
        "RGB",
        (640, 360),
        (120, 120, 120),
    )

    pixels = image.load()

    for x in range(0, 640, 20):
        for y in range(0, 360, 20):
            pixels[x, y] = (255, 0, 0)

    image.save(NORMAL)

    # Insufficient resolution
    Image.new(
        "RGB",
        (160, 90),
        (120, 120, 120),
    ).save(LOW_RES)


def main():

    print("=" * 70)
    print("WEEK 4 - FRAME QUALITY VALIDATION")
    print("=" * 70)

    create_test_images()

    quality = FrameQuality()

    # ------------------------------------------------------------
    # BLACK
    # ------------------------------------------------------------

    assert quality.is_black(BLACK)

    print("PASS: Black frame detection")

    # ------------------------------------------------------------
    # BRIGHT / CLIPPING
    # ------------------------------------------------------------

    assert quality.is_bright(BRIGHT)

    print("PASS: Bright/clipped frame detection")

    # ------------------------------------------------------------
    # RESOLUTION
    # ------------------------------------------------------------

    width, height = quality.resolution(
        NORMAL
    )

    print(
        "NORMAL RESOLUTION =",
        width,
        "x",
        height,
    )

    assert width == 640
    assert height == 360

    print("PASS: Resolution extraction")

    assert quality.has_sufficient_resolution(
        NORMAL
    )

    assert not quality.has_sufficient_resolution(
        LOW_RES
    )

    print("PASS: Resolution quality check")

    # ------------------------------------------------------------
    # NORMAL FRAME
    # ------------------------------------------------------------

    assert not quality.is_black(NORMAL)
    assert not quality.is_bright(NORMAL)

    print("PASS: Normal frame accepted by black/bright checks")

    # ------------------------------------------------------------
    # USABILITY
    # ------------------------------------------------------------

    assert not quality.is_usable(
        BLACK
    )

    assert not quality.is_usable(
        BRIGHT
    )

    assert not quality.is_usable(
        LOW_RES
    )

    print("PASS: Unusable frames rejected")

    print()
    print("=" * 70)
    print("FRAME QUALITY VALIDATION = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()