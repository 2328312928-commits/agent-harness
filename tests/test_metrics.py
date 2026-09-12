from agent_harness.observability.metrics import CostCalculator, percentile


def test_unknown_provider_pricing_is_explicit() -> None:
    assert CostCalculator.is_known("fake-deterministic-v1")
    assert not CostCalculator.is_known("deepseek-v4.1-flash")
    assert CostCalculator.estimate_usd("deepseek-v4.1-flash", 1000, 1000) == 0


def test_percentile() -> None:
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
