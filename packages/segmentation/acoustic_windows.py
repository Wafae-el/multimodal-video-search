from typing import List, Dict


def create_acoustic_windows(
    duration_ms: int,
    window_ms: int = 5000,
) -> List[Dict]:

    windows = []

    start = 0
    index = 1

    while start < duration_ms:

        end = min(start + window_ms, duration_ms)

        windows.append(
            {
                "window_id": index,
                "start_ms": start,
                "end_ms": end,
            }
        )

        start = end
        index += 1

    return windows