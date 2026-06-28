from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    mongo_uri: str
    mongo_database: str
    llm_provider: str
    openai_api_key: str | None
    openai_model: str
    duplicate_secret: str
    prompt_config_path: Path
    # Optional: Azure OpenAI
    azure_openai_api_key: str | None = field(default=None)
    azure_openai_endpoint: str | None = field(default=None)
    azure_openai_deployment: str = field(default="gpt-4o-mini")
    azure_openai_api_version: str = field(default="2024-12-01-preview")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "Engineering Service Desk Chatbot"),
            environment=os.getenv("ENVIRONMENT", "local"),
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_database=os.getenv("MONGO_DATABASE", "engineering_service_desk"),
            llm_provider=os.getenv("LLM_PROVIDER", "fake").lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            duplicate_secret=os.getenv("DUPLICATE_SECRET", "dev-only-change-me"),
            prompt_config_path=Path(os.getenv("PROMPT_CONFIG_PATH", "config/prompts.yaml")),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY") or None,
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or None,
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )


@dataclass(frozen=True)
class PromptConfig:
    prompt_version: str
    request_extraction_prompt: str
    identity_extraction_prompt: str
    assistant_response_prompt: str
    required_request_fields: list[str]
    required_identity_fields: list[str]
    allowed_request_types: list[str]
    allowed_target_environments: list[str]
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptConfig":
        prompts = data.get("prompts", {})
        required_fields = data.get("required_fields", {})
        allowed_values = data.get("allowed_values", {})

        return cls(
            prompt_version=str(data["prompt_version"]),
            request_extraction_prompt=str(prompts["request_extraction"]),
            identity_extraction_prompt=str(prompts["identity_extraction"]),
            assistant_response_prompt=str(prompts["assistant_response"]),
            required_request_fields=list(required_fields["request"]),
            required_identity_fields=list(required_fields["identity"]),
            allowed_request_types=list(allowed_values["request_type"]),
            allowed_target_environments=list(allowed_values["target_environment"]),
            raw=data,
        )


def load_prompt_config(path: Path) -> PromptConfig:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Prompt config at {path} must be a YAML mapping.")
    return PromptConfig.from_dict(data)
