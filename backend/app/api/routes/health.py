from fastapi import HTTPException, status
from fastapi import APIRouter
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from ...config import settings
from ...db.session import engine
from ...schemas.health import HealthResponse
from ...services.cache import cache

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service=settings.app_name)


@router.get("/ready")
async def readiness() -> dict[str, str]:
    try:
        database_revision, journal_mode = await run_in_threadpool(_check_database)
        if settings.redis_url and not await cache.ping():
            raise RuntimeError("Redis health check failed")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database or shared realtime services are unavailable",
        ) from exc
    return {
        "status": "ready",
        "service": settings.app_name,
        "database_revision": database_revision,
        "journal_mode": journal_mode,
    }


def _check_database() -> tuple[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
    return str(revision), str(journal_mode).lower()
