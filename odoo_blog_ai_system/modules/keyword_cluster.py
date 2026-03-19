"""
Módulo de Cluster de Palavras-Chave (SEO Programático).

Expande uma keyword semente em clusters de keywords agrupadas
por intenção de busca, com priorização automática e content map.
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from typing import Any, Optional

from config import ArticleType, LLMProvider, SearchIntent, get_settings
from models.keyword import ContentMap, InterlinkMapping, Keyword, KeywordCluster
from providers.gemini_provider import GeminiProvider
from providers.llm_provider import LLMProviderBase
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from utils.cache import get_cache
from utils.http_client import HttpClient
from utils.logger import get_logger

logger = get_logger("keyword_cluster")

# Modificadores para expansão de keywords
MODIFIERS_PT = {
    "informacional": [
        "o que é", "como funciona", "para que serve", "qual a diferença",
        "como usar", "exemplos de", "tipos de", "vantagens de",
        "importância de", "benefícios de", "como fazer",
    ],
    "transacional": [
        "melhor", "melhores", "preço", "quanto custa", "contratar",
        "comprar", "ferramentas de", "software de", "plataforma de",
        "serviço de", "curso de",
    ],
    "comparativa": [
        "vs", "versus", "ou", "comparação", "alternativas a",
        "diferença entre", "qual o melhor", "comparativo",
    ],
    "navegacional": [
        "login", "site oficial", "download", "app", "tutorial",
    ],
}


class KeywordClusterGenerator:
    """Gerador de clusters de keywords a partir de seed keyword."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        max_keywords: int = 50,
    ) -> None:
        """
        Args:
            provider: Provider LLM para expansão semântica.
            max_keywords: Máximo de keywords a gerar.
        """
        self.settings = get_settings()
        self.provider = provider or self.settings.default_llm_provider
        self.max_keywords = max_keywords
        self._cache = get_cache("keywords")
        self._http = HttpClient(max_calls_per_second=2)
        self._llm: Optional[LLMProviderBase] = None
        self._semaphore = asyncio.Semaphore(3)

    def _get_llm(self) -> LLMProviderBase:
        """Retorna o provider LLM."""
        if self._llm is None:
            api_key = self.settings.get_llm_api_key(self.provider)
            model = self.settings.get_llm_model(self.provider)
            if self.provider == LLMProvider.OPENAI:
                self._llm = OpenAIProvider(api_key=api_key, model=model)
            elif self.provider == LLMProvider.OLLAMA:
                self._llm = OllamaProvider(model=model)
            else:
                self._llm = GeminiProvider(api_key=api_key, model=model)
        return self._llm

    async def generate_cluster(
        self,
        seed_keyword: str,
        depth: int = 2,
        max_keywords: Optional[int] = None,
        language: str = "pt-br",
    ) -> ContentMap:
        """
        Gera um cluster completo de keywords a partir de uma seed.

        Args:
            seed_keyword: Keyword semente.
            depth: Profundidade de expansão (1-3).
            max_keywords: Override do máximo de keywords.
            language: Idioma.

        Returns:
            ContentMap com clusters e mapa de conteúdo.
        """
        max_kw = max_keywords or self.max_keywords

        # Check cache
        cache_key = f"cluster:{seed_keyword}:{depth}:{max_kw}:{language}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.info("cluster_from_cache", seed=seed_keyword)
            return ContentMap.from_storage_dict(cached)

        logger.info(
            "cluster_generation_start",
            seed=seed_keyword,
            depth=depth,
            max_keywords=max_kw,
        )

        # Phase 1: Expand keywords from multiple sources
        all_keywords: list[str] = [seed_keyword]

        # Run expansion methods concurrently
        expansion_tasks = [
            self._expand_with_modifiers(seed_keyword),
            self._expand_with_autocomplete(seed_keyword),
            self._expand_with_llm(seed_keyword, language),
        ]

        if depth >= 2:
            expansion_tasks.append(
                self._expand_paa(seed_keyword)
            )
        if depth >= 3:
            expansion_tasks.append(
                self._expand_related_searches(seed_keyword)
            )

        results = await asyncio.gather(*expansion_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_keywords.extend(result)
            elif isinstance(result, Exception):
                logger.warning("expansion_error", error=str(result))

        # Deduplicate
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in all_keywords:
            normalized = kw.lower().strip()
            if normalized and normalized not in seen and len(normalized) > 3:
                seen.add(normalized)
                unique_keywords.append(kw.strip())

        # Limit
        unique_keywords = unique_keywords[:max_kw]

        logger.info("keywords_expanded", count=len(unique_keywords))

        # Phase 2: Classify keywords by intent and create Keyword objects
        classified = await self._classify_keywords(unique_keywords, seed_keyword, language)

        # Phase 3: Group into clusters
        clusters = self._group_into_clusters(classified)

        # Phase 4: Calculate opportunity scores and prioritize
        for cluster in clusters:
            for kw in cluster.keywords:
                kw.calculate_opportunity_score()
                kw.set_priority_from_score()
            cluster.sort_by_priority()

        # Phase 5: Build content map
        content_map = ContentMap(
            seed_keyword=seed_keyword,
            clusters=clusters,
            pillar_article={
                "title": f"Guia Completo sobre {seed_keyword.title()}",
                "keyword": seed_keyword,
                "type": "guia",
            },
        )

        # Phase 6: Generate interlink suggestions
        content_map.interlinks = self._generate_interlinks(content_map)
        content_map.calculate_totals()

        # Cache
        self._cache.set(cache_key, content_map.to_storage_dict(), ttl=86400)

        logger.info(
            "cluster_generation_complete",
            seed=seed_keyword,
            total_keywords=content_map.total_keywords,
            clusters=len(clusters),
        )

        return content_map

    async def _expand_with_modifiers(self, seed: str) -> list[str]:
        """Expande com modificadores pré-definidos."""
        keywords: list[str] = []
        for intent_mods in MODIFIERS_PT.values():
            for mod in intent_mods:
                if mod.startswith("o que") or mod.startswith("como") or mod.startswith("para"):
                    keywords.append(f"{mod} {seed}")
                elif mod in ("vs", "versus", "ou"):
                    keywords.append(f"{seed} {mod}")
                else:
                    keywords.append(f"{mod} {seed}")
                    keywords.append(f"{seed} {mod}")
        return keywords

    async def _expand_with_autocomplete(self, seed: str) -> list[str]:
        """Expande usando Google Autocomplete API."""
        keywords: list[str] = []
        try:
            async with self._semaphore:
                encoded = urllib.parse.quote(seed)
                url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={encoded}&hl=pt-BR"

                response = await self._http.get(url)
                data = response.json()

                if isinstance(data, list) and len(data) > 1:
                    suggestions = data[1]
                    if isinstance(suggestions, list):
                        keywords.extend(str(s) for s in suggestions)

                # Also try with space suffix for more suggestions
                for prefix in ["como ", "o que ", "melhor ", "por que "]:
                    url2 = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urllib.parse.quote(prefix + seed)}&hl=pt-BR"
                    try:
                        resp2 = await self._http.get(url2)
                        data2 = resp2.json()
                        if isinstance(data2, list) and len(data2) > 1:
                            keywords.extend(str(s) for s in data2[1] if isinstance(data2[1], list))
                    except Exception:
                        pass

                logger.debug("autocomplete_results", count=len(keywords))

        except Exception as exc:
            logger.warning("autocomplete_error", error=str(exc))

        return keywords

    async def _expand_paa(self, seed: str) -> list[str]:
        """Expande com People Also Ask (via LLM simulation)."""
        try:
            llm = self._get_llm()
            prompt = (
                f"Gere 10 perguntas que as pessoas frequentemente fazem no Google "
                f"relacionadas a '{seed}' (em português brasileiro).\n\n"
                f"Formato JSON: {{\"questions\": [\"pergunta1\", \"pergunta2\", ...]}}"
            )
            response = await llm.generate_structured(prompt=prompt)
            data = json.loads(response.content)
            return data.get("questions", [])
        except Exception as exc:
            logger.warning("paa_expansion_error", error=str(exc))
            return []

    async def _expand_related_searches(self, seed: str) -> list[str]:
        """Expande com buscas relacionadas (via LLM)."""
        try:
            llm = self._get_llm()
            prompt = (
                f"Gere 15 termos de busca relacionados a '{seed}' que "
                f"as pessoas buscam no Google em português brasileiro.\n"
                f"Inclua variações long-tail, sinônimos e termos complementares.\n\n"
                f"Formato JSON: {{\"related\": [\"termo1\", \"termo2\", ...]}}"
            )
            response = await llm.generate_structured(prompt=prompt)
            data = json.loads(response.content)
            return data.get("related", [])
        except Exception as exc:
            logger.warning("related_expansion_error", error=str(exc))
            return []

    async def _expand_with_llm(self, seed: str, language: str) -> list[str]:
        """Expansão semântica via LLM."""
        try:
            llm = self._get_llm()
            prompt = (
                f"Você é um especialista em SEO. Gere 20 variações e "
                f"expansões de keyword para '{seed}' em {language}.\n\n"
                f"Inclua:\n"
                f"- Variações de cauda longa\n"
                f"- Perguntas que as pessoas fazem\n"
                f"- Termos comparativos\n"
                f"- Termos transacionais\n"
                f"- Sinônimos e termos relacionados\n\n"
                f"Formato JSON: {{\"keywords\": [\"keyword1\", \"keyword2\", ...]}}"
            )
            response = await llm.generate_structured(prompt=prompt)
            data = json.loads(response.content)
            return data.get("keywords", [])
        except Exception as exc:
            logger.warning("llm_expansion_error", error=str(exc))
            return []

    async def _classify_keywords(
        self,
        keywords: list[str],
        seed: str,
        language: str,
    ) -> list[Keyword]:
        """Classifica keywords por intenção de busca e tipo de artigo."""
        try:
            llm = self._get_llm()
            # Process in batches to avoid token limits
            batch_size = 25
            all_classified: list[Keyword] = []

            for i in range(0, len(keywords), batch_size):
                batch = keywords[i:i + batch_size]
                prompt = (
                    f"Classifique as seguintes keywords por intenção de busca.\n\n"
                    f"Keywords:\n{json.dumps(batch, ensure_ascii=False)}\n\n"
                    f"Para cada keyword, determine:\n"
                    f"1. intent: informacional, transacional, comparativa, ou navegacional\n"
                    f"2. article_type: how-to, listicle, guia, comparativo, case-study, review, tutorial\n"
                    f"3. estimated_volume: estimativa de volume de busca mensal (100-10000)\n"
                    f"4. estimated_difficulty: dificuldade de ranquear (0.0-1.0)\n\n"
                    f"Formato JSON:\n"
                    f"{{\n"
                    f"  \"classified\": [\n"
                    f"    {{\n"
                    f"      \"keyword\": \"...\",\n"
                    f"      \"intent\": \"informacional\",\n"
                    f"      \"article_type\": \"guia\",\n"
                    f"      \"estimated_volume\": 1000,\n"
                    f"      \"estimated_difficulty\": 0.5\n"
                    f"    }}\n"
                    f"  ]\n"
                    f"}}"
                )

                response = await llm.generate_structured(prompt=prompt)
                try:
                    data = json.loads(response.content)
                    for item in data.get("classified", []):
                        intent_map = {
                            "informacional": SearchIntent.INFORMATIONAL,
                            "transacional": SearchIntent.TRANSACTIONAL,
                            "comparativa": SearchIntent.COMPARATIVE,
                            "navegacional": SearchIntent.NAVIGATIONAL,
                        }
                        type_map = {
                            "how-to": ArticleType.HOW_TO,
                            "listicle": ArticleType.LISTICLE,
                            "guia": ArticleType.GUIDE,
                            "comparativo": ArticleType.COMPARISON,
                            "case-study": ArticleType.CASE_STUDY,
                            "review": ArticleType.REVIEW,
                            "tutorial": ArticleType.TUTORIAL,
                        }

                        kw = Keyword(
                            keyword=item.get("keyword", ""),
                            intent=intent_map.get(
                                item.get("intent", ""), SearchIntent.INFORMATIONAL
                            ),
                            article_type=type_map.get(
                                item.get("article_type", ""), ArticleType.GUIDE
                            ),
                            estimated_volume=item.get("estimated_volume", 100),
                            estimated_difficulty=min(1.0, max(0.0, item.get("estimated_difficulty", 0.5))),
                            source="llm_classification",
                            parent_keyword=seed,
                        )
                        all_classified.append(kw)
                except json.JSONDecodeError:
                    # Fallback: create keywords with default classification
                    for kw_text in batch:
                        all_classified.append(Keyword(
                            keyword=kw_text,
                            intent=self._guess_intent(kw_text),
                            source="modifier_expansion",
                            parent_keyword=seed,
                        ))

            return all_classified

        except Exception as exc:
            logger.warning("classification_error", error=str(exc))
            # Fallback classification
            return [
                Keyword(
                    keyword=kw,
                    intent=self._guess_intent(kw),
                    source="fallback",
                    parent_keyword=seed,
                )
                for kw in keywords
            ]

    @staticmethod
    def _guess_intent(keyword: str) -> SearchIntent:
        """Heurística para adivinhar intenção de busca."""
        kw = keyword.lower()
        if any(w in kw for w in ["comprar", "preço", "contratar", "melhor", "ferramenta", "software", "curso"]):
            return SearchIntent.TRANSACTIONAL
        if any(w in kw for w in ["vs", "versus", "comparar", "alternativa", "diferença entre"]):
            return SearchIntent.COMPARATIVE
        if any(w in kw for w in ["login", "site", "download", "app"]):
            return SearchIntent.NAVIGATIONAL
        return SearchIntent.INFORMATIONAL

    @staticmethod
    def _group_into_clusters(keywords: list[Keyword]) -> list[KeywordCluster]:
        """Agrupa keywords em clusters por intenção de busca."""
        groups: dict[SearchIntent, list[Keyword]] = {}
        for kw in keywords:
            groups.setdefault(kw.intent, []).append(kw)

        clusters: list[KeywordCluster] = []
        for intent, kws in groups.items():
            cluster = KeywordCluster(
                intent=intent,
                keywords=kws,
                primary_keyword=kws[0].keyword if kws else None,
            )
            clusters.append(cluster)

        return clusters

    @staticmethod
    def _generate_interlinks(content_map: ContentMap) -> list[InterlinkMapping]:
        """Gera sugestões de interlinks entre artigos planejados."""
        interlinks: list[InterlinkMapping] = []
        all_keywords = content_map.get_all_keywords()

        # Simple: link each article to 2-3 related articles
        for i, kw in enumerate(all_keywords):
            for j, related_kw in enumerate(all_keywords):
                if i != j and i < len(all_keywords) - 1:
                    # Check if keywords share words
                    kw_words = set(kw.keyword.lower().split())
                    related_words = set(related_kw.keyword.lower().split())
                    overlap = kw_words & related_words
                    if len(overlap) >= 1 and len(interlinks) < len(all_keywords) * 2:
                        interlinks.append(InterlinkMapping(
                            from_article_id=f"article_{i}",
                            to_article_id=f"article_{j}",
                            anchor_text=related_kw.keyword,
                            from_keyword=kw.keyword,
                            to_keyword=related_kw.keyword,
                        ))

        return interlinks[:50]  # Limit

    async def close(self) -> None:
        """Cleanup."""
        await self._http.close()
