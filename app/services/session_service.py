from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.session import ConversationStep, SessionStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    def __init__(self, collection: Any) -> None:
        self._collection = collection

    async def create_session(self, required_request_fields: list[str]) -> dict[str, Any]:
        now = utc_now()
        session = {
            "session_id": str(uuid4()),
            "status": SessionStatus.ACTIVE.value,
            "current_step": ConversationStep.COLLECT_REQUEST_DETAILS.value,
            "partial_request_data": {},
            "partial_identity_data": {},
            "missing_fields": required_request_fields,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "duplicate_candidate_id": None,
            "duplicate_key": None,
            "messages": [],
        }
        await self._collection.insert_one(session)
        return session

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._collection.find_one({"session_id": session_id})

    async def update_session(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> None:
        updates = {**updates, "updated_at": utc_now()}
        await self._collection.update_one({"session_id": session_id}, {"$set": updates})

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        message = {
            "role": role,
            "content": content,
            "created_at": utc_now(),
        }
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": utc_now()},
            },
        )

    async def complete_session(
        self,
        session_id: str,
        request_id: str,
    ) -> None:
        now = utc_now()
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "status": SessionStatus.COMPLETED.value,
                    "current_step": ConversationStep.COMPLETED.value,
                    "completed_at": now,
                    "updated_at": now,
                    "request_id": request_id,
                }
            },
        )
