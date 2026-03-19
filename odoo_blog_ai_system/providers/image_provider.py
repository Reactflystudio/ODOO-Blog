"""
Interface abstrata para provedores de geração de imagem.

Define o contrato para geradores de imagem (DALL-E, Imagen, Stable Diffusion)
e implementação de fallback para bancos de imagens gratuitos.
"""

from __future__ import annotations

import base64
import io
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger("image_provider")


class ImageProviderBase(ABC):
    """Interface abstrata para provedores de geração de imagem."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provedor."""
        ...

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        style: str = "natural",
        quality: str = "standard",
    ) -> ImageGenerationResult:
        """
        Gera uma imagem a partir de um prompt.

        Args:
            prompt: Descrição da imagem.
            width: Largura em pixels.
            height: Altura em pixels.
            style: Estilo da imagem.
            quality: Qualidade (standard, hd).

        Returns:
            Resultado com a imagem gerada.
        """
        ...


class ImageGenerationResult:
    """Resultado da geração de uma imagem."""

    def __init__(
        self,
        success: bool = False,
        image_data: bytes = b"",
        image_url: str = "",
        local_path: str = "",
        provider: str = "",
        prompt_used: str = "",
        cost_usd: float = 0.0,
        error_message: str = "",
    ) -> None:
        self.success = success
        self.image_data = image_data
        self.image_url = image_url
        self.local_path = local_path
        self.provider = provider
        self.prompt_used = prompt_used
        self.cost_usd = cost_usd
        self.error_message = error_message

    def save_to_file(self, output_path: str, optimize: bool = True) -> str:
        """
        Salva a imagem em disco, opcionalmente otimizando.

        Args:
            output_path: Caminho de destino.
            optimize: Se deve otimizar (comprimir) a imagem.

        Returns:
            Caminho do arquivo salvo.
        """
        if not self.image_data:
            raise ValueError("Sem dados de imagem para salvar")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if optimize:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(self.image_data))

                # Convert to WebP for better compression
                webp_path = output.with_suffix(".webp")
                img.save(str(webp_path), "WEBP", quality=85, method=6)
                self.local_path = str(webp_path)
                logger.info("image_saved_webp", path=str(webp_path))
                return str(webp_path)
            except ImportError:
                logger.warning("pillow_not_available", msg="Salvando sem otimização")

        # Fallback: save raw
        output.write_bytes(self.image_data)
        self.local_path = str(output)
        return str(output)


class DALLEProvider(ImageProviderBase):
    """Provedor DALL-E 3 para geração de imagens."""

    @property
    def provider_name(self) -> str:
        return "dalle"

    async def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        style: str = "natural",
        quality: str = "standard",
    ) -> ImageGenerationResult:
        """Gera imagem usando DALL-E 3."""
        from tenacity import retry, stop_after_attempt, wait_exponential

        start_time = time.monotonic()

        # DALL-E 3 supported sizes
        size = self._get_closest_size(width, height)

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)

            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
                response_format="b64_json",
            )

            image_b64 = response.data[0].b64_json
            image_data = base64.b64decode(image_b64) if image_b64 else b""

            # Cost: $0.040 (standard), $0.080 (hd) for 1024x1024
            cost = 0.080 if quality == "hd" else 0.040

            result = ImageGenerationResult(
                success=True,
                image_data=image_data,
                provider=self.provider_name,
                prompt_used=prompt,
                cost_usd=cost,
            )

            logger.info(
                "dalle_image_generated",
                size=size,
                quality=quality,
                latency_s=round(time.monotonic() - start_time, 2),
            )
            return result

        except Exception as exc:
            logger.error("dalle_generation_failed", error=str(exc))
            return ImageGenerationResult(
                success=False,
                provider=self.provider_name,
                prompt_used=prompt,
                error_message=str(exc),
            )

    @staticmethod
    def _get_closest_size(width: int, height: int) -> str:
        """Retorna o tamanho DALL-E mais próximo."""
        if width > height:
            return "1792x1024"
        elif height > width:
            return "1024x1792"
        return "1024x1024"


class UnsplashFallback:
    """Fallback para imagens do Unsplash."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com"

    async def search_image(
        self, query: str, width: int = 1200, height: int = 630
    ) -> ImageGenerationResult:
        """
        Busca imagem no Unsplash.

        Args:
            query: Termo de busca.
            width: Largura desejada.
            height: Altura desejada.

        Returns:
            Resultado com URL da imagem.
        """
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search/photos",
                    params={
                        "query": query,
                        "per_page": 1,
                        "orientation": "landscape" if width > height else "portrait",
                    },
                    headers={"Authorization": f"Client-ID {self.api_key}"},
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("results"):
                    photo = data["results"][0]
                    image_url = photo["urls"]["regular"]

                    # Download the image
                    img_response = await client.get(image_url, timeout=30.0)
                    img_response.raise_for_status()

                    return ImageGenerationResult(
                        success=True,
                        image_data=img_response.content,
                        image_url=image_url,
                        provider="unsplash",
                        prompt_used=query,
                        cost_usd=0.0,
                    )

                return ImageGenerationResult(
                    success=False,
                    provider="unsplash",
                    prompt_used=query,
                    error_message="Nenhuma imagem encontrada no Unsplash",
                )

        except Exception as exc:
            logger.error("unsplash_search_failed", error=str(exc))
            return ImageGenerationResult(
                success=False,
                provider="unsplash",
                prompt_used=query,
                error_message=str(exc),
            )


class GoogleImagenProvider(ImageProviderBase):
    """Provedor Google Imagen para geracao de imagens via Google API (AI Studio)."""

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "imagen-3.0-generate-001"

    @property
    def provider_name(self) -> str:
        return "google_imagen"

    async def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        style: str = "realistic",
        quality: str = "standard",
    ) -> ImageGenerationResult:
        """Gera imagem usando Google Imagen 3 via API REST."""
        import httpx
        from tenacity import retry, stop_after_attempt, wait_exponential

        start_time = time.monotonic()

        # Try multiple model names if one fails
        models_to_try = [
            "imagen-3.0-generate-001",
            "imagen-3.0-alpha-generate-001",
            "imagen-3.0-fast-generate-001",
        ]

        # Imagen 3 supported aspect ratios: "1:1", "3:4", "4:3", "9:16", "16:9"
        aspect_ratio = "1:1"
        if width > height:
            aspect_ratio = "16:9" if (width / height) >= 1.5 else "4:3"
        elif height > width:
            aspect_ratio = "9:16" if (height / width) >= 1.5 else "3:4"

        last_error = ""
        for model_name in models_to_try:
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "instances": [
                            {"prompt": prompt}
                        ],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": aspect_ratio,
                        }
                    }
                    
                    # Try both v1beta and v1
                    for version in ["v1beta", "v1"]:
                        url = f"https://generativelanguage.googleapis.com/{version}/models/{model_name}:predict?key={self.api_key}"
                        response = await client.post(
                            url,
                            json=payload,
                            timeout=30.0,
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            predictions = data.get("predictions", [])
                            
                            if predictions:
                                image_b64 = predictions[0].get("bytesBase64Encoded", "")
                                if image_b64:
                                    image_data = base64.b64decode(image_b64)
                                    logger.info(
                                        "imagen_image_generated",
                                        model=model_name,
                                        version=version,
                                        aspect_ratio=aspect_ratio,
                                        latency_s=round(time.monotonic() - start_time, 2),
                                    )
                                    return ImageGenerationResult(
                                        success=True,
                                        image_data=image_data,
                                        provider=self.provider_name,
                                        prompt_used=prompt,
                                        cost_usd=0.03,
                                    )
                        
                        elif response.status_code == 404:
                            continue # Try next version or model
                        else:
                            last_error = f"HTTP {response.status_code}: {response.text}"
                            logger.warning("imagen_generation_failed_step", model=model_name, version=version, error=last_error)

            except Exception as exc:
                last_error = str(exc)
                logger.warning("imagen_generation_exception", model=model_name, error=last_error)
                continue

        return ImageGenerationResult(
            success=False,
            provider=self.provider_name,
            prompt_used=prompt,
            error_message=f"Falha em todos os modelos Imagen: {last_error}",
        )
