"""Replaceable deterministic wait-time prediction model."""

from __future__ import annotations

from statistics import median
from typing import Protocol

from .fallback import FallbackWaitTimePredictor, WaitTimePrediction
from .features import WaitTimeFeatures


class WaitTimeModel(Protocol):
    def predict(self, features: WaitTimeFeatures) -> WaitTimePrediction: ...


class StatisticalWaitTimePredictor:
    """Robust baseline model using median history and current throughput."""

    def __init__(self, fallback: WaitTimeModel | None = None) -> None:
        self.fallback = fallback or FallbackWaitTimePredictor()

    def predict(self, features: WaitTimeFeatures) -> WaitTimePrediction:
        if features.queue_length <= 0:
            return WaitTimePrediction(0, 1.0, "statistical")
        durations = [
            duration
            for duration in features.recent_completed_durations
            if duration > 0
        ]
        if not durations:
            return self.fallback.predict(features)
        # Blend sparse history with the configured duration to avoid overfitting
        # one or two completed visits while remaining robust to outliers.
        historical_minutes = float(median(durations))
        configured_minutes = max(0.0, float(features.average_service_minutes or 0))
        if configured_minutes:
            history_weight = min(0.8, len(durations) / (len(durations) + 3))
            service_minutes = (
                configured_minutes * (1 - history_weight)
                + historical_minutes * history_weight
            )
        else:
            service_minutes = historical_minutes

        counters = max(1, features.active_counters)
        baseline = features.people_ahead * service_minutes / counters
        if features.processing_rate_per_hour > 0:
            rate_estimate = (
                features.people_ahead * 60 / features.processing_rate_per_hour
            )
            rate_weight = min(0.25, features.processing_rate_per_hour / 20)
            baseline = baseline * (1 - rate_weight) + rate_estimate * rate_weight

        estimate = max(1, round(baseline))
        confidence = min(0.98, 0.5 + min(len(durations), 16) * 0.025)
        if features.active_counters <= 0:
            confidence *= 0.8
        return WaitTimePrediction(estimate, round(confidence, 2), "statistical")


Predictor = StatisticalWaitTimePredictor
