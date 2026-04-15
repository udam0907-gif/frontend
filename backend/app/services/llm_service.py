from __future__ import annotations

import time
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.exceptions import LLMServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMResponse:
    def __init__(
        self,
        content: str,
        model_version: str,
        prompt_version: str,
        token_usage: dict[str, int],
        cached: bool = False,
    ) -> None:
        self.content = content
        self.model_version = model_version
        self.prompt_version = prompt_version
        self.token_usage = token_usage
        self.cached = cached


class LLMService:
    """
    Isolated LLM service behind a swappable interface.
    Currently backed by Anthropic Claude. Swap provider via config.
    """

    def __init__(self) -> None:
        self._provider = settings.llm_provider
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._cache_enabled = settings.prompt_cache_enabled

        if self._provider == "anthropic":
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            raise LLMServiceError(f"지원하지 않는 LLM 제공자: {self._provider}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        prompt_version: str = "unknown",
        cache_system: bool = True,
        extra_context: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """
        Call LLM with optional prompt caching for system prompts.
        Logs model_version, prompt_version, token_usage for every call.
        """
        start_time = time.monotonic()

        try:
            if self._provider == "anthropic":
                return await self._call_anthropic(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    prompt_version=prompt_version,
                    cache_system=cache_system and self._cache_enabled,
                    extra_context=extra_context or [],
                )
        except anthropic.APIError as e:
            logger.error(
                "llm_api_error",
                provider=self._provider,
                model=self._model,
                error=str(e),
            )
            raise LLMServiceError(f"LLM API 오류: {str(e)}") from e
        finally:
            elapsed = time.monotonic() - start_time
            logger.info("llm_call_completed", elapsed_sec=round(elapsed, 3))

    async def _call_anthropic(
        self,
        system_prompt: str,
        user_message: str,
        prompt_version: str,
        cache_system: bool,
        extra_context: list[dict[str, Any]],
    ) -> LLMResponse:
        # Build system with optional caching
        if cache_system:
            system: Any = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        # Build messages
        messages: list[dict[str, Any]] = []

        # Inject extra context as a cached user turn if provided
        if extra_context:
            context_text = "\n\n".join(
                f"[문서 {i+1}]\n{c['text']}" for i, c in enumerate(extra_context)
            )
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": context_text,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
            messages.append({"role": "assistant", "content": "참고 문서를 확인했습니다."})

        messages.append({"role": "user", "content": user_message})

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system,
            messages=messages,
        )

        content = response.content[0].text if response.content else ""
        usage = response.usage

        token_usage = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
        }

        cached = token_usage.get("cache_read_input_tokens", 0) > 0

        logger.info(
            "llm_usage",
            model=self._model,
            prompt_version=prompt_version,
            input_tokens=token_usage["input_tokens"],
            output_tokens=token_usage["output_tokens"],
            cache_read=token_usage["cache_read_input_tokens"],
            cache_write=token_usage["cache_creation_input_tokens"],
            cached=cached,
        )

        return LLMResponse(
            content=content,
            model_version=self._model,
            prompt_version=prompt_version,
            token_usage=token_usage,
            cached=cached,
        )


_llm_service_instance: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
