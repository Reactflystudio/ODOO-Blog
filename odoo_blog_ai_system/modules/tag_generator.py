"""
Módulo de Geração Automática de Tags.

Gera tags relevantes para artigos do blog, verifica existentes
no Odoo, faz merge de similares e normaliza slugs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from config import LLMProvider, get_settings
from models.article import Article
from providers.gemini_provider import GeminiProvider
from providers.llm_provider import LLMProviderBase
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from utils.logger import get_logger
from utils.text_processing import (
    extract_named_entities_simple,
    normalize_keyword,
    remove_accents,
    slugify,
    strip_html_tags,
)

logger = get_logger("tag_generator")


class TagGenerator:
    """Gerador automático de tags para artigos do blog."""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.settings = get_settings()
        self.provider = provider or self.settings.default_llm_provider
        self._llm: Optional[LLMProviderBase] = None
        self._existing_tags_cache: dict[str, int] = {}

    def _get_llm(self) -> LLMProviderBase:
        """Retorna o provider LLM."""
        if self._llm is None:
            api_key = self.settings.get_llm_api_key(self.provider)
            model = self.settings.get_llm_model(self.provider)
            if self.provider == LLMProvider.OPENAI:
                self._llm = OpenAIProvider(api_key=api_key, model=model, max_tokens=1024)
            elif self.provider == LLMProvider.OLLAMA:
                self._llm = OllamaProvider(model=model, max_tokens=1024)
            else:
                self._llm = GeminiProvider(api_key=api_key, model=model, max_tokens=1024)
        return self._llm

    async def generate_tags(
        self,
        article: Article,
        max_tags: int = 7,
        min_tags: int = 3,
    ) -> list[str]:
        """
        Gera tags para um artigo.

        Args:
            article: Artigo para gerar tags.
            max_tags: Número máximo de tags.
            min_tags: Número mínimo de tags.

        Returns:
            Lista de tags normalizadas.
        """
        logger.info("generating_tags", article_id=article.id, keyword=article.metadata.keyword_primary)

        # Collect tag candidates from multiple sources
        candidates: list[str] = []

        # Source 1: Keywords do artigo
        if article.metadata.keyword_primary:
            candidates.append(article.metadata.keyword_primary)
        candidates.extend(article.metadata.keywords_secondary[:5])

        # Source 2: Entidades nomeadas do texto
        plain_text = strip_html_tags(article.content_html)
        entities = extract_named_entities_simple(plain_text)
        candidates.extend(entities[:5])

        # Source 3: LLM-based tag suggestions
        try:
            llm_tags = await self._generate_tags_with_llm(article, max_tags)
            candidates.extend(llm_tags)
        except Exception as exc:
            logger.warning("llm_tag_generation_failed", error=str(exc))

        # Normalize and deduplicate
        normalized_tags = self._normalize_tags(candidates)

        # Limit count
        tags = normalized_tags[: max(max_tags, min_tags)]

        # Ensure minimum
        if len(tags) < min_tags:
            # Add from category and article type
            if article.category:
                tags.append(self._normalize_single_tag(article.category))
            if article.metadata.article_type:
                tags.append(self._normalize_single_tag(article.metadata.article_type))
            tags = list(dict.fromkeys(tags))[:max_tags]

        article.tags = tags
        logger.info("tags_generated", count=len(tags), tags=tags)

        return tags

    async def _generate_tags_with_llm(
        self,
        article: Article,
        max_tags: int = 7,
    ) -> list[str]:
        """Gera tags usando LLM."""
        llm = self._get_llm()

        prompt = (
            f"Gere {max_tags} tags relevantes para o seguinte artigo de blog.\n\n"
            f"Título: {article.title}\n"
            f"Keyword: {article.metadata.keyword_primary}\n"
            f"Tipo: {article.metadata.article_type}\n"
            f"Idioma: {article.metadata.language}\n\n"
            f"Regras:\n"
            f"- Tags curtas (1-3 palavras)\n"
            f"- Relevantes para o conteúdo\n"
            f"- Úteis para categorização e SEO\n"
            f"- Em português brasileiro\n"
            f"- No singular quando possível\n\n"
            f"Formato JSON: {{\"tags\": [\"tag1\", \"tag2\", ...]}}"
        )

        response = await llm.generate_structured(prompt=prompt)
        try:
            data = json.loads(response.content)
            return data.get("tags", [])
        except json.JSONDecodeError:
            logger.warning("llm_tags_parse_error")
            return []

    def _normalize_tags(self, raw_tags: list[str]) -> list[str]:
        """
        Normaliza e deduplica uma lista de tags.

        Args:
            raw_tags: Tags brutas.

        Returns:
            Tags normalizadas e deduplicadas.
        """
        normalized: list[str] = []
        seen_slugs: set[str] = set()

        for tag in raw_tags:
            clean = self._normalize_single_tag(tag)
            if not clean or len(clean) < 2:
                continue

            tag_slug = slugify(clean)
            if tag_slug and tag_slug not in seen_slugs:
                # Check for fuzzy duplicates
                is_duplicate = False
                for existing_slug in seen_slugs:
                    if self._is_similar(tag_slug, existing_slug, threshold=0.90):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_slugs.add(tag_slug)
                    normalized.append(clean)

        return normalized

    @staticmethod
    def _normalize_single_tag(tag: str) -> str:
        """Normaliza uma tag individual."""
        # Lowercase
        clean = tag.strip().lower()
        # Remove special characters but keep spaces and accents
        clean = re.sub(r"[^\w\sáàâãéêíóôõúüç-]", "", clean)
        # Remove extra spaces
        clean = re.sub(r"\s+", " ", clean).strip()
        # Remove trailing hyphens
        clean = clean.strip("-")
        return clean

    @staticmethod
    def _is_similar(slug_a: str, slug_b: str, threshold: float = 0.90) -> bool:
        """
        Verifica similaridade entre dois slugs (fuzzy matching simples).

        Usa distância de Jaccard baseada em n-gramas.
        """
        if slug_a == slug_b:
            return True

        # Jaccard similarity on character bigrams
        def bigrams(s: str) -> set[str]:
            return {s[i:i + 2] for i in range(len(s) - 1)}

        bg_a = bigrams(slug_a)
        bg_b = bigrams(slug_b)

        if not bg_a or not bg_b:
            return False

        intersection = bg_a & bg_b
        union = bg_a | bg_b
        similarity = len(intersection) / len(union)

        return similarity >= threshold

    def set_existing_tags(self, tags: dict[str, int]) -> None:
        """
        Define tags existentes no Odoo para evitar duplicatas.

        Args:
            tags: Dict de {tag_name: tag_id}.
        """
        self._existing_tags_cache = tags
        logger.info("existing_tags_loaded", count=len(tags))

    def find_matching_tag(self, tag_name: str) -> Optional[int]:
        """
        Encontra uma tag existente que match com o nome dado.

        Args:
            tag_name: Nome da tag a buscar.

        Returns:
            ID da tag existente ou None.
        """
        normalized = self._normalize_single_tag(tag_name)
        tag_slug = slugify(normalized)

        for existing_name, tag_id in self._existing_tags_cache.items():
            existing_slug = slugify(self._normalize_single_tag(existing_name))
            if existing_slug == tag_slug or self._is_similar(tag_slug, existing_slug):
                return tag_id

        return None
