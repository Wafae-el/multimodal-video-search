from dataclasses import dataclass


@dataclass(frozen=True)
class SamplePoint:
    timestamp_ms: int


class PeriodicSampler:

    def sample(
        self,
        start_ms: int,
        end_ms: int,
        interval_ms: int = 5000,
    ):
        samples = []

        current = start_ms

        while current <= end_ms:
            samples.append(
                SamplePoint(
                    timestamp_ms=current,
                )
            )

            current += interval_ms

        return samples