class AIProviderError(RuntimeError):
    """Base class for expected AI provider failures."""


class MissingApiKeyError(AIProviderError):
    """Raised when OpenAI is selected without a configured API key."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when the selected provider is unreachable or disabled."""


class AIProviderTimeoutError(AIProviderUnavailableError):
    """Raised when a provider request times out."""


class MalformedAIResponseError(AIProviderError):
    """Raised when provider output cannot be converted into a typed schema."""
