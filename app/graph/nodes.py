from __future__ import annotations

from typing import Any

from app.core.config import PromptConfig
from app.core.errors import LLMResponseError, SessionNotFoundError, WorkflowStateError
from app.models.session import ConversationStep, SessionStatus
from app.services.duplicate_service import DuplicateService
from app.services.llm_service import BaseLLMClient
from app.services.request_service import RequestService
from app.services.session_service import SessionService
from app.services.validators import validate_identity_details, validate_request_details


USER_MESSAGE_PLACEHOLDER = "[redacted user message]"
DUPLICATE_MESSAGE = (
    "A possible existing request was found. Do you want to update the existing "
    "request instead of creating a new one?"
)


async def load_session_state(
    state: dict[str, Any],
    session_service: SessionService,
) -> dict[str, Any]:
    session = await session_service.get_session(state["session_id"])
    if not session:
        raise SessionNotFoundError(f"Session {state['session_id']} was not found.")

    current_step = session.get("current_step")
    existing_messages = session.get("messages", [])
    state["is_first_message"] = len(existing_messages) == 0

    stored_message = (
        USER_MESSAGE_PLACEHOLDER
        if current_step == ConversationStep.COLLECT_IDENTITY_DETAILS.value
        else state["user_message"]
    )
    await session_service.append_message(state["session_id"], "user", stored_message)

    state["session"] = session
    state["partial_request_data"] = session.get("partial_request_data", {})
    state["partial_identity_data"] = session.get("partial_identity_data", {})
    state["current_step"] = current_step
    state["status"] = session.get("status")

    if state["status"] == SessionStatus.COMPLETED.value:
        _set_response(
            state,
            "session_already_completed",
            "This session is already completed. Please create a new session for "
            "another request.",
        )

    return state


async def extract_request_details(
    state: dict[str, Any],
    llm_client: BaseLLMClient,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state
    if state.get("current_step") != ConversationStep.COLLECT_REQUEST_DETAILS.value:
        return state

    state["request_extraction"] = await llm_client.extract_request_details(
        state["user_message"],
        state.get("partial_request_data", {}),
        prompt_config,
    )
    return state


async def validate_request_details_node(
    state: dict[str, Any],
    session_service: SessionService,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state
    if state.get("current_step") != ConversationStep.COLLECT_REQUEST_DETAILS.value:
        return state

    result = validate_request_details(
        state.get("request_extraction", {}),
        state.get("partial_request_data", {}),
        prompt_config,
    )

    if not result.valid:
        await session_service.update_session(
            state["session_id"],
            {
                "status": SessionStatus.ACTIVE.value,
                "current_step": ConversationStep.COLLECT_REQUEST_DETAILS.value,
                "partial_request_data": result.data,
                "missing_fields": result.missing_fields,
            },
        )
        state["partial_request_data"] = result.data
        state["missing_fields"] = result.missing_fields
        state["status"] = SessionStatus.ACTIVE.value
        state["current_step"] = ConversationStep.COLLECT_REQUEST_DETAILS.value
        fallback = _request_missing_message(result.missing_fields, result.errors)
        off_topic = state.get("request_extraction", {}).get("off_topic", False)

        if state.get("is_first_message"):
            greeting = (
                "Hello! I'm the Engineering Service Desk assistant. "
                "I'll help you submit an engineering request. " + fallback
            )
            # Bypass LLM so the greeting is never stripped or rewritten.
            state["assistant_response"] = greeting
            state["assistant_response_type"] = None
            state["assistant_response_context"] = {}
            state["response_ready"] = True
        elif off_topic:
            redirect = (
                "I'm the Engineering Service Desk assistant and I can only help "
                "with engineering requests. " + fallback
            )
            state["assistant_response"] = redirect
            state["assistant_response_type"] = None
            state["assistant_response_context"] = {}
            state["response_ready"] = True
        else:
            _set_response(
                state,
                "request_details_missing",
                fallback,
                {
                    "missing_fields": result.missing_fields,
                    "next_missing_field": _first_or_none(result.missing_fields),
                    "validation_errors": result.errors,
                    "safe_partial_request_data": result.data,
                },
            )
        return state

    await session_service.update_session(
        state["session_id"],
        {
            "status": SessionStatus.ACTIVE.value,
            "current_step": ConversationStep.COLLECT_IDENTITY_DETAILS.value,
            "partial_request_data": result.data,
            "partial_identity_data": {},
            "missing_fields": prompt_config.required_identity_fields,
        },
    )
    state["partial_request_data"] = result.data
    state["status"] = SessionStatus.ACTIVE.value
    state["current_step"] = ConversationStep.COLLECT_IDENTITY_DETAILS.value
    _set_response(
        state,
        "request_details_complete",
        "Thanks! Just a couple of details about you. What is your full name?",
        {
            "safe_request_data": result.data,
            "next_required_fields": prompt_config.required_identity_fields,
            "next_missing_field": prompt_config.required_identity_fields[0],
        },
    )
    return state


async def extract_identity_details(
    state: dict[str, Any],
    llm_client: BaseLLMClient,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state
    if state.get("current_step") != ConversationStep.COLLECT_IDENTITY_DETAILS.value:
        return state

    state["identity_extraction"] = await llm_client.extract_identity_details(
        state["user_message"],
        prompt_config,
    )
    return state


async def validate_identity_details_node(
    state: dict[str, Any],
    session_service: SessionService,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state
    if state.get("current_step") != ConversationStep.COLLECT_IDENTITY_DETAILS.value:
        return state

    result = validate_identity_details(
        state.get("identity_extraction", {}),
        prompt_config,
        state.get("partial_identity_data", {}),
    )

    if not result.valid:
        await session_service.update_session(
            state["session_id"],
            {
                "status": SessionStatus.ACTIVE.value,
                "current_step": ConversationStep.COLLECT_IDENTITY_DETAILS.value,
                "partial_identity_data": result.data,
                "missing_fields": result.missing_fields,
            },
        )
        state["status"] = SessionStatus.ACTIVE.value
        state["current_step"] = ConversationStep.COLLECT_IDENTITY_DETAILS.value
        state["partial_identity_data"] = result.data
        _set_response(
            state,
            "identity_details_missing",
            _identity_missing_message(result.missing_fields, result.errors),
            {
                "missing_fields": result.missing_fields,
                "next_missing_field": _first_or_none(result.missing_fields),
                "validation_errors": result.errors,
            },
        )
        return state

    state["identity_data"] = result.data
    return state


async def duplicate_check(
    state: dict[str, Any],
    session_service: SessionService,
    duplicate_service: DuplicateService,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state

    current_step = state.get("current_step")
    if current_step == ConversationStep.COLLECT_IDENTITY_DETAILS.value:
        identity_data = state.get("identity_data")
        if not identity_data:
            raise WorkflowStateError("Identity data is required before duplicate check.")

        duplicate_key, duplicate = await duplicate_service.find_duplicate(
            identity_data["requester_name"],
            identity_data["employee_id"],
        )
        state["duplicate_key"] = duplicate_key

        if duplicate:
            await session_service.update_session(
                state["session_id"],
                {
                    "status": SessionStatus.AWAITING_DUPLICATE_CONFIRMATION.value,
                    "current_step": ConversationStep.DUPLICATE_CONFIRMATION.value,
                    "missing_fields": [],
                    "duplicate_candidate_id": duplicate["request_id"],
                    "duplicate_key": duplicate_key,
                },
            )
            state["status"] = SessionStatus.AWAITING_DUPLICATE_CONFIRMATION.value
            state["current_step"] = ConversationStep.DUPLICATE_CONFIRMATION.value
            state["duplicate_candidate_id"] = duplicate["request_id"]
            _set_response(
                state,
                "duplicate_candidate_found",
                DUPLICATE_MESSAGE,
                {
                    "privacy_requirement": (
                        "Do not include requester names, employee IDs, contact "
                        "details, duplicate keys, or request IDs."
                    ),
                    "requires_confirmation": True,
                },
            )
            return state

        state["save_action"] = "create"
        return state

    if current_step == ConversationStep.DUPLICATE_CONFIRMATION.value:
        confirmation = _parse_confirmation(state["user_message"])
        if confirmation is None:
            _set_response(
                state,
                "duplicate_confirmation_invalid",
                "Please answer yes or no: do you want to update the existing "
                "request instead of creating a new one?",
                {"expected_answers": ["yes", "no"]},
            )
            return state

        if confirmation:
            state["save_action"] = "update_existing"
        else:
            state["save_action"] = "create"
        state["duplicate_key"] = state.get("session", {}).get("duplicate_key")
        state["duplicate_candidate_id"] = state.get("session", {}).get(
            "duplicate_candidate_id"
        )
        return state

    return state


async def save_or_update_request(
    state: dict[str, Any],
    session_service: SessionService,
    request_service: RequestService,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    if state.get("response_ready"):
        return state
    if not state.get("save_action"):
        return state

    session = state.get("session", {})
    request_data = state.get("partial_request_data") or session.get(
        "partial_request_data",
        {},
    )
    duplicate_key = state.get("duplicate_key") or session.get("duplicate_key")
    if not duplicate_key:
        raise WorkflowStateError("Duplicate key is required before saving a request.")

    if state["save_action"] == "update_existing":
        duplicate_candidate_id = state.get("duplicate_candidate_id")
        if not duplicate_candidate_id:
            raise WorkflowStateError("Duplicate candidate is required for update.")

        request = await request_service.update_existing_request(
            duplicate_candidate_id,
            state["session_id"],
            prompt_config.prompt_version,
            request_data,
        )
        if not request:
            raise WorkflowStateError("Duplicate candidate request no longer exists.")
        response_type = "request_updated"
        response = (
            "Your existing request has been updated successfully. "
            "Thank you — our engineering team will be in touch. "
            "This session is now closed."
        )
    else:
        request = await request_service.create_request(
            state["session_id"],
            prompt_config.prompt_version,
            request_data,
            duplicate_key,
        )
        response_type = "request_created"
        response = (
            "Your engineering request has been submitted successfully. "
            "Thank you — our engineering team will review it shortly. "
            "This session is now closed."
        )

    await session_service.complete_session(state["session_id"], request["request_id"])
    state["request_id"] = request["request_id"]
    state["status"] = SessionStatus.COMPLETED.value
    state["current_step"] = ConversationStep.COMPLETED.value
    _set_response(
        state,
        response_type,
        response,
        {
            "safe_request_data": request_data,
            "session_closed": True,
        },
    )
    return state


async def generate_response(
    state: dict[str, Any],
    session_service: SessionService,
    llm_client: BaseLLMClient,
    prompt_config: PromptConfig,
) -> dict[str, Any]:
    fallback_response = state.get("assistant_response") or (
        "I could not process that message. Please try again."
    )
    response = fallback_response
    response_type = state.get("assistant_response_type")
    if response_type:
        try:
            response = await llm_client.generate_assistant_response(
                response_type,
                state.get("assistant_response_context", {}),
                fallback_response,
                prompt_config,
            )
        except LLMResponseError:
            response = fallback_response

    state["assistant_response"] = response
    await session_service.append_message(state["session_id"], "assistant", response)
    return state


def _set_response(
    state: dict[str, Any],
    response_type: str,
    fallback_message: str,
    context: dict[str, Any] | None = None,
) -> None:
    state["assistant_response"] = fallback_message
    state["assistant_response_type"] = response_type
    state["assistant_response_context"] = context or {}
    state["response_ready"] = True


def _request_missing_message(missing_fields: list[str], errors: list[str]) -> str:
    parts: list[str] = []
    if errors:
        parts.append(" ".join(errors))
    if missing_fields:
        parts.append(_request_field_question(missing_fields[0]))
    return " ".join(parts)


def _identity_missing_message(missing_fields: list[str], errors: list[str]) -> str:
    parts: list[str] = []
    if errors:
        parts.append(" ".join(errors))
    if missing_fields:
        parts.append(_identity_field_question(missing_fields[0]))
    return " ".join(parts)


def _request_field_question(field: str) -> str:
    if field == "request_type":
        return (
            "What type of engineering request is this? Choose one of: "
            "infrastructure-provisioning, service-deployment, access-grant, "
            "pipeline-change, or incident-fix."
        )
    if field == "target_environment":
        return "Which target environment is this for: development, staging, or production?"
    if field == "justification":
        return "What is the business justification or priority for this request?"
    return f"Please provide {field}."


def _identity_field_question(field: str) -> str:
    if field == "requester_name":
        return "What is your full name?"
    if field == "employee_id":
        return (
            "Please provide your employee ID "
            "(letters and numbers only, no spaces — e.g. EMP007 or AB99)."
        )
    return f"Please provide {field}."


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None


def _parse_confirmation(message: str) -> bool | None:
    normalized = message.strip().lower()
    yes_values = {"yes", "y", "sure", "update", "update it", "please update"}
    no_values = {"no", "n", "create new", "create a new one", "new request"}
    if normalized in yes_values:
        return True
    if normalized in no_values:
        return False
    return None
