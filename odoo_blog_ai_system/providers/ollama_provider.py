"""
Provider Ollama para geração de conteúdo local.

Implementação do provedor Ollama utilizando a API local (Docker ou Desktop).
Suporta geração de chat e conteúdos estruturados.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from providers.llm_provider import LLMProviderBase, LLMResponse
from utils.logger import get_logger
from config import get_settings

logger = get_logger("ollama_provider")


class OllamaProvider(LLMProviderBase):
    """Provedor Ollama para geração de conteúdo local."""

    def __init__(
        self,
        api_key: str = "local",
        model: str = "llama3",
        max_retries: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(api_key, model, max_retries, temperature, max_tokens)
        self.settings = get_settings()
        self.base_url = self.settings.ollama_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "ollama"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, Exception)),
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
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
        """Gera conteúdo usando Ollama Chat API."""
        start_time = time.monotonic()
        
        url = f"{self.base_url}/api/chat"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            content = data.get("message", {}).get("content", "")
            
            # Ollama doesn't provide token usage in standard chat response usually, 
            # or it's formatted differently. We'll try to extract if available.
            prompt_eval_count = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)

            llm_response = LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count,
                cost_usd=0.0, # Local is free!
                latency_seconds=round(time.monotonic() - start_time, 2),
                success=True,
                raw_response=data
            )

            self._track_usage(llm_response)
            return llm_response

        except Exception as exc:
            logger.error("ollama_generate_error", error=str(exc))
            raise

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, Exception)),
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Gera conteúdo estruturado (JSON) com Ollama."""
        start_time = time.monotonic()
        url = f"{self.base_url}/api/chat"
        
        messages = []
        system = system_prompt or "You are a helpful assistant that responds in valid JSON."
        if "JSON" not in system.upper():
             system += " Always respond in valid JSON format."
             
        messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json", # Ollama native JSON support
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            content = data.get("message", {}).get("content", "{}")
            
            # Ollama metadata
            prompt_eval_count = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)

            llm_response = LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count,
                cost_usd=0.0,
                latency_seconds=round(time.monotonic() - start_time, 2),
                success=True,
                raw_response=data
            )

            self._track_usage(llm_response)
            return llm_response

        except Exception as exc:
            logger.error("ollama_structured_error", error=str(exc))
            raise

    async def health_check(self) -> bool:
        """Verifica se o Ollama está rodando localmente."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    # Check if our model is pulled
                    models = [m["name"] for m in response.json().get("models", [])]
                    # match either llama3 or llama3:latest etc
                    has_model = any(self.model in m for m in models)
                    if not has_model:
                        logger.warning("ollama_model_not_found", model=self.model, found=models)
                    return True
                return False
        except Exception:
            return False
