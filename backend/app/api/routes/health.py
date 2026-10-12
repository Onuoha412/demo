from fastapi import HTTPException, status
from fastapi import APIRouter
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from ...config import settings
from ...db.session import engine
from ...schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service=settings.app_name)


@router.get("/ready")
async def readiness() -> dict[str, str]:
    try:
        await run_in_threadpool(_check_database)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return {"status": "ready", "service": settings.app_name}


def _check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
