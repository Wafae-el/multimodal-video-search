def clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def audio_quality(
    snr_norm: float,
    speech_ratio: float,
    asr_confidence: float,
    clipping_ratio: float,
    weights: tuple[float, float, float, float] = (0.35, 0.25, 0.30, 0.10),
) -> float:
    w1, w2, w3, w4 = weights
    return clip01(w1 * snr_norm + w2 * speech_ratio + w3 * asr_confidence - w4 * clipping_ratio)


def renormalize_active_weights(weights: dict[str, float], active: set[str]) -> dict[str, float]:
    total = sum(weight for name, weight in weights.items() if name in active)
    if total <= 0:
        return {name: 0.0 for name in weights}
    return {name: (weight / total if name in active else 0.0) for name, weight in weights.items()}
