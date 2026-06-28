from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    AWAITING_DUPLICATE_CONFIRMATION = "awaiting_duplicate_confirmation"
    COMPLETED = "completed"


class ConversationStep(str, Enum):
    COLLECT_REQUEST_DETAILS = "collect_request_details"
    COLLECT_IDENTITY_DETAILS = "collect_identity_details"
    DUPLICATE_CONFIRMATION = "duplicate_confirmation"
    COMPLETED = "completed"

