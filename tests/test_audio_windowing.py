from packages.audio.windowing import AudioWindowGenerator


def main():

    print("=" * 70)
    print("WEEK 5 - AUDIO WINDOWING")
    print("=" * 70)

    generator = AudioWindowGenerator(
        window_ms=5000,
        overlap_ms=2500,
    )

    windows = generator.generate(
        duration_ms=15000
    )

    print("WINDOW COUNT =", len(windows))

    for window in windows:
        print(
            f"WINDOW {window.index}: "
            f"{window.start_ms} -> {window.end_ms} "
            f"duration={window.duration_ms}"
        )

    assert len(windows) == 5

    assert windows[0].start_ms == 0
    assert windows[0].end_ms == 5000

    assert windows[1].start_ms == 2500
    assert windows[1].end_ms == 7500

    assert windows[2].start_ms == 5000
    assert windows[2].end_ms == 10000

    assert windows[3].start_ms == 7500
    assert windows[3].end_ms == 12500

    assert windows[4].start_ms == 10000
    assert windows[4].end_ms == 15000

    print("PASS: 5-second windows")
    print("PASS: 2.5-second overlap")
    print("PASS: Correct hop size")

    print()
    print("=" * 70)
    print("AUDIO WINDOWING = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()