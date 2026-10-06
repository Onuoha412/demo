from app.models.entities import QueueEntryStatus, QueueStatus, UserRole


def test_required_enum_values() -> None:
    assert {member.value for member in UserRole} == {"customer", "staff", "admin"}
    assert {member.value for member in QueueStatus} == {"open", "paused", "closed"}
    assert {member.value for member in QueueEntryStatus} == {
        "waiting",
        "called",
        "serving",
        "completed",
        "skipped",
        "cancelled",
    }
