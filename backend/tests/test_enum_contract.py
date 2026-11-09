from app.models.entities import (
    NotificationType,
    QueueEntryStatus,
    QueueEventType,
    QueueStatus,
    UserRole,
)


def test_required_enum_values() -> None:
    assert {member.value for member in UserRole} == {
        "customer",
        "staff",
        "admin",
        "super_admin",
    }
    assert {member.value for member in QueueStatus} == {"open", "paused", "closed"}
    assert "closed" in {member.value for member in QueueEventType}
    assert "queue_closed" in {member.value for member in NotificationType}
    assert {member.value for member in QueueEntryStatus} == {
        "waiting",
        "called",
        "serving",
        "completed",
        "skipped",
        "cancelled",
    }
