"""
HTTP Client com retry, proxy e rate limiting.

Fornece um cliente HTTP robusto baseado em httpx com:
- Retry automático com exponential backoff (tenacity)
- Suporte a proxy rotation
- Rate limiting configurável
- Timeouts sensatos
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings
from utils.logger import get_logger

logger = get_logger("http_client")


class RateLimiter:
    """Rate limiter baseado em token bucket."""

    def __init__(self, max_calls: int = 10, period: float = 1.0) -> None:
        """
        Args:
            max_calls: Máximo de chamadas no período.
            period: Período em segundos.
        """
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Aguarda até que uma chamada seja permitida."""
        async with self._lock:
            now = time.monotonic()
            # Remove calls fora do período
            self._calls = [t for t in self._calls if now - t < self.period]

            if len(self._calls) >= self.max_calls:
                wait_time = self.period - (now - self._calls[0])
                if wait_time > 0:
                    logger.debug("rate_limit_wait", wait_seconds=round(wait_time, 2))
                    await asyncio.sleep(wait_time)

            self._calls.append(time.monotonic())


class HttpClient:
    """Cliente HTTP assíncrono robusto com retry e rate limiting."""

    def __init__(
        self,
        base_url: str = "",
        max_retries: int = 3,
        timeout: float = 30.0,
        max_calls_per_second: int = 10,
        proxy_url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.proxy_url = proxy_url or settings.proxy_url
        self.rate_limiter = RateLimiter(max_calls=max_calls_per_second)
        self._default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if headers:
            self._default_headers.update(headers)

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna ou cria o cliente HTTP assíncrono."""
        if self._client is None or self._client.is_closed:
            transport_kwargs: dict[str, Any] = {
                "retries": self.max_retries,
            }
            if self.proxy_url:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout),
                    headers=self._default_headers,
                    follow_redirects=True,
                    proxy=self.proxy_url,
                    transport=httpx.AsyncHTTPTransport(**transport_kwargs),
                )
            else:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout),
                    headers=self._default_headers,
                    follow_redirects=True,
                    transport=httpx.AsyncHTTPTransport(**transport_kwargs),
                )
        return self._client

    async def close(self) -> None:
        """Fecha o cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Realiza GET request com retry e rate limiting.

        Args:
            url: URL ou path (se base_url configurada).
            params: Query parameters.
            headers: Headers adicionais.

        Returns:
            Resposta HTTP.

        Raises:
            httpx.HTTPStatusError: Se o status code indicar erro após retries.
        """
        await self.rate_limiter.acquire()
        client = await self._get_client()
        logger.debug("http_get", url=url)
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Realiza POST request com retry e rate limiting.

        Args:
            url: URL ou path.
            json: Body JSON.
            data: Form data.
            headers: Headers adicionais.

        Returns:
            Resposta HTTP.
        """
        await self.rate_limiter.acquire()
        client = await self._get_client()
        logger.debug("http_post", url=url)
        response = await client.post(url, json=json, data=data, headers=headers)
        response.raise_for_status()
        return response

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def download(
        self,
        url: str,
        output_path: str,
        chunk_size: int = 8192,
    ) -> str:
        """
        Faz download de um arquivo.

        Args:
            url: URL do arquivo.
            output_path: Caminho de destino.
            chunk_size: Tamanho do chunk para streaming.

        Returns:
            Caminho do arquivo baixado.
        """
        await self.rate_limiter.acquire()
        client = await self._get_client()
        logger.info("http_download", url=url, output=output_path)
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size):
                    f.write(chunk)
        return output_path

    async def __aenter__(self) -> HttpClient:
        """Context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Context manager exit."""
        await self.close()


def create_http_client(**kwargs: Any) -> HttpClient:
    """Factory para criar HttpClient com configurações padrão."""
    return HttpClient(**kwargs)
