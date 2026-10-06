from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..ai.features import WaitTimeFeatureExtractor
from ..ai.predictor import StatisticalWaitTimePredictor, WaitTimeModel
from ..models import Queue, QueueEntry


class WaitTimePredictionService:
    def __init__(
        self, session: Session, predictor: WaitTimeModel | None = None
    ) -> None:
        self.session = session
        self.extractor = WaitTimeFeatureExtractor()
        self.predictor = predictor or StatisticalWaitTimePredictor()

    def predict(self, entry_id: UUID) -> dict:
        entry = self.session.scalar(
            select(QueueEntry)
            .options(joinedload(QueueEntry.queue).joinedload(Queue.service))
            .where(QueueEntry.id == entry_id)
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        features = self.extractor.extract(self.session, entry)
        prediction = self.predictor.predict(features)
        estimate = prediction.estimated_wait_minutes
        if features.queue_length == 0:
            spread = 0
        elif features.recent_completed_durations:
            durations = [
                duration
                for duration in features.recent_completed_durations
                if duration > 0
            ]
            spread = (
                max(2, round((max(durations) - min(durations)) / 2))
                if durations
                else max(2, round(estimate * 0.35))
            )
        else:
            spread = max(2, round(max(1, estimate) * 0.35))
        if features.active_counters:
            explanation = (
                f"Based on {features.people_ahead} people ahead and "
                f"{features.active_counters} active counters."
            )
        else:
            explanation = (
                f"Based on {features.people_ahead} people ahead; "
                "no active counters are available, so the estimate assumes one."
            )
        return {
            "estimated_minutes": estimate,
            "lower_bound_minutes": max(0, estimate - spread),
            "upper_bound_minutes": estimate + spread,
            "confidence": prediction.confidence,
            "model_version": f"{prediction.source}-v1",
            "factors": {
                "people_ahead": features.people_ahead,
                "queue_length": features.queue_length,
                "average_service_duration": round(features.average_service_minutes, 2),
                "active_counters": features.active_counters,
                "historical_samples": len(features.recent_completed_durations),
                "service_type": features.service_type,
                "hour_of_day": features.hour,
                "day_of_week": features.day_of_week,
                "current_processing_rate": round(features.processing_rate_per_hour, 2),
                "explanation": explanation,
            },
        }
