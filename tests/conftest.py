from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, load_prompt_config
from app.db.in_memory import InMemoryAsyncCollection
from app.graph.workflow import ConversationWorkflow
from app.main import create_app
from app.services.container import AppContainer
from app.services.duplicate_service import DuplicateService
from app.services.llm_service import FakeLLMClient
from app.services.request_service import RequestService
from app.services.session_service import SessionService


@pytest.fixture
def prompt_config():
    return load_prompt_config(Path("config/prompts.yaml"))


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_name="Test Engineering Service Desk Chatbot",
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_database="test",
        llm_provider="fake",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        duplicate_secret="test-duplicate-secret",
        prompt_config_path=Path("config/prompts.yaml"),
    )


@pytest.fixture
def app_container(test_settings, prompt_config) -> AppContainer:
    session_collection = InMemoryAsyncCollection()
    request_collection = InMemoryAsyncCollection()
    session_service = SessionService(session_collection)
    request_service = RequestService(request_collection)
    duplicate_service = DuplicateService(
        request_service,
        test_settings.duplicate_secret,
    )
    llm_client = FakeLLMClient()
    workflow = ConversationWorkflow(
        session_service,
        request_service,
        duplicate_service,
        llm_client,
        prompt_config,
    )
    container = AppContainer(
        settings=test_settings,
        prompt_config=prompt_config,
        session_service=session_service,
        request_service=request_service,
        duplicate_service=duplicate_service,
        llm_client=llm_client,
        workflow=workflow,
    )
    container.session_collection = session_collection
    container.request_collection = request_collection
    return container


@pytest.fixture
async def async_client(app_container):
    app = create_app(app_container)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

