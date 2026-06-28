from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import PromptConfig, Settings
from app.core.errors import LLMResponseError, UnsupportedLLMProviderError


class BaseLLMClient(ABC):
    @abstractmethod
    async def extract_request_details(
        self,
        message: str,
        existing_data: dict[str, Any],
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def extract_identity_details(
        self,
        message: str,
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def generate_assistant_response(
        self,
        response_type: str,
        context: dict[str, Any],
        fallback_message: str,
        prompt_config: PromptConfig,
    ) -> str:
        raise NotImplementedError


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def extract_request_details(
        self,
        message: str,
        existing_data: dict[str, Any],
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        user_payload = {
            "message": message,
            "existing_partial_request_data": existing_data,
            "allowed_values": {
                "request_type": prompt_config.allowed_request_types,
                "target_environment": prompt_config.allowed_target_environments,
            },
            "required_fields": prompt_config.required_request_fields,
        }
        return await self._extract_json(
            prompt_config.request_extraction_prompt,
            user_payload,
        )

    async def extract_identity_details(
        self,
        message: str,
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        user_payload = {
            "message": message,
            "required_fields": prompt_config.required_identity_fields,
        }
        return await self._extract_json(
            prompt_config.identity_extraction_prompt,
            user_payload,
        )

    async def generate_assistant_response(
        self,
        response_type: str,
        context: dict[str, Any],
        fallback_message: str,
        prompt_config: PromptConfig,
    ) -> str:
        user_payload = {
            "response_type": response_type,
            "safe_context": context,
            "fallback_message": fallback_message,
        }
        parsed = await self._extract_json(
            prompt_config.assistant_response_prompt,
            user_payload,
            temperature=0.2,
        )
        message = parsed.get("message")
        if not isinstance(message, str) or not message.strip():
            return fallback_message
        return message.strip()

    async def _extract_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        temperature: float = 0,
    ) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMResponseError("LLM returned an empty response.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError("LLM returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise LLMResponseError("LLM JSON response must be an object.")
        return parsed


class FakeLLMClient(BaseLLMClient):
    """Deterministic extractor used for tests and local demos."""

    async def extract_request_details(
        self,
        message: str,
        existing_data: dict[str, Any],
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        extracted: dict[str, Any] = {
            "request_type": existing_data.get("request_type"),
            "target_environment": existing_data.get("target_environment"),
            "justification": existing_data.get("justification"),
        }
        text = message.lower()

        for request_type in prompt_config.allowed_request_types:
            if request_type in text or request_type.replace("-", " ") in text:
                extracted["request_type"] = request_type
                break

        for environment in prompt_config.allowed_target_environments:
            if re.search(rf"\b{re.escape(environment)}\b", text):
                extracted["target_environment"] = environment
                break

        justification = self._extract_justification(message)
        if justification:
            extracted["justification"] = justification

        missing_fields = [
            field for field in prompt_config.required_request_fields if not extracted.get(field)
        ]
        extracted.update(
            {
                "missing_fields": missing_fields,
                "valid": not missing_fields,
                "message": "",
            }
        )
        return extracted

    async def extract_identity_details(
        self,
        message: str,
        prompt_config: PromptConfig,
    ) -> dict[str, Any]:
        requester_name = self._extract_name(message)
        employee_id = self._extract_employee_id(message)

        extracted: dict[str, Any] = {
            "requester_name": requester_name,
            "employee_id": employee_id,
        }
        missing_fields = [
            field for field in prompt_config.required_identity_fields if not extracted.get(field)
        ]
        extracted.update(
            {
                "missing_fields": missing_fields,
                "valid": not missing_fields,
                "message": "",
            }
        )
        return extracted

    async def generate_assistant_response(
        self,
        response_type: str,
        context: dict[str, Any],
        fallback_message: str,
        prompt_config: PromptConfig,
    ) -> str:
        return fallback_message

    def _extract_justification(self, message: str) -> str | None:
        patterns = [
            r"\bbecause\b(?P<value>.+)$",
            r"\bjustification(?: is|:)?\s*(?P<value>.+)$",
            r"\bpriority(?: is|:)?\s*(?P<value>.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                value = match.group("value").strip(" .")
                return value or None
        return None

    def _extract_name(self, message: str) -> str | None:
        patterns = [
            r"\bmy name is\s+(?P<value>[A-Za-z][A-Za-z .,'-]*?)(?:\s+and\b|,|\.|$)",
            r"\bi am\s+(?P<value>[A-Za-z][A-Za-z .,'-]*?)(?:\s+and\b|,|\.|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return re.sub(r"\s+", " ", match.group("value")).strip()
        return None

    def _extract_employee_id(self, message: str) -> str | None:
        patterns = [
            r"\bemployee\s*(?:id|number)?\s*(?:is|:)?\s*(?P<value>[A-Za-z0-9._-]+)",
            r"\bid\s*(?:is|:)?\s*(?P<value>[A-Za-z0-9._-]+)",
            r"^\s*(?P<value>[A-Za-z0-9._-]{2,})\s*$",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return match.group("value").strip()
        return None


class AzureOpenAILLMClient(OpenAILLMClient):
    def __init__(
        self,
        api_key: str | None,
        endpoint: str | None,
        deployment: str,
        api_version: str,
    ) -> None:
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required when LLM_PROVIDER=azure.")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required when LLM_PROVIDER=azure.")

        from openai import AsyncAzureOpenAI

        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self._model = deployment


def build_llm_client(settings: Settings) -> BaseLLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()
    if settings.llm_provider == "openai":
        return OpenAILLMClient(settings.openai_api_key, settings.openai_model)
    if settings.llm_provider == "azure":
        return AzureOpenAILLMClient(
            settings.azure_openai_api_key,
            settings.azure_openai_endpoint,
            settings.azure_openai_deployment,
            settings.azure_openai_api_version,
        )
    raise UnsupportedLLMProviderError(f"Unsupported LLM_PROVIDER={settings.llm_provider}")
