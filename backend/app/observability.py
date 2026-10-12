from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .config import settings

_UUID_PATH_SEGMENT = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])"
)


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    path = _UUID_PATH_SEGMENT.sub(":id", parsed.path)
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", path, "", ""))


def sanitize_sentry_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    del hint
    event.pop("user", None)
    event.pop("extra", None)
    transaction = event.get("transaction")
    if isinstance(transaction, str):
        event["transaction"] = _UUID_PATH_SEGMENT.sub(":id", transaction)
    request = event.get("request")
    if isinstance(request, dict):
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = _safe_url(url)
        for field in ("data", "cookies", "query_string", "env"):
            request.pop(field, None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: value
                for key, value in headers.items()
                if key.lower() not in {"authorization", "cookie", "set-cookie", "referer"}
            }
    spans = event.get("spans")
    for span in spans if isinstance(spans, list) else []:
        if not isinstance(span, dict):
            continue
        data = span.get("data")
        if not isinstance(data, dict):
            continue
        for key in list(data):
            normalized_key = key.lower()
            if normalized_key in {
                "authorization",
                "cookie",
                "set-cookie",
                "http.query",
                "http.request.body",
                "http.request.headers",
                "db.statement",
                "db.params",
            }:
                data.pop(key, None)
            elif normalized_key in {"url", "http.url", "url.full"} and isinstance(
                data[key], str
            ):
                data[key] = _safe_url(data[key])
    breadcrumbs = event.get("breadcrumbs")
    for breadcrumb in breadcrumbs.get("values", []) if isinstance(breadcrumbs, dict) else []:
        data = breadcrumb.get("data")
        if isinstance(data, dict):
            data.pop("data", None)
            for key in ("url", "from", "to"):
                value = data.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    data[key] = _safe_url(value)
            for key in list(data):
                if key.lower() in {"authorization", "cookie", "set-cookie"}:
                    data.pop(key, None)
    return event


def configure_sentry() -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        include_local_variables=False,
        before_send=sanitize_sentry_event,
        before_send_transaction=sanitize_sentry_event,
        integrations=[FastApiIntegration()],
    )
