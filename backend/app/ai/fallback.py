"""Safe deterministic fallback for wait-time predictions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .features import WaitTimeFeatures


@dataclass(frozen=True)
class WaitTimePrediction:
    estimated_wait_minutes: int
    confidence: float
    source: str = "statistical"


class FallbackWaitTimePredictor:
    """Conservative model used when there is little or no historical data."""

    def predict(self, features: WaitTimeFeatures) -> WaitTimePrediction:
        if features.queue_length <= 0:
            return WaitTimePrediction(0, 1.0, "fallback")
        durations = [
            duration
            for duration in features.recent_completed_durations
            if duration > 0
        ]
        baseline = median(durations) if durations else features.average_service_minutes
        baseline = max(1.0, float(baseline or 0))
        counters = max(1, features.active_counters)
        estimate = max(1, round(features.people_ahead * baseline / counters))
        confidence = min(0.95, 0.35 + 0.05 * len(features.recent_completed_durations))
        if features.active_counters == 0:
            confidence *= 0.65
        return WaitTimePrediction(max(0, estimate), round(confidence, 2), "fallback")
