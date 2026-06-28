from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.models.request import RequestStatus
from app.services.session_service import utc_now


class RequestService:
    def __init__(self, collection: Any) -> None:
        self._collection = collection

    async def create_request(
        self,
        session_id: str,
        prompt_version: str,
        request_data: dict[str, Any],
        duplicate_key: str,
    ) -> dict[str, Any]:
        now = utc_now()
        request = {
            "request_id": str(uuid4()),
            "session_id": session_id,
            "prompt_version": prompt_version,
            "request_data": dict(request_data),
            "duplicate_key": duplicate_key,
            "status": RequestStatus.COMPLETED.value,
            "created_at": now,
            "updated_at": now,
        }
        await self._collection.insert_one(request)
        return request

    async def find_completed_by_duplicate_key(
        self,
        duplicate_key: str,
    ) -> dict[str, Any] | None:
        return await self._collection.find_one(
            {
                "duplicate_key": duplicate_key,
                "status": RequestStatus.COMPLETED.value,
            }
        )

    async def update_existing_request(
        self,
        request_id: str,
        session_id: str,
        prompt_version: str,
        request_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = utc_now()
        await self._collection.update_one(
            {"request_id": request_id},
            {
                "$set": {
                    "session_id": session_id,
                    "prompt_version": prompt_version,
                    "request_data": dict(request_data),
                    "status": RequestStatus.COMPLETED.value,
                    "updated_at": now,
                }
            },
        )
        return await self._collection.find_one({"request_id": request_id})

