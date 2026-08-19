from packages.retrieval.scoring import cosine_similarity


def suppress_duplicates(
    ranked_ids: list[str], duplicate_groups: list[set[str]], limit: int
) -> list[str]:
    seen_groups: set[int] = set()
    result: list[str] = []
    for item_id in ranked_ids:
        group_index = next(
            (i for i, group in enumerate(duplicate_groups) if item_id in group), None
        )
        if group_index is not None and group_index in seen_groups:
            continue
        if group_index is not None:
            seen_groups.add(group_index)
        result.append(item_id)
        if len(result) == limit:
            break
    return result


def clip_pool_scores(
    query_frames: list[list[float]], archive_frames: dict[str, list[float]], beta: float = 0.7
) -> list[tuple[str, float]]:
    if not 0 <= beta <= 1:
        raise ValueError("beta must be in [0, 1]")
    scored = []
    for frame_id, vector in archive_frames.items():
        sims = [cosine_similarity(query, vector) for query in query_frames]
        scored.append((frame_id, beta * max(sims) + (1 - beta) * (sum(sims) / len(sims))))
    return sorted(scored, key=lambda item: (-item[1], item[0]))
