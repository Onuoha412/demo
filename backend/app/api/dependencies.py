"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator


async def request_context() -> AsyncIterator[None]:
    """Reserved dependency boundary for request-scoped services."""
    yield
