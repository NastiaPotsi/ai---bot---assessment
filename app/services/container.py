from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo.errors import PyMongoError

from app.core.config import PromptConfig, Settings, load_prompt_config
from app.db.mongo import create_mongo_database
from app.graph.workflow import ConversationWorkflow
from app.services.duplicate_service import DuplicateService
from app.services.llm_service import BaseLLMClient, build_llm_client
from app.services.request_service import RequestService
from app.services.session_service import SessionService


@dataclass
class AppContainer:
    settings: Settings
    prompt_config: PromptConfig
    session_service: SessionService
    request_service: RequestService
    duplicate_service: DuplicateService
    llm_client: BaseLLMClient
    workflow: ConversationWorkflow
    mongo_client: Any | None = None
    mongo_database: Any | None = None

    async def ping_database(self) -> str:
        if not self.mongo_client:
            return "in-memory"
        try:
            await self.mongo_client.admin.command("ping")
        except PyMongoError:
            return "unavailable"
        return "ok"

    def close(self) -> None:
        if self.mongo_client:
            self.mongo_client.close()


async def build_app_container(settings: Settings) -> AppContainer:
    prompt_config = load_prompt_config(settings.prompt_config_path)
    mongo_client, database = await create_mongo_database(settings)
    session_service = SessionService(database.sessions)
    request_service = RequestService(database.requests)
    duplicate_service = DuplicateService(request_service, settings.duplicate_secret)
    llm_client = build_llm_client(settings)
    workflow = ConversationWorkflow(
        session_service,
        request_service,
        duplicate_service,
        llm_client,
        prompt_config,
    )
    return AppContainer(
        settings=settings,
        prompt_config=prompt_config,
        session_service=session_service,
        request_service=request_service,
        duplicate_service=duplicate_service,
        llm_client=llm_client,
        workflow=workflow,
        mongo_client=mongo_client,
        mongo_database=database,
    )

