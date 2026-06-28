from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CreateSessionResponse,
    HealthResponse,
    SessionDebugResponse,
)
from app.core.errors import LLMResponseError, SessionNotFoundError, WorkflowStateError
from app.services.container import AppContainer


router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(request: Request) -> HealthResponse:
    container = _container(request)
    database_status = await container.ping_database()
    overall_status = "ok" if database_status in {"ok", "in-memory"} else "degraded"
    return HealthResponse(
        status=overall_status,
        database=database_status,
        app=container.settings.app_name,
    )


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation session",
)
async def create_session(request: Request) -> CreateSessionResponse:
    container = _container(request)
    try:
        session = await container.session_service.create_session(
            container.prompt_config.required_request_fields
        )
    except (PyMongoError, ServerSelectionTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable.",
        ) from exc

    return CreateSessionResponse(
        session_id=session["session_id"],
        status=session["status"],
    )


@router.post("/chat/{session_id}", response_model=ChatResponse, summary="Send a message and advance the conversation")
async def chat(session_id: str, payload: ChatRequest, request: Request) -> ChatResponse:
    container = _container(request)
    try:
        result = await container.workflow.run(session_id, payload.message)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid session_id.",
        ) from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned invalid structured JSON.",
        ) from exc
    except WorkflowStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (PyMongoError, ServerSelectionTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable.",
        ) from exc

    return ChatResponse(
        session_id=session_id,
        assistant_response=result["assistant_response"],
        status=result.get("status", "active"),
        current_step=result.get("current_step", "unknown"),
    )


@router.get("/sessions/{session_id}", response_model=SessionDebugResponse, summary="Inspect session state (sanitized — no personal data)")
async def get_session(session_id: str, request: Request) -> SessionDebugResponse:
    container = _container(request)
    try:
        session = await container.session_service.get_session(session_id)
    except (PyMongoError, ServerSelectionTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable.",
        ) from exc

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid session_id.",
        )

    return SessionDebugResponse(session=jsonable_encoder(_sanitize_session(session)))


def _container(request: Request) -> AppContainer:
    return request.app.state.container


def _sanitize_session(session: dict[str, Any]) -> dict[str, Any]:
    safe_session = deepcopy(session)
    safe_session.pop("_id", None)
    safe_session.pop("duplicate_key", None)

    partial_request_data = safe_session.get("partial_request_data") or {}
    safe_session["partial_request_data"] = {
        key: value
        for key, value in partial_request_data.items()
        if key not in {"requester_name", "employee_id", "contact_details"}
    }
    safe_session.pop("partial_identity_data", None)

    messages = safe_session.get("messages") or []
    safe_session["messages"] = [
        {
            "role": message.get("role"),
            "content": message.get("content"),
            "created_at": message.get("created_at"),
        }
        for message in messages
    ]
    return safe_session
