from __future__ import annotations

from typing import Any, TypedDict


class ConversationState(TypedDict, total=False):
    session_id: str
    user_message: str
    session: dict[str, Any]
    partial_request_data: dict[str, Any]
    partial_identity_data: dict[str, Any]
    current_step: str
    status: str
    request_extraction: dict[str, Any]
    identity_extraction: dict[str, Any]
    identity_data: dict[str, str]
    duplicate_key: str
    duplicate_candidate_id: str | None
    missing_fields: list[str]
    save_action: str
    request_id: str
    assistant_response: str
    assistant_response_type: str
    assistant_response_context: dict[str, Any]
    response_ready: bool
    is_first_message: bool
