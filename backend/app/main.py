from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware.gzip import GZipMiddleware
import sentry_sdk

from .api.routes.auth import router as auth_router
from .api.routes.catalog import router as catalog_router
from .api.routes.customers import router as customer_router
from .api.routes.health import router as health_router
from .api.routes.queues import entry_router, router as queue_router
from .api.routes.staff import router as staff_router
from .api.routes.admin import router as admin_router
from .api.routes.ai import router as ai_router
from .api.routes.notifications import router as notifications_router
from .websocket.routes import router as websocket_router
from .config import settings
from .observability import configure_sentry
from .services.cache import cache
from .services.realtime import realtime


def create_app() -> FastAPI:
    production = settings.environment == "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await realtime.start()
        try:
            yield
        finally:
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

    application.include_router(health_router)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(catalog_router, prefix="/api/v1")
    application.include_router(customer_router, prefix="/api/v1")
    application.include_router(queue_router, prefix="/api/v1")
    application.include_router(entry_router, prefix="/api/v1")
    application.include_router(staff_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    application.include_router(ai_router, prefix="/api/v1")
    application.include_router(notifications_router, prefix="/api/v1")
    application.include_router(websocket_router)

    return application


configure_sentry()
app = create_app()
