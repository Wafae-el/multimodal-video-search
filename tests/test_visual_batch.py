from pathlib import Path

from packages.visual.openclip_encoder import OpenCLIPVisualEncoder


def main():
    print("=" * 70)
    print("WEEK 4 - VISUAL BATCH EMBEDDING")
    print("=" * 70)

    frames = [
        Path("/tmp/test_frame.jpg"),
    ]

    print("FRAMES =", len(frames))

    encoder = OpenCLIPVisualEncoder(
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu",
    )

    embeddings = encoder.encode_images(frames)

    print("EMBEDDINGS =", len(embeddings))

    for i, embedding in enumerate(embeddings):
        print(
            f"FRAME {i}: "
            f"DIMENSION={len(embedding)} "
            f"NORM={(sum(x * x for x in embedding) ** 0.5):.4f}"
        )

    assert len(embeddings) == len(frames)

    for embedding in embeddings:
        assert len(embedding) == 512

    print("PASS: Batch embedding")
    print("PASS: One embedding per frame")
    print("PASS: Dimension = 512")
    print("=" * 70)
    print("VISUAL BATCH EMBEDDING = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()