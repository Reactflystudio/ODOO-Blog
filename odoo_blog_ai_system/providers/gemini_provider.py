"""
Provider Google Gemini.

Implementação concreta do provedor Google Gemini com suporte a
geração de texto e conteúdo estruturado.
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

logger = get_logger("gemini_provider")

# Pricing per 1M tokens (approximate)
_PRICING = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-pro": {"input": 1.25, "output": 5.00},
}


class GeminiProvider(LLMProviderBase):
    """Provedor Google Gemini para geração de conteúdo."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_retries: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(api_key, model, max_retries, temperature, max_tokens)
        self._client: Optional[Any] = None
        self._model_instance: Optional[Any] = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_client(self) -> Any:
        """Retorna ou cria o cliente Gemini."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai
            self._model_instance = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                },
            )
        return self._client

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calcula o custo estimado."""
        pricing = _PRICING.get(self.model, _PRICING.get("gemini-2.5-flash", {"input": 0.15, "output": 0.60}))
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
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
        Gera conteúdo usando Google Gemini.

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt para contexto.
            temperature: Override de temperatura.
            max_tokens: Override de max tokens.

        Returns:
            LLMResponse com o conteúdo gerado.
        """
        self._get_client()
        start_time = time.monotonic()

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        try:
            # Create model with overrides if needed
            gen_config: dict[str, Any] = {}
            if temperature is not None:
                gen_config["temperature"] = temperature
            if max_tokens is not None:
                gen_config["max_output_tokens"] = max_tokens

            if gen_config:
                import google.generativeai as genai
                model = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config={
                        "temperature": temperature or self.temperature,
                        "max_output_tokens": max_tokens or self.max_tokens,
                        **gen_config,
                    },
                )
            else:
                model = self._model_instance

            response = await model.generate_content_async(full_prompt)

            content = ""
            if response.text:
                content = response.text

            # Extract token counts from usage metadata
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            llm_response = LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=self._calculate_cost(prompt_tokens, completion_tokens),
                latency_seconds=round(time.monotonic() - start_time, 2),
                finish_reason="stop",
                raw_response=response,
                success=True,
            )

            self._track_usage(llm_response)
            return llm_response

        except Exception as exc:
            latency = round(time.monotonic() - start_time, 2)
            logger.error(
                "gemini_generate_error",
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
        Gera conteúdo estruturado (JSON) usando Gemini.

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt.
            response_format: Formato de resposta esperado (ignorado, Gemini usa prompt).

        Returns:
            LLMResponse com conteúdo JSON.
        """
        json_system = (
            f"{system_prompt}\n\n"
            "IMPORTANTE: Responda EXCLUSIVAMENTE em JSON válido. "
            "Não inclua markdown, explicações ou texto adicional. "
            "Apenas o objeto JSON puro."
        ) if system_prompt else (
            "Responda EXCLUSIVAMENTE em JSON válido. "
            "Não inclua markdown, explicações ou texto adicional."
        )

        response = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            **kwargs,
        )

        # Clean and validate JSON
        content = response.content.strip()
        # Remove markdown code fences if present (handles leading whitespace, various patterns)
        import re
        fence_match = re.search(r"```(?:json|JSON)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
        if fence_match:
            content = fence_match.group(1).strip()
        elif content.startswith("```"):
            # Fallback: strip leading/trailing ``` lines
            lines = content.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        # Validate JSON
        try:
            json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON object between first { and last }
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                try:
                    json.loads(json_match.group(0))
                    content = json_match.group(0)
                except json.JSONDecodeError:
                    logger.warning("gemini_invalid_json", content_preview=content[:200])

        response.content = content
        return response

    async def health_check(self) -> bool:
        """Verifica se a API Gemini está funcional."""
        try:
            self._get_client()
            response = await self._model_instance.generate_content_async("ping")
            return bool(response.text)
        except Exception as exc:
            logger.error("gemini_health_check_failed", error=str(exc))
            return False
