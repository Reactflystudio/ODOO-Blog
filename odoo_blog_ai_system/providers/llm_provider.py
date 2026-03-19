"""
Interface abstrata para provedores de LLM.

Define o contrato que todos os provedores de LLM devem implementar,
com suporte a retry, rate limiting e métricas.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger("llm_provider")


@dataclass
class LLMResponse:
    """Resposta de um provedor de LLM."""
    content: str = ""
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    finish_reason: str = ""
    raw_response: Optional[Any] = None
    success: bool = True
    error_message: str = ""

    @property
    def total_cost_display(self) -> str:
        """Retorna o custo formatado."""
        return f"${self.cost_usd:.4f}"


class LLMProviderBase(ABC):
    """Interface abstrata para provedores de LLM (Strategy Pattern)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """
        Args:
            api_key: Chave da API.
            model: Nome do modelo.
            max_retries: Máximo de tentativas em caso de falha.
            temperature: Temperatura de geração (0.0-2.0).
            max_tokens: Máximo de tokens na resposta.
        """
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._call_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provedor."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Gera conteúdo a partir de um prompt.

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt (contexto/instrução).
            temperature: Override de temperatura.
            max_tokens: Override de max tokens.

        Returns:
            Resposta do LLM.
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Gera conteúdo estruturado (JSON).

        Args:
            prompt: Prompt do usuário.
            system_prompt: System prompt.
            response_format: Formato de resposta esperado.

        Returns:
            Resposta do LLM em formato estruturado.
        """
        ...

    def _track_usage(self, response: LLMResponse) -> None:
        """Rastreia métricas de uso."""
        self._call_count += 1
        self._total_tokens += response.total_tokens
        self._total_cost += response.cost_usd
        logger.info(
            "llm_call_complete",
            provider=self.provider_name,
            model=self.model,
            tokens=response.total_tokens,
            cost=response.total_cost_display,
            latency_s=round(response.latency_seconds, 2),
        )

    @property
    def usage_stats(self) -> dict[str, Any]:
        """Retorna estatísticas de uso."""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "total_calls": self._call_count,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
        }

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor está funcionando."""
        ...
