import re
import sys
import time
from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

_MAX_RATE_LIMIT_RETRIES = 15


def _countdown(wait_sec: int, attempt: int, total: int) -> None:
    """Print a live countdown to stderr so it shows through Rich Live display."""
    for remaining in range(wait_sec, 0, -1):
        sys.stderr.write(
            f"\r\033[33m⏳ Rate limit (429) — attempt {attempt}/{total}. "
            f"Retrying in {remaining:3d}s... \033[0m"
        )
        sys.stderr.flush()
        time.sleep(1)
    sys.stderr.write("\r" + " " * 70 + "\r")  # clear the line
    sys.stderr.flush()


class NormalizedChatGoogleGenerativeAI(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI with normalized content output.

    Gemini 3 models return content as list of typed blocks.
    This normalizes to string for consistent downstream handling.
    Automatically retries on 429 RESOURCE_EXHAUSTED with the delay
    suggested by the API (retryDelay field), up to _MAX_RATE_LIMIT_RETRIES times.
    """

    def invoke(self, input, config=None, **kwargs):
        """
        Retry with automatic key + model rotation on 429 RESOURCE_EXHAUSTED.
        Rotation order: try all models for current key, then switch key and repeat.
        """
        from telegram_bot.config import GOOGLE_API_KEYS, FALLBACK_MODELS

        # Build (key, model) rotation pairs
        keys   = GOOGLE_API_KEYS if GOOGLE_API_KEYS else [None]
        models = FALLBACK_MODELS if FALLBACK_MODELS else [self.model]

        rotation = [(k, m) for k in keys for m in models]

        for attempt, (api_key, model_name) in enumerate(rotation):
            try:
                # Patch key/model for this attempt
                if api_key:
                    self.google_api_key = api_key
                if model_name:
                    self.model = model_name

                return normalize_content(super().invoke(input, config, **kwargs))

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_not_found  = "404" in err_str or "NOT_FOUND" in err_str or "no longer available" in err_str
                is_daily_exhausted = "limit: 0" in err_str or "GenerateRequestsPerDay" in err_str

                if (is_rate_limit or is_not_found) and attempt < len(rotation) - 1:
                    next_key, next_model = rotation[attempt + 1]
                    k_label = f"key…{next_key[-6:]}" if next_key else "same key"
                    m_label = next_model or "same model"
                    if is_not_found:
                        sys.stderr.write(
                            f"\r\033[33m⚡ Model {model_name} not available "
                            f"→ switching to [{m_label} / {k_label}]\033[0m\n"
                        )
                        sys.stderr.flush()
                    elif is_daily_exhausted:
                        sys.stderr.write(
                            f"\r\033[33m⚡ Daily quota exhausted for {model_name} "
                            f"→ switching to [{m_label} / {k_label}]\033[0m\n"
                        )
                        sys.stderr.flush()
                    else:
                        match = re.search(r"retry[_ ]in[^\d]*(\d+)", err_str, re.IGNORECASE)
                        wait_sec = int(match.group(1)) + 5 if match else 30
                        _countdown(wait_sec, attempt + 1, len(rotation))
                else:
                    raise


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatGoogleGenerativeAI instance."""
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in ("timeout", "max_retries", "callbacks", "http_client", "http_async_client"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Unified api_key maps to provider-specific google_api_key
        google_api_key = self.kwargs.get("api_key") or self.kwargs.get("google_api_key")
        if google_api_key:
            llm_kwargs["google_api_key"] = google_api_key

        # Map thinking_level to appropriate API param based on model
        # Gemini 3 Pro: low, high
        # Gemini 3 Flash: minimal, low, medium, high
        # Gemini 2.5: thinking_budget (0=disable, -1=dynamic)
        thinking_level = self.kwargs.get("thinking_level")
        if thinking_level:
            model_lower = self.model.lower()
            if "gemini-3" in model_lower:
                # Gemini 3 Pro doesn't support "minimal", use "low" instead
                if "pro" in model_lower and thinking_level == "minimal":
                    thinking_level = "low"
                llm_kwargs["thinking_level"] = thinking_level
            else:
                # Gemini 2.5: map to thinking_budget
                llm_kwargs["thinking_budget"] = -1 if thinking_level == "high" else 0

        return NormalizedChatGoogleGenerativeAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for Google."""
        return validate_model("google", self.model)
