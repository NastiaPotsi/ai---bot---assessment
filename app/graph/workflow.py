from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import PromptConfig
from app.graph import nodes
from app.graph.state import ConversationState
from app.services.duplicate_service import DuplicateService
from app.services.llm_service import BaseLLMClient
from app.services.request_service import RequestService
from app.services.session_service import SessionService


class ConversationWorkflow:
    def __init__(
        self,
        session_service: SessionService,
        request_service: RequestService,
        duplicate_service: DuplicateService,
        llm_client: BaseLLMClient,
        prompt_config: PromptConfig,
    ) -> None:
        self._graph = self._build_graph(
            session_service,
            request_service,
            duplicate_service,
            llm_client,
            prompt_config,
        )

    async def run(self, session_id: str, message: str) -> dict[str, Any]:
        return await self._graph.ainvoke(
            {
                "session_id": session_id,
                "user_message": message,
                "response_ready": False,
            }
        )

    def _build_graph(
        self,
        session_service: SessionService,
        request_service: RequestService,
        duplicate_service: DuplicateService,
        llm_client: BaseLLMClient,
        prompt_config: PromptConfig,
    ) -> Any:
        graph = StateGraph(ConversationState)

        async def load(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.load_session_state(state, session_service)

        async def extract_request(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.extract_request_details(state, llm_client, prompt_config)

        async def validate_request(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.validate_request_details_node(
                state,
                session_service,
                prompt_config,
            )

        async def extract_identity(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.extract_identity_details(state, llm_client, prompt_config)

        async def validate_identity(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.validate_identity_details_node(
                state,
                session_service,
                prompt_config,
            )

        async def check_duplicate(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.duplicate_check(state, session_service, duplicate_service)

        async def save_request(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.save_or_update_request(
                state,
                session_service,
                request_service,
                prompt_config,
            )

        async def respond(state: dict[str, Any]) -> dict[str, Any]:
            return await nodes.generate_response(
                state,
                session_service,
                llm_client,
                prompt_config,
            )

        graph.add_node("load_session_state", load)
        graph.add_node("extract_request_details", extract_request)
        graph.add_node("validate_request_details", validate_request)
        graph.add_node("extract_identity_details", extract_identity)
        graph.add_node("validate_identity_details", validate_identity)
        graph.add_node("duplicate_check", check_duplicate)
        graph.add_node("save_or_update_request", save_request)
        graph.add_node("generate_response", respond)

        graph.add_edge(START, "load_session_state")
        graph.add_edge("load_session_state", "extract_request_details")
        graph.add_edge("extract_request_details", "validate_request_details")
        graph.add_edge("validate_request_details", "extract_identity_details")
        graph.add_edge("extract_identity_details", "validate_identity_details")
        graph.add_edge("validate_identity_details", "duplicate_check")
        graph.add_edge("duplicate_check", "save_or_update_request")
        graph.add_edge("save_or_update_request", "generate_response")
        graph.add_edge("generate_response", END)

        return graph.compile()
