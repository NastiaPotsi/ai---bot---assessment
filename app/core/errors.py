class AppError(Exception):
    """Base application exception."""


class SessionNotFoundError(AppError):
    """Raised when a conversation session cannot be found."""


class LLMResponseError(AppError):
    """Raised when an LLM response cannot be parsed or validated."""


class UnsupportedLLMProviderError(AppError):
    """Raised when LLM_PROVIDER is not supported."""


class WorkflowStateError(AppError):
    """Raised when the conversation workflow reaches an impossible state."""

