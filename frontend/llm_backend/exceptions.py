"""Custom exceptions raised by the importable LLM backend."""


class LLMBackendError(Exception):
    """Base exception for backend failures."""


class ConfigurationError(LLMBackendError):
    """Raised when an optional provider is requested but not configured."""


class ExtractionError(LLMBackendError):
    """Raised when incident field extraction fails unexpectedly."""


class TranscriptionError(LLMBackendError):
    """Raised when audio transcription fails."""


class GeocodingError(LLMBackendError):
    """Raised when location resolution fails unexpectedly."""


class VoiceSessionError(LLMBackendError):
    """Raised when a voice session cannot process a turn."""
