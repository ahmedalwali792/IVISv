from ivis.common.time_utils import latency_ms


def test_latency_ms_simple_difference():
    assert latency_ms(1500, 1000) == 500


def test_latency_ms_zero():
    assert latency_ms(1000, 1000) == 0
