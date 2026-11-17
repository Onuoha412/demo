from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
import sentry_sdk

from .api.routes.auth import router as auth_router
from .api.routes.appointments import (
    admin_router as appointment_admin_router,
    customer_router as appointment_customer_router,
)
from .api.routes.catalog import router as catalog_router
from .api.routes.customers import router as customer_router
from .api.routes.health import router as health_router
from .api.routes.queues import entry_router, router as queue_router
from .api.routes.queue_requests import router as queue_requests_router
from .api.routes.staff import router as staff_router
from .api.routes.admin import router as admin_router
from .api.routes.organization_announcements import (
    router as organization_announcements_router,
)
from .api.routes.migrations import router as migrations_router
from .api.routes.ai import router as ai_router
from .api.routes.notifications import router as notifications_router
from .api.routes.feedback import router as feedback_router
from .api.routes.super_admin import router as super_admin_router
from .api.routes.operations import router as operations_router
from .api.routes.time import router as time_router
from .api.routes.scheduler import router as scheduler_router
from .websocket.routes import router as websocket_router
from .config import settings
from .db.session import SessionLocal
from .models import PlatformSettings
from .observability import configure_sentry
from .services.cache import cache
from .services.database_backup import (
    create_database_backup,
    prune_database_backups,
)
from .services.realtime import realtime
from .services.outbox import claim as claim_outbox
from .services.outbox import mark_failed as mark_outbox_failed
from .services.outbox import mark_published as mark_outbox_published
from .services.jobs import worker_loop

logger = logging.getLogger(__name__)


def _claim_outbox_event():
    with SessionLocal() as session:
        return claim_outbox(session)


def _mark_outbox_published(event_id):
    with SessionLocal() as session:
        mark_outbox_published(session, event_id)


def _mark_outbox_failed(event_id, error):
    with SessionLocal() as session:
        mark_outbox_failed(session, event_id, error)


async def _scheduled_sqlite_backups() -> None:
    interval_seconds = settings.database_backup_interval_hours * 60 * 60
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            backup = await asyncio.to_thread(
                create_database_backup,
                settings.database_url,
                settings.database_backup_dir,
            )
            removed = await asyncio.to_thread(
                prune_database_backups,
                settings.database_backup_dir,
                keep=settings.database_backup_retention_count,
            )
        except (OSError, ValueError):
            logger.exception("Scheduled QueueLess SQLite backup failed")
        else:
            logger.info(
                "Scheduled QueueLess SQLite backup completed",
                extra={
                    "backup_filename": backup.name,
                    "retained_backups": (
                        settings.database_backup_retention_count
                    ),
                    "removed_backups": len(removed),
                },
            )


async def _outbox_worker() -> None:
    while True:
        event = None
        try:
            event = await asyncio.to_thread(_claim_outbox_event)
            if event is None:
                await asyncio.sleep(0.25)
                continue
            if event.queue_id is not None:
                await realtime.publish(
                    event.queue_id,
                    event.event_type,
                    {
                        "event_id": str(event.id),
                        "event_version": event.event_version,
                        "event_sequence": event.sequence_number,
                        **event.payload,
                    },
                )
            await asyncio.to_thread(_mark_outbox_published, event.id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if event is not None:
                await asyncio.to_thread(_mark_outbox_failed, event.id, str(error))
            else:
                logger.exception("QueueLess outbox worker failed before claiming an event")
                await asyncio.sleep(1)


def create_app() -> FastAPI:
    production = settings.environment == "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await realtime.start()
        backup_task: asyncio.Task[None] | None = None
        outbox_task = asyncio.create_task(_outbox_worker())
        scheduled_job_task = asyncio.create_task(worker_loop())
        database_url = make_url(settings.database_url)
        if (
            settings.database_backup_interval_hours > 0
            and database_url.get_backend_name() == "sqlite"
            and database_url.database not in {None, "", ":memory:"}
        ):
            backup_task = asyncio.create_task(_scheduled_sqlite_backups())
        try:
            yield
        finally:
            outbox_task.cancel()
            try:
                await outbox_task
            except asyncio.CancelledError:
                pass
            scheduled_job_task.cancel()
            try:
                await scheduled_job_task
            except asyncio.CancelledError:
                pass
            if backup_task is not None:
                backup_task.cancel()
                try:
                    await backup_task
                except asyncio.CancelledError:
                    pass
            await realtime.stop()
            await cache.close()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=500)

    @application.middleware("http")
    async def broadcast_successful_writes(request: Request, call_next) -> Response:
        response = await call_next(request)
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/api/v1/")
            and not request.url.path.endswith("-ws-ticket")
            and 200 <= response.status_code < 300
        ):
            realtime.publish_app_change_nowait()
        return response

    @application.middleware("http")
    async def capture_server_errors(request: Request, call_next) -> Response:
        if (
            production
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/api/")
        ):
            origin = request.headers.get("origin")
            configured_origins = {
                value.strip() for value in settings.allowed_origins.split(",")
            }
            if origin is not None and origin not in configured_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request origin is not allowed."},
                )
        response = await call_next(request)
        if response.status_code >= 500:
            route = request.scope.get("route")
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("http.status_code", str(response.status_code))
                if route is not None:
                    scope.set_tag("http.route", route.path)
                sentry_sdk.capture_message(
                    "QueueLess API returned a server error",
                    level="error",
                )
        return response

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")
        if production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000",
            )
        return response

    @application.middleware("http")
    async def maintenance_gate(request: Request, call_next) -> Response:
        path = request.url.path
        allowed_during_maintenance = (
            path in {"/health", "/api/v1/health", "/api/v1/system-status"}
            or path.startswith("/api/v1/super-admin/")
            or (path == "/api/v1/auth/login" and request.method == "POST")
        )
        if request.method != "OPTIONS" and not allowed_during_maintenance:
            try:
                with SessionLocal() as db:
                    platform_settings = db.get(PlatformSettings, 1)
            except OperationalError as error:
                if "no such table: platform_settings" not in str(error).lower():
                    raise
                logger.warning(
                    "Maintenance gate skipped because platform_settings is unavailable"
                )
                platform_settings = None
            if platform_settings is not None and platform_settings.maintenance_mode:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": platform_settings.maintenance_message,
                        "code": "maintenance_mode",
                    },
                    headers={"Retry-After": "300"},
                )
        return await call_next(request)

    application.include_router(health_router)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(catalog_router, prefix="/api/v1")
    application.include_router(customer_router, prefix="/api/v1")
    application.include_router(appointment_customer_router, prefix="/api/v1")
    application.include_router(appointment_admin_router, prefix="/api/v1")
    application.include_router(queue_router, prefix="/api/v1")
    application.include_router(queue_requests_router, prefix="/api/v1")
    application.include_router(entry_router, prefix="/api/v1")
    application.include_router(staff_router, prefix="/api/v1")
    application.include_router(organization_announcements_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    application.include_router(migrations_router, prefix="/api/v1")
    application.include_router(super_admin_router, prefix="/api/v1")
    application.include_router(ai_router, prefix="/api/v1")
    application.include_router(notifications_router, prefix="/api/v1")
    application.include_router(feedback_router, prefix="/api/v1")
    application.include_router(operations_router, prefix="/api/v1")
    application.include_router(time_router, prefix="/api/v1")
    application.include_router(scheduler_router, prefix="/api/v1")
    application.include_router(websocket_router)

    return application


configure_sentry()
app = create_app()
