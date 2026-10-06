from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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


app = create_app()
