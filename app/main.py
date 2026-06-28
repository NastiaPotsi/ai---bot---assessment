from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import Settings
from app.services.container import AppContainer, build_app_container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not hasattr(app.state, "container"):
        app.state.container = await build_app_container(Settings.from_env())

    try:
        yield
    finally:
        app.state.container.close()


def create_app(container: AppContainer | None = None) -> FastAPI:
    app = FastAPI(
        title="Engineering Service Desk Chatbot",
        version="1.0.0",
        lifespan=lifespan,
    )
    if container:
        app.state.container = container
    app.include_router(router)
    return app


app = create_app()

