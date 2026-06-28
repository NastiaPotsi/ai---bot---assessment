from __future__ import annotations

from typing import Any

from app.core.security import create_duplicate_key
from app.services.request_service import RequestService


class DuplicateService:
    def __init__(self, request_service: RequestService, secret: str) -> None:
        self._request_service = request_service
        self._secret = secret

    def create_key(self, requester_name: str, employee_id: str) -> str:
        return create_duplicate_key(self._secret, requester_name, employee_id)

    async def find_duplicate(
        self,
        requester_name: str,
        employee_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        duplicate_key = self.create_key(requester_name, employee_id)
        duplicate = await self._request_service.find_completed_by_duplicate_key(
            duplicate_key
        )
        return duplicate_key, duplicate

