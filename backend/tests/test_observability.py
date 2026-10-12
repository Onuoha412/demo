from app.observability import sanitize_sentry_event


def test_sentry_event_sanitization_removes_auth_and_customer_data() -> None:
    event = {
        "user": {"email": "customer@example.com"},
        "extra": {"password": "not-for-monitoring"},
        "transaction": (
            "/api/v1/queue-entries/12345678-1234-5678-1234-567812345678"
        ),
        "request": {
            "url": (
                "https://api.example.com/api/v1/queue-entries/"
                "12345678-1234-5678-1234-567812345678?ticket=private"
            ),
            "data": {"password": "not-for-monitoring"},
            "cookies": {"session": "private"},
            "query_string": "token=private",
            "headers": {
                "Authorization": "Bearer private",
                "Cookie": "session=private",
                "Accept": "application/json",
            },
        },
        "breadcrumbs": {
            "values": [
                {
                    "data": {
                        "url": "https://api.example.com/api?token=private",
                        "Authorization": "Bearer private",
                    }
                }
            ]
        },
        "spans": [
            {
                "data": {
                    "http.url": (
                        "https://api.example.com/queue/"
                        "12345678-1234-5678-1234-567812345678?token=private"
                    ),
                    "http.request.body": "private",
                    "http.request.headers": {"Authorization": "Bearer private"},
                }
            }
        ],
    }

    sanitized = sanitize_sentry_event(event, {})

    assert "user" not in sanitized
    assert "extra" not in sanitized
    assert sanitized["transaction"] == "/api/v1/queue-entries/:id"
    assert sanitized["request"]["url"] == (
        "https://api.example.com/api/v1/queue-entries/:id"
    )
    assert "data" not in sanitized["request"]
    assert "cookies" not in sanitized["request"]
    assert "query_string" not in sanitized["request"]
    assert sanitized["request"]["headers"] == {"Accept": "application/json"}
    assert sanitized["breadcrumbs"]["values"][0]["data"] == {
        "url": "https://api.example.com/api"
    }
    assert sanitized["spans"][0]["data"] == {
        "http.url": "https://api.example.com/queue/:id"
    }
    assert "private" not in repr(sanitized)
