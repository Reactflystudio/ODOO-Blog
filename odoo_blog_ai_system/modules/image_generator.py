"""
Módulo de Geração de Imagens com IA.

Gera imagens de capa e contextuais para artigos usando DALL-E 3,
com otimização automática (WebP), alt text SEO e upload ao Odoo.
Fallback para Unsplash se a geração IA falhar.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from config import IMAGES_DIR, ImageProvider, get_settings
from models.article import Article, ImageInfo
from providers.image_provider import DALLEProvider, GoogleImagenProvider, ImageGenerationResult, UnsplashFallback
from utils.logger import get_logger
from utils.text_processing import remove_accents, slugify

logger = get_logger("image_generator")


class ImageGenerator:
    """Gerador de imagens para artigos do blog."""

    def __init__(self, provider: Optional[ImageProvider] = None) -> None:
        self.settings = get_settings()
        self.provider = provider or self.settings.image_provider
        self.api_key_override = None
        self._dalle: Optional[DALLEProvider] = None
        self._unsplash: Optional[UnsplashFallback] = None
        self._google_imagen: Optional[GoogleImagenProvider] = None
        self._semaphore = asyncio.Semaphore(2)

    def _get_dalle(self) -> DALLEProvider:
        """Retorna o provider DALL-E."""
        if self._dalle is None:
            self._dalle = DALLEProvider(api_key=self.settings.openai_api_key)
        return self._dalle

    def _get_unsplash(self) -> UnsplashFallback:
        """Retorna o fallback Unsplash."""
        if self._unsplash is None:
            self._unsplash = UnsplashFallback(api_key=self.settings.unsplash_api_key)
        return self._unsplash

    def _get_google_imagen(self) -> GoogleImagenProvider:
        """Retorna o provider Google Imagen."""
        if self._google_imagen is None:
            api_key = self.api_key_override or self.settings.google_ai_api_key
            self._google_imagen = GoogleImagenProvider(api_key=api_key)
        return self._google_imagen

    async def generate_article_images(
        self,
        article: Article,
        cover_style: str = "modern, professional, minimalist",
        content_image_count: int = 2,
        aspect_ratio: str = "16:9",
    ) -> Article:
        """
        Gera todas as imagens para um artigo.

        Args:
            article: Artigo para gerar imagens.
            cover_style: Estilo das imagens.
            content_image_count: Número de imagens de corpo.
            aspect_ratio: Proporção das imagens.

        Returns:
            Artigo atualizado com informações das imagens.
        """
        keyword = article.metadata.keyword_primary
        title = article.title
        base_slug = article.slug or slugify(title or keyword) or "article"

        logger.info(
            "generating_images",
            article_id=article.id,
            keyword=keyword,
            count=content_image_count + 1,
        )

        # Configuração de dimensões
        width, height = 1200, 630
        if aspect_ratio == "1:1":
            width, height = 1024, 1024
        elif aspect_ratio == "4:3":
            width, height = 1024, 768

        # Generate cover image
        cover_prompt = self._build_cover_prompt(title, keyword, cover_style)
        cover_result = await self._generate_single_image(
            prompt=cover_prompt,
            filename_base=f"{base_slug}-cover",
            width=width,
            height=height,
            is_cover=True,
        )

        if cover_result.success:
            article.cover_image = ImageInfo(
                local_path=cover_result.local_path,
                url=cover_result.image_url,
                alt_text=self._generate_alt_text(title, keyword, is_cover=True),
                title_text=title,
                filename=Path(cover_result.local_path).name if cover_result.local_path else "",
                width=width,
                height=height,
                is_cover=True,
            )
            logger.info("cover_image_generated", path=cover_result.local_path)
        else:
            logger.warning("cover_image_failed", error=cover_result.error_message)

        # Generate content images
        content_prompts = self._build_content_prompts(
            title, keyword, cover_style, content_image_count
        )

        for i, prompt in enumerate(content_prompts):
            result = await self._generate_single_image(
                prompt=prompt,
                filename_base=f"{base_slug}-content-{i + 1}",
                width=width,
                height=height,
                is_cover=False,
            )

            if result.success:
                article.content_images.append(ImageInfo(
                    local_path=result.local_path,
                    url=result.image_url,
                    alt_text=self._generate_alt_text(title, keyword, index=i + 1),
                    title_text=f"{title} - Imagem {i + 1}",
                    filename=Path(result.local_path).name if result.local_path else "",
                    width=width,
                    height=height,
                    is_cover=False,
                ))

        logger.info(
            "images_generated",
            article_id=article.id,
            cover=bool(article.cover_image),
            content_count=len(article.content_images),
        )

        return article

    async def _generate_single_image(
        self,
        prompt: str,
        filename_base: str,
        width: int = 1200,
        height: int = 630,
        is_cover: bool = False,
    ) -> ImageGenerationResult:
        """Gera uma única imagem com fallback."""
        async with self._semaphore:
            # Try primary provider
            if self.provider == ImageProvider.DALLE:
                try:
                    dalle = self._get_dalle()
                    result = await dalle.generate_image(
                        prompt=prompt,
                        width=width,
                        height=height,
                    )
                    if result.success and result.image_data:
                        output_path = str(IMAGES_DIR / f"{filename_base}.png")
                        saved_path = result.save_to_file(output_path, optimize=True)
                        result.local_path = saved_path
                        return result
                except Exception as exc:
                    logger.warning("dalle_failed", error=str(exc), msg="Tentando Unsplash...")

            elif self.provider == ImageProvider.GOOGLE_IMAGEN:
                try:
                    google_imagen = self._get_google_imagen()
                    result = await google_imagen.generate_image(
                        prompt=prompt,
                        width=width,
                        height=height,
                    )
                    if result.success and result.image_data:
                        output_path = str(IMAGES_DIR / f"{filename_base}.png")
                        saved_path = result.save_to_file(output_path, optimize=True)
                        result.local_path = saved_path
                        return result
                    else:
                        logger.warning("google_imagen_returned_false", error=result.error_message)
                except Exception as exc:
                    logger.warning("google_imagen_failed", error=str(exc), msg="Tentando Unsplash...")

            # Fallback to Unsplash
            if self.settings.unsplash_api_key:
                try:
                    unsplash = self._get_unsplash()
                    search_query = remove_accents(prompt.split(",")[0][:50])
                    result = await unsplash.search_image(
                        query=search_query,
                        width=width,
                        height=height,
                    )
                    if result.success and result.image_data:
                        output_path = str(IMAGES_DIR / f"{filename_base}.png")
                        saved_path = result.save_to_file(output_path, optimize=True)
                        result.local_path = saved_path
                        return result
                except Exception as exc:
                    logger.warning("unsplash_failed", error=str(exc))

            return ImageGenerationResult(
                success=False,
                error_message="Todos os provedores de imagem falharam",
            )

    @staticmethod
    def _build_cover_prompt(title: str, keyword: str, style: str) -> str:
        """Constrói prompt para imagem de capa."""
        return (
            f"A high-quality, professional blog cover image relevant to the topic of '{keyword}'. "
            f"DETAILED INSTRUCTIONS: {style}. "
            f"The image must be photorealistic, clean, and highly relevant. "
            f"CRITICAL: Absolutely NO TEXT, NO WORDS, NO LETTERS, no watermarks, no logos in the image. "
            f"Optimized for professional web design hero sections with great lighting and depth of field."
        )

    @staticmethod
    def _build_content_prompts(
        title: str,
        keyword: str,
        style: str,
        count: int,
    ) -> list[str]:
        """Constrói prompts para imagens de conteúdo."""
        angles = [
            "showing a real-world scenario or application",
            "conceptually representing the core idea",
            "showing professionals in action",
            "abstract but grounded representation",
        ]

        prompts: list[str] = []
        for i in range(count):
            angle = angles[i % len(angles)]
            prompts.append(
                f"A high-quality editorial image about '{keyword}'. "
                f"Concept: {angle}. "
                f"DETAILED INSTRUCTIONS: {style}. "
                f"CRITICAL: Absolutely NO TEXT, NO WORDS, NO LETTERS, no watermarks, no logos. "
                f"Professional lighting, highly detailed photography or hyper-realistic illustration."
            )
        return prompts


    @staticmethod
    def _generate_alt_text(
        title: str,
        keyword: str,
        is_cover: bool = False,
        index: int = 0,
    ) -> str:
        """Gera alt text SEO-friendly para a imagem."""
        if is_cover:
            alt = f"{keyword} - {title}"
        else:
            alt = f"Ilustração sobre {keyword} - exemplo {index}"

        # Max 125 chars
        if len(alt) > 125:
            alt = alt[:122] + "..."

        return alt

    async def generate_thumbnail(
        self,
        image_path: str,
        width: int = 300,
        height: int = 200,
    ) -> str:
        """
        Gera thumbnail de uma imagem existente.

        Args:
            image_path: Caminho da imagem original.
            width: Largura do thumbnail.
            height: Altura do thumbnail.

        Returns:
            Caminho do thumbnail gerado.
        """
        try:
            from PIL import Image

            img = Image.open(image_path)
            img.thumbnail((width, height), Image.Resampling.LANCZOS)

            thumb_path = Path(image_path)
            thumb_output = thumb_path.parent / f"{thumb_path.stem}_thumb{thumb_path.suffix}"
            img.save(str(thumb_output), optimize=True, quality=80)

            logger.info("thumbnail_generated", path=str(thumb_output))
            return str(thumb_output)

        except ImportError:
            logger.warning("pillow_not_available")
            return image_path
        except Exception as exc:
            logger.error("thumbnail_error", error=str(exc))
            return image_path
