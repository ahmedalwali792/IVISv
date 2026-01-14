# FILE: tests/test_monotonic_ms.py
# ------------------------------------------------------------------------------
from ivis.common.time_utils import monotonic_ms


def test_monotonic_ms_non_decreasing():
    last = monotonic_ms()
    for _ in range(500):
        current = monotonic_ms()
        assert current >= last
        last = current
