from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.config import PromptConfig


@dataclass(frozen=True)
class ValidationResult:
    data: dict[str, str]
    missing_fields: list[str]
    errors: list[str]

    @property
    def valid(self) -> bool:
        return not self.missing_fields and not self.errors


def _is_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical_allowed_value(value: Any, allowed_values: list[str]) -> str | None:
    if not _is_present(value):
        return None

    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    allowed_lookup = {item.lower(): item for item in allowed_values}
    return allowed_lookup.get(normalized)


def validate_request_details(
    extracted: dict[str, Any],
    existing: dict[str, Any],
    prompt_config: PromptConfig,
) -> ValidationResult:
    data: dict[str, str] = {}
    errors: list[str] = []

    request_type = extracted.get("request_type") or existing.get("request_type")
    canonical_request_type = _canonical_allowed_value(
        request_type, prompt_config.allowed_request_types
    )
    if canonical_request_type:
        data["request_type"] = canonical_request_type
    elif _is_present(request_type):
        errors.append(
            "request_type must be one of: "
            + ", ".join(prompt_config.allowed_request_types)
        )

    target_environment = extracted.get("target_environment") or existing.get(
        "target_environment"
    )
    canonical_environment = _canonical_allowed_value(
        target_environment, prompt_config.allowed_target_environments
    )
    if canonical_environment:
        data["target_environment"] = canonical_environment
    elif _is_present(target_environment):
        errors.append(
            "target_environment must be one of: "
            + ", ".join(prompt_config.allowed_target_environments)
        )

    justification = extracted.get("justification") or existing.get("justification")
    if _is_present(justification):
        data["justification"] = str(justification).strip()

    missing_fields = [
        field for field in prompt_config.required_request_fields if field not in data
    ]
    return ValidationResult(data=data, missing_fields=missing_fields, errors=errors)


def validate_identity_details(
    extracted: dict[str, Any],
    prompt_config: PromptConfig,
    existing: dict[str, Any] | None = None,
) -> ValidationResult:
    data: dict[str, str] = {}
    errors: list[str] = []
    existing = existing or {}

    requester_name = extracted.get("requester_name") or existing.get("requester_name")
    if _is_present(requester_name):
        cleaned_name = re.sub(r"\s+", " ", str(requester_name).strip())
        if len(cleaned_name) >= 2 and re.search(r"[A-Za-z]", cleaned_name):
            data["requester_name"] = cleaned_name
        else:
            errors.append("requester_name must contain a valid name.")

    employee_id = extracted.get("employee_id") or existing.get("employee_id")
    if _is_present(employee_id):
        cleaned_employee_id = str(employee_id).strip()
        if re.fullmatch(r"[A-Za-z0-9._-]+", cleaned_employee_id):
            data["employee_id"] = cleaned_employee_id
        else:
            errors.append("employee_id may contain only letters, numbers, dot, dash, or underscore.")

    missing_fields = [
        field for field in prompt_config.required_identity_fields if field not in data
    ]
    return ValidationResult(data=data, missing_fields=missing_fields, errors=errors)
