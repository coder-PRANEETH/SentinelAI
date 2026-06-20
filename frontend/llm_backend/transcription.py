"""Audio transcription via a singleton Faster-Whisper model."""

from __future__ import annotations

from pathlib import Path

from .exceptions import TranscriptionError
from .logging_utils import get_logger, log_event
from .registry import get_model_registry

logger = get_logger(__name__)


def transcribe(audio_path: str | Path) -> str:
    """Transcribe an audio file using the process-wide Whisper model."""
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError(f"Audio file does not exist: {path}")
    if not path.is_file():
        raise TranscriptionError(f"Audio path is not a file: {path}")

    try:
        model = get_model_registry().get_whisper_model()
        segments, _info = model.transcribe(str(path), language="en")
        transcript = " ".join(segment.text for segment in segments)
        result = transcript.strip()
        log_event(logger, 20, "transcription_success", "Audio transcribed", path=str(path))
        return result
    except TranscriptionError:
        raise
    except Exception as exc:
        log_event(logger, 40, "transcription_failed", "Audio transcription failed", path=str(path), error=str(exc))
        raise TranscriptionError(f"Transcription failed: {exc}") from exc


transcribe_audio_file = transcribe
