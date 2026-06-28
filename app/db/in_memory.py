from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from uuid import uuid4


class InMemoryAsyncCollection:
    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    async def create_index(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def insert_one(self, document: dict[str, Any]) -> SimpleNamespace:
        stored = deepcopy(document)
        stored.setdefault("_id", str(uuid4()))
        self._documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, filter_query: dict[str, Any]) -> dict[str, Any] | None:
        for document in self._documents:
            if self._matches(document, filter_query):
                return deepcopy(document)
        return None

    async def update_one(
        self,
        filter_query: dict[str, Any],
        update: dict[str, Any],
    ) -> SimpleNamespace:
        for index, document in enumerate(self._documents):
            if self._matches(document, filter_query):
                updated = deepcopy(document)
                self._apply_update(updated, update)
                self._documents[index] = updated
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def count_documents(self, filter_query: dict[str, Any]) -> int:
        return sum(1 for document in self._documents if self._matches(document, filter_query))

    async def all_documents(self) -> list[dict[str, Any]]:
        return deepcopy(self._documents)

    def _matches(self, document: dict[str, Any], filter_query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in filter_query.items())

    def _apply_update(self, document: dict[str, Any], update: dict[str, Any]) -> None:
        for key, value in update.get("$set", {}).items():
            document[key] = deepcopy(value)
        for key in update.get("$unset", {}):
            document.pop(key, None)
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(deepcopy(value))

