from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.features import WaitTimeFeatures
from app.ai.predictor import StatisticalWaitTimePredictor
from app.api.auth_dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.entities import QueueEntryStatus, UserRole
from app.services.wait_time import WaitTimePredictionService


def make_features(
    *,
    people_ahead: int = 4,
    queue_length: int = 4,
    average_service_minutes: float = 10,
    active_counters: int = 2,
    recent_completed_durations: tuple[float, ...] = (),
    service_type: str = "admissions",
    hour: int = 10,
    day_of_week: int = 1,
    processing_rate_per_hour: float = 0,
) -> WaitTimeFeatures:
    return WaitTimeFeatures(
        people_ahead=people_ahead,
        queue_length=queue_length,
        average_service_minutes=average_service_minutes,
        active_counters=active_counters,
        recent_completed_durations=recent_completed_durations,
        service_type=service_type,
        hour=hour,
        day_of_week=day_of_week,
        processing_rate_per_hour=processing_rate_per_hour,
    )


def test_empty_queue_has_zero_wait_and_zero_width_bounds() -> None:
    features = make_features(
        people_ahead=0,
        queue_length=0,
        recent_completed_durations=(8, 10, 12),
    )
    prediction = StatisticalWaitTimePredictor().predict(features)

    assert prediction.estimated_wait_minutes == 0
    assert prediction.confidence == 1

    service = WaitTimePredictionService(StubSession(SimpleNamespace(
        queue_id=uuid4(),
        status=QueueEntryStatus.WAITING,
    ), 0))
    service.extractor = StubExtractor(features)
    result = service.predict(uuid4())
    assert result["lower_bound_minutes"] == 0
    assert result["upper_bound_minutes"] == 0


def test_baseline_scales_with_people_ahead_and_active_counters() -> None:
    predictor = StatisticalWaitTimePredictor()

    one_ahead = predictor.predict(make_features(people_ahead=1, active_counters=1))
    several_ahead = predictor.predict(make_features(people_ahead=4, active_counters=1))
    multiple_counters = predictor.predict(make_features(people_ahead=4, active_counters=2))

    assert one_ahead.estimated_wait_minutes == 10
    assert several_ahead.estimated_wait_minutes == 40
    assert multiple_counters.estimated_wait_minutes == 20


def test_first_person_in_a_nonempty_queue_gets_minimum_estimate() -> None:
    prediction = StatisticalWaitTimePredictor().predict(
        make_features(people_ahead=0, queue_length=1, active_counters=1)
    )

    assert prediction.estimated_wait_minutes == 1


def test_fallback_is_deterministic_without_history() -> None:
    features = make_features(recent_completed_durations=())
    predictor = StatisticalWaitTimePredictor()

    assert predictor.predict(features) == predictor.predict(features)
    assert predictor.predict(features).estimated_wait_minutes == 20
    assert predictor.predict(features).source == "fallback"


def test_historical_durations_adjust_prediction_robustly() -> None:
    features = make_features(
        people_ahead=2,
        active_counters=1,
        recent_completed_durations=(20,),
    )

    prediction = StatisticalWaitTimePredictor().predict(features)

    assert prediction.estimated_wait_minutes == 25
    assert 0 < prediction.confidence <= 1


def test_no_active_counters_uses_one_safe_divisor() -> None:
    features = make_features(people_ahead=1, active_counters=0)

    prediction = StatisticalWaitTimePredictor().predict(features)

    assert prediction.estimated_wait_minutes == 10


def test_missing_duration_still_produces_minimum_wait() -> None:
    features = make_features(
        people_ahead=1, average_service_minutes=0, recent_completed_durations=()
    )

    prediction = StatisticalWaitTimePredictor().predict(features)

    assert prediction.estimated_wait_minutes == 1


def test_prediction_response_has_ordered_bounds() -> None:
    features = make_features(people_ahead=4)
    service = WaitTimePredictionService(
        StubSession(
            SimpleNamespace(queue_id=uuid4(), status=QueueEntryStatus.WAITING),
            4,
        )
    )
    service.extractor = StubExtractor(features)

    result = service.predict(uuid4())

    assert result["lower_bound_minutes"] <= result["estimated_minutes"]
    assert result["estimated_minutes"] <= result["upper_bound_minutes"]
    assert result["model_version"] == "fallback-v1"


def test_invalid_queue_entry_returns_not_found() -> None:
    class MissingEntrySession:
        def get(self, _model: object, _entry_id: object) -> None:
            return None

    def override_db():
        yield MissingEntrySession()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.CUSTOMER
    )

    response = TestClient(app).get(f"/api/v1/ai/wait-time/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Queue entry not found"


def test_active_queue_entry_without_history_returns_prediction() -> None:
    customer_id = uuid4()
    queue_id = uuid4()
    entry = SimpleNamespace(
        id=uuid4(),
        queue_id=queue_id,
        customer_id=customer_id,
        queue_number=2,
        status=QueueEntryStatus.WAITING,
        joined_at=datetime.now(timezone.utc),
        queue=SimpleNamespace(
            id=queue_id,
            service=SimpleNamespace(
                id=uuid4(),
                branch_id=uuid4(),
                average_service_minutes=10,
                code="admissions",
                name="Admissions",
            ),
        ),
    )

    class QueueSession:
        def __init__(self) -> None:
            self.scalar_results = iter((entry, 2, 1, 0))

        def get(self, _model: object, _entry_id: object) -> object:
            return entry

        def scalar(self, _query: object) -> object:
            return next(self.scalar_results)

        def scalars(self, _query: object) -> list[object]:
            return []

    session = QueueSession()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=customer_id, role=UserRole.CUSTOMER
    )

    response = TestClient(app).get(f"/api/v1/ai/wait-time/{entry.id}")

    assert response.status_code == 200
    result = response.json()
    assert result["estimated_minutes"] == 10
    assert result["model_version"] == "fallback-v1"
    assert result["factors"]["historical_samples"] == 0
    assert "no active counters" in result["factors"]["explanation"]


class StubExtractor:
    def __init__(self, features: WaitTimeFeatures) -> None:
        self.features = features

    def extract(self, _session: object, _entry: object) -> WaitTimeFeatures:
        return self.features


class StubSession:
    def __init__(self, entry: object, queue_length: int) -> None:
        self.entry = entry
        self.queue_length = queue_length
        self.calls = 0

    def scalar(self, _query: object) -> object:
        self.calls += 1
        return self.entry if self.calls == 1 else self.queue_length
