import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import (
    get_current_user,
    get_db,
    get_optional_current_user,
)
from app.main import app
from app.models import (
    Branch,
    FeedbackReport,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import UserRole


def _client(db: Session, current_user: User | None) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_optional_current_user] = lambda: current_user
    return TestClient(app)


def test_anonymous_feedback_is_persisted_and_idempotent(db_session: Session) -> None:
    client = _client(db_session, None)
    payload = {
        "category": "general",
        "title": "A small improvement",
        "description": "The service search could explain why some results are unavailable.",
        "is_anonymous": True,
        "page_identifier": "/services",
        "app_version": "0.1.0",
        "idempotency_key": str(uuid.uuid4()),
    }

    first = client.post("/api/v1/feedback", json=payload)
    retry = client.post("/api/v1/feedback", json=payload)

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]
    report = db_session.get(FeedbackReport, uuid.UUID(first.json()["id"]))
    assert report is not None
    assert report.reporter_user_id is None
    assert report.organization_id is None
    assert report.is_anonymous is True


def test_queue_context_is_verified_and_only_organization_context_is_stored(
    db_session: Session,
) -> None:
    organization = Organization(name="Queue Context Org", slug=f"context-{uuid.uuid4()}")
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Service", code=f"S-{uuid.uuid4().hex[:6]}", branch=branch)
    queue = Queue(name="Main queue", prefix="Q", service=service)
    customer = User(
        full_name="Queue Customer",
        email=f"queue-customer-{uuid.uuid4()}@example.test",
        password_hash="not-used",
        role=UserRole.CUSTOMER,
    )
    other_customer = User(
        full_name="Other Queue Customer",
        email=f"other-queue-customer-{uuid.uuid4()}@example.test",
        password_hash="not-used",
        role=UserRole.CUSTOMER,
    )
    entry = QueueEntry(queue=queue, customer=customer, queue_number=1)
    other_entry = QueueEntry(queue=queue, customer=other_customer, queue_number=2)
    db_session.add_all([entry, other_entry])
    db_session.commit()

    client = _client(db_session, customer)
    payload = {
        "category": "queue_accuracy",
        "title": "Incorrect position shown",
        "description": "My position number did not match the queue display.",
        "queue_context_entry_id": str(entry.id),
        "idempotency_key": str(uuid.uuid4()),
    }
    response = client.post("/api/v1/feedback", json=payload)

    assert response.status_code == 201
    report = db_session.get(FeedbackReport, uuid.UUID(response.json()["id"]))
    assert report is not None
    assert report.organization_id == organization.id
    assert report.branch_id == branch.id
    assert not hasattr(report, "queue_entry_id")

    payload["idempotency_key"] = str(uuid.uuid4())
    payload["queue_context_entry_id"] = str(other_entry.id)
    assert client.post("/api/v1/feedback", json=payload).status_code == 404


def test_feedback_visibility_workflow_and_metrics_are_scoped(db_session: Session) -> None:
    organization = Organization(name="Feedback Org", slug=f"feedback-{uuid.uuid4()}")
    other_organization = Organization(
        name="Other Feedback Org", slug=f"feedback-other-{uuid.uuid4()}"
    )
    branch = Branch(name="Feedback Branch", organization=organization)
    customer = User(
        full_name="Feedback Customer",
        email=f"customer-{uuid.uuid4()}@example.test",
        password_hash="not-used",
        role=UserRole.CUSTOMER,
        organization=organization,
    )
    admin = User(
        full_name="Feedback Admin",
        email=f"admin-{uuid.uuid4()}@example.test",
        password_hash="not-used",
        role=UserRole.ADMIN,
        organization=organization,
    )
    outsider = User(
        full_name="Other Admin",
        email=f"other-admin-{uuid.uuid4()}@example.test",
        password_hash="not-used",
        role=UserRole.ADMIN,
        organization=other_organization,
    )
    db_session.add_all([branch, customer, admin, outsider])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.add(
        OrganizationMembership(
            user_id=outsider.id,
            organization_id=other_organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()

    customer_client = _client(db_session, customer)
    submitted = customer_client.post(
        "/api/v1/feedback",
        json={
            "category": "queue_accuracy",
            "title": "Wait estimate was too short",
            "description": "The displayed estimate was much shorter than the actual wait.",
            "rating": 2,
            "page_identifier": "/queue/:id",
            "app_version": "0.1.0",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert submitted.status_code == 201
    report_id = submitted.json()["id"]

    assert customer_client.get("/api/v1/feedback/mine").json()["total"] == 1
    assert customer_client.get(f"/api/v1/feedback/{uuid.uuid4()}").status_code == 404

    outsider_client = _client(db_session, outsider)
    assert outsider_client.get("/api/v1/feedback/managed").json()["total"] == 0
    assert outsider_client.get(f"/api/v1/feedback/{report_id}").status_code == 404

    admin_client = _client(db_session, admin)
    managed = admin_client.get("/api/v1/feedback/managed")
    assert managed.status_code == 200
    assert managed.json()["total"] == 1
    assert managed.json()["items"][0]["id"] == report_id

    assert admin_client.post(
        f"/api/v1/feedback/{report_id}/notes",
        json={"body": "Keep the wait estimate model under review."},
    ).status_code == 200
    customer_client = _client(db_session, customer)
    customer_view = customer_client.get(f"/api/v1/feedback/{report_id}").json()
    assert all(not reply["is_internal"] for reply in customer_view["replies"])
    assert "Keep the wait estimate model under review." not in str(customer_view)

    admin_client = _client(db_session, admin)
    assert admin_client.patch(
        f"/api/v1/feedback/{report_id}/status",
        json={"status": "under_review"},
    ).status_code == 200
    resolved = admin_client.patch(
        f"/api/v1/feedback/{report_id}/status",
        json={
            "status": "resolved",
            "resolution_summary": "Wait estimates now use recent queue processing data.",
            "release_version": "0.2.0",
        },
    )
    assert resolved.status_code == 200

    customer_client = _client(db_session, customer)
    assert customer_client.post(
        f"/api/v1/feedback/{report_id}/confirm", json={"helpful": True}
    ).status_code == 200
    admin_client = _client(db_session, admin)
    metrics = admin_client.get("/api/v1/feedback/metrics").json()
    assert metrics["total"] == 1
    assert metrics["average_rating"] == 2.0
    assert metrics["resolution_confirmation_rate"] == 100.0
    assert metrics["by_category"] == {"queue_accuracy": 1}

    customer_client = _client(db_session, customer)
    feature_report = customer_client.post(
        "/api/v1/feedback",
        json={
            "category": "feature_request",
            "title": "Show queue trend history",
            "description": "Show how the queue wait estimate changed over time.",
            "idempotency_key": str(uuid.uuid4()),
        },
    ).json()
    admin_client = _client(db_session, admin)
    for next_status in ("under_review", "planned"):
        assert admin_client.patch(
            f"/api/v1/feedback/{feature_report['id']}/status",
            json={"status": next_status},
        ).status_code == 200
    customer_client = _client(db_session, customer)
    assert customer_client.get("/api/v1/feedback/features").json()["total"] == 1
    vote = customer_client.post(f"/api/v1/feedback/{feature_report['id']}/votes")
    assert vote.json() == {"voted": True, "votes": 1}
    assert customer_client.get("/api/v1/feedback/features").json()["items"][0][
        "voted_by_current_user"
    ]
    assert customer_client.post(
        f"/api/v1/feedback/{feature_report['id']}/votes"
    ).json()["votes"] == 1
    assert customer_client.delete(
        f"/api/v1/feedback/{feature_report['id']}/votes"
    ).json() == {"voted": False, "votes": 0}
    admin_client = _client(db_session, admin)
    assert admin_client.get(
        "/api/v1/feedback/managed?sort_by=votes"
    ).status_code == 200

    created_task = admin_client.post(
        f"/api/v1/feedback/{report_id}/tasks",
        json={
            "title": "Improve wait estimates",
            "description": "Use recent queue activity in the estimate.",
            "priority": 2,
            "impact": "high",
        },
    )
    assert created_task.status_code == 201
    task_id = created_task.json()["id"]
    assert admin_client.get("/api/v1/feedback/tasks").json()[0]["feedback_report_ids"] == [
        report_id
    ]
    assert admin_client.patch(
        f"/api/v1/feedback/tasks/{task_id}", json={"status": "prioritized"}
    ).status_code == 200
    assert admin_client.patch(
        f"/api/v1/feedback/tasks/{task_id}",
        json={"status": "assigned"},
    ).status_code == 422
    assert admin_client.patch(
        f"/api/v1/feedback/tasks/{task_id}",
        json={"assigned_to_user_id": str(admin.id)},
    ).status_code == 200
    assert admin_client.patch(
        f"/api/v1/feedback/tasks/{task_id}",
        json={"status": "assigned"},
    ).status_code == 200
    outsider_client = _client(db_session, outsider)
    assert outsider_client.get("/api/v1/feedback/tasks").json() == []
