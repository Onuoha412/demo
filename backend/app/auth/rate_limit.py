import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuthRateLimit


def enforce_rate_limit(
    db: Session,
    scope: str,
    client_key: str,
    limit: int,
    window_seconds: int = 60,
) -> bool:
    digest = hashlib.sha256(
        f"{settings.jwt_secret_key}:{scope}:{client_key}".encode()
    ).hexdigest()
    bucket_key = f"{scope}:{digest}"
    now = datetime.now(timezone.utc)
    bucket = db.get(AuthRateLimit, bucket_key)
    if bucket is None:
        bucket = AuthRateLimit(
            bucket_key=bucket_key,
            count=1,
            window_started_at=now,
        )
        db.add(bucket)
        allowed = True
    else:
        started = bucket.window_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started + timedelta(seconds=window_seconds) <= now:
            bucket.count = 1
            bucket.window_started_at = now
            allowed = True
        else:
            bucket.count += 1
            allowed = bucket.count <= limit
    db.execute(
        delete(AuthRateLimit).where(
            AuthRateLimit.window_started_at < now - timedelta(days=1),
            AuthRateLimit.bucket_key != bucket_key,
        ).execution_options(synchronize_session=False)
    )
    db.commit()
    return allowed
