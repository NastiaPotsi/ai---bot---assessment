from __future__ import annotations

import hashlib
import hmac
import re


def normalize_requester_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return normalized


def normalize_employee_id(value: str) -> str:
    return value.strip().lower()


def create_duplicate_key(secret: str, requester_name: str, employee_id: str) -> str:
    if not secret:
        raise ValueError("DUPLICATE_SECRET must be set.")

    normalized_payload = (
        f"{normalize_requester_name(requester_name)}:"
        f"{normalize_employee_id(employee_id)}"
    )
    return hmac.new(
        secret.encode("utf-8"),
        normalized_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

