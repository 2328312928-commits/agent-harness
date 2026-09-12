from __future__ import annotations

import math
from statistics import median

MODEL_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "fake-deterministic-v1": (0.0, 0.0),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


class CostCalculator:
    @staticmethod
    def is_known(model: str) -> bool:
        return model in MODEL_PRICING_PER_MILLION

    @staticmethod
    def estimate_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        input_price, output_price = MODEL_PRICING_PER_MILLION.get(model, (0.0, 0.0))
        return (
            prompt_tokens / 1_000_000 * input_price
            + completion_tokens / 1_000_000 * output_price
        )


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_latencies(values: list[float]) -> dict[str, float]:
    return {
        "mean": sum(values) / len(values) if values else 0,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "median": median(values) if values else 0,
    }

