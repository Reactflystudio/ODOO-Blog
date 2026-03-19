"""
Provider OpenAI (GPT-4o).

Implementação concreta do provedor OpenAI com suporte a
chat completions, structured output e retry logic.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from providers.llm_provider import LLMProviderBase, LLMResponse
from utils.logger import get_logger

logger = get_logger("openai_provider")

# Pricing per 1M tokens (approximate, GPT-4o)
_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}


class OpenAIProvider(LLMProviderBase):
    """Provedor OpenAI para geração de conteúdo."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_retries: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(api_key, model, max_retries, temperature, max_tokens)
        self._client: Optional[Any] = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self) -> Any:
        """Retorna ou cria o cliente OpenAI."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calcula o custo estimado da chamada."""
        pricing = _PRICING.get(self.model, _PRICING["gpt-4o"])
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Gera conteúdo usando OpenAI Chat Completions.

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt para contexto.
            temperature: Override de temperatura.
            max_tokens: Override de max tokens.

        Returns:
            LLMResponse com o conteúdo gerado.
        """
        client = self._get_client()
        start_time = time.monotonic()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                **kwargs,
            )

            choice = response.choices[0]
            usage = response.usage

            llm_response = LLMResponse(
                content=choice.message.content or "",
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                cost_usd=self._calculate_cost(
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                ),
                latency_seconds=round(time.monotonic() - start_time, 2),
                finish_reason=choice.finish_reason or "",
                raw_response=response,
                success=True,
            )

            self._track_usage(llm_response)
            return llm_response

        except Exception as exc:
            latency = round(time.monotonic() - start_time, 2)
            logger.error(
                "openai_generate_error",
                error=str(exc),
                model=self.model,
                latency_s=latency,
            )
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Gera conteúdo estruturado (JSON) usando OpenAI.

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt.
            response_format: Formato de resposta esperado.

        Returns:
            LLMResponse com conteúdo JSON.
        """
        client = self._get_client()
        start_time = time.monotonic()

        messages: list[dict[str, str]] = []
        effective_system = system_prompt or "You are a helpful assistant that responds in valid JSON."
        messages.append({"role": "system", "content": effective_system})
        messages.append({"role": "user", "content": prompt})

        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **kwargs,
        }

        if response_format:
            create_kwargs["response_format"] = response_format
        else:
            create_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**create_kwargs)

            choice = response.choices[0]
            usage = response.usage
            content = choice.message.content or "{}"

            # Validate JSON
            try:
                json.loads(content)
            except json.JSONDecodeError:
                logger.warning("openai_invalid_json", content_preview=content[:200])
                # Try to extract JSON from the response
                json_match = _extract_json(content)
                if json_match:
                    content = json_match

            llm_response = LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                cost_usd=self._calculate_cost(
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                ),
                latency_seconds=round(time.monotonic() - start_time, 2),
                finish_reason=choice.finish_reason or "",
                raw_response=response,
                success=True,
            )

            self._track_usage(llm_response)
            return llm_response

        except Exception as exc:
            logger.error("openai_structured_error", error=str(exc))
            raise

    async def health_check(self) -> bool:
        """Verifica se a API OpenAI está acessível."""
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception as exc:
            logger.error("openai_health_check_failed", error=str(exc))
            return False


def _extract_json(text: str) -> str:
    """Tenta extrair JSON de um texto."""
    import re
    # Try to find JSON block in markdown code fence
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try to find raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            json.loads(match.group(0))
            return match.group(0)
        except json.JSONDecodeError:
            pass
    return text
