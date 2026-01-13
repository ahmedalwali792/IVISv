from ui.results_cache import ResultsCache


class FakeTime:
    def __init__(self, value: float = 0.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


def test_results_cache_lru_eviction():
    clock = FakeTime()
    cache = ResultsCache(max_entries=2, ttl_seconds=60, time_fn=clock)
    cache.put("a", 1)
    cache.put("b", 2)
    assert len(cache) == 2
    cache.get("a")
    cache.put("c", 3)
    assert len(cache) == 2
    assert cache.get("b") is None
    assert cache.get("a") == 1


def test_results_cache_ttl_expiry():
    clock = FakeTime()
    cache = ResultsCache(max_entries=10, ttl_seconds=1, time_fn=clock)
    cache.put("a", 1)
    clock.advance(2)
    assert cache.get("a") is None
    assert len(cache) == 0
