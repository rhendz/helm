class LLMError(Exception):
    """Base error for llm package."""


class LLMTimeoutError(LLMError):
    """Raised when model invocation times out."""


class LLMRequestError(LLMError):
    """Raised when model invocation fails for a non-timeout reason."""


class LLMResponseFormatError(LLMError):
    """Raised when a model response cannot be parsed as the expected structure."""
