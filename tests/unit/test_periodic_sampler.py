from packages.media.periodic_sampler import (
    PeriodicSampler,
    SamplePoint,
)


def test_short_scene():

    sampler = PeriodicSampler()

    samples = sampler.sample(
        0,
        3000,
    )

    assert samples == [
        SamplePoint(
            timestamp_ms=0,
        )
    ]


def test_long_scene():

    sampler = PeriodicSampler()

    samples = sampler.sample(
        0,
        20000,
    )

    assert samples == [
        SamplePoint(0),
        SamplePoint(5000),
        SamplePoint(10000),
        SamplePoint(15000),
        SamplePoint(20000),
    ]