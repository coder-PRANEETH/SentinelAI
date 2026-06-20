"""Centralized lazy singleton registry for heavy models and SDK clients."""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

from .exceptions import ConfigurationError
from .logging_utils import get_logger, log_event

logger = get_logger(__name__)


class ModelRegistry:
    """Process-wide registry that loads heavy models and clients once."""

    _instance: Optional["ModelRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "ModelRegistry":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_once()
        return cls._instance

    def _init_once(self) -> None:
        self._resource_lock = threading.RLock()
        self._whisper_model: Any = None
        self._openai_client: Any = None
        self._gemini_configured_key: Optional[str] = None
        self._gemini_models: dict[str, Any] = {}
        self._geocoder: Any = None

    def get_whisper_model(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> Any:
        """Return a singleton Faster-Whisper model with GPU preference support."""
        with self._resource_lock:
            if self._whisper_model is not None:
                return self._whisper_model

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ConfigurationError("faster-whisper is not installed") from exc

            model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "base")
            preferred_device = device or os.getenv("WHISPER_DEVICE", "auto")
            compute_type = compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "default")
            devices = [preferred_device] if preferred_device != "auto" else ["cuda", "cpu"]

            last_error: Optional[Exception] = None
            for candidate in devices:
                try:
                    self._whisper_model = WhisperModel(
                        model_size,
                        device=candidate,
                        compute_type=compute_type,
                    )
                    log_event(
                        logger,
                        20,
                        "model_loaded",
                        "Whisper model loaded",
                        provider="faster_whisper",
                        model=model_size,
                        device=candidate,
                    )
                    return self._whisper_model
                except Exception as exc:
                    last_error = exc
                    log_event(
                        logger,
                        30,
                        "model_load_failed",
                        "Whisper model load failed",
                        provider="faster_whisper",
                        model=model_size,
                        device=candidate,
                        error=str(exc),
                    )

            raise ConfigurationError("Unable to load Whisper model") from last_error

    def get_openai_client(self) -> Any:
        """Return a singleton OpenAI client when OPENAI_API_KEY is configured."""
        with self._resource_lock:
            if self._openai_client is not None:
                return self._openai_client

            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise ConfigurationError("OPENAI_API_KEY is not configured")

            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ConfigurationError("openai is not installed") from exc

            self._openai_client = OpenAI(api_key=api_key)
            log_event(logger, 20, "client_loaded", "OpenAI client initialized", provider="openai")
            return self._openai_client

    def get_gemini_model(self, model_name: str) -> Any:
        """Return a singleton Gemini model by model name."""
        with self._resource_lock:
            if model_name in self._gemini_models:
                return self._gemini_models[model_name]

            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                raise ConfigurationError("GEMINI_API_KEY is not configured")

            try:
                import google.generativeai as genai
            except ImportError as exc:
                raise ConfigurationError("google-generativeai is not installed") from exc

            if self._gemini_configured_key != api_key:
                genai.configure(api_key=api_key)
                self._gemini_configured_key = api_key

            model = genai.GenerativeModel(model_name=model_name)
            self._gemini_models[model_name] = model
            log_event(
                logger,
                20,
                "model_loaded",
                "Gemini model initialized",
                provider="gemini",
                model=model_name,
            )
            return model

    def get_geocoder(self) -> Any:
        """Return a singleton Nominatim geocoder."""
        with self._resource_lock:
            if self._geocoder is not None:
                return self._geocoder

            try:
                from geopy.geocoders import Nominatim
            except ImportError as exc:
                raise ConfigurationError("geopy is not installed") from exc

            self._geocoder = Nominatim(
                user_agent=os.getenv("GEOCODER_USER_AGENT", "sentinelai_incident_copilot")
            )
            log_event(logger, 20, "client_loaded", "Geocoder initialized", provider="nominatim")
            return self._geocoder


def get_model_registry() -> ModelRegistry:
    """Return the process-wide model registry."""
    return ModelRegistry()
