"""
Módulo de Scraping de Tendências.

Identifica tópicos em alta a partir de múltiplas fontes com
fallback, classificação e integração direta com o gerador de conteúdo.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Optional

from config import get_settings
from utils.cache import get_cache
from utils.http_client import HttpClient
from utils.logger import get_logger

logger = get_logger("trend_scraper")


class TrendItem:
    """Item de tendência identificado."""

    def __init__(
        self,
        topic: str,
        score: float = 0.0,
        source: str = "",
        category: str = "",
        region: str = "BR",
        classification: str = "trending",
        url: str = "",
        description: str = "",
        suggested_keyword: str = "",
        suggested_angle: str = "",
        discovered_at: Any = None,
    ) -> None:
        self.topic = topic
        self.score = score
        self.source = source
        self.category = category
        self.region = region
        self.classification = classification  # trending, evergreen, seasonal
        self.url = url
        self.description = description
        self.suggested_keyword = suggested_keyword or topic
        self.suggested_angle = suggested_angle
        
        if isinstance(discovered_at, str):
            try:
                self.discovered_at = datetime.fromisoformat(discovered_at)
            except ValueError:
                self.discovered_at = datetime.utcnow()
        elif isinstance(discovered_at, datetime):
            self.discovered_at = discovered_at
        else:
            self.discovered_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "topic": self.topic,
            "score": self.score,
            "source": self.source,
            "category": self.category,
            "region": self.region,
            "classification": self.classification,
            "url": self.url,
            "description": self.description,
            "suggested_keyword": self.suggested_keyword,
            "suggested_angle": self.suggested_angle,
            "discovered_at": self.discovered_at.isoformat(),
        }


class TrendScraper:
    """Scraper de tendências de múltiplas fontes."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._http = HttpClient(max_calls_per_second=2)
        self._cache = get_cache("trends", ttl=1800)
        self._semaphore = asyncio.Semaphore(3)

    async def close(self) -> None:
        """Fecha recursos internos (HTTP client e cache)."""
        await self._http.close()
        try:
            self._cache.close()
        except Exception:
            # Cache close is best-effort; ignore failures.
            pass

    async def discover_trends(
        self,
        niche: str = "",
        region: str = "BR",
        language: str = "pt-br",
        limit: int = 20,
    ) -> list[TrendItem]:
        """
        Descobre tendências de múltiplas fontes.

        Args:
            niche: Nicho/indústria para filtrar.
            region: Região (BR, US, etc.).
            language: Idioma.
            limit: Máximo de resultados.

        Returns:
            Lista de tendências rankeadas por score de oportunidade.
        """
        cache_key = f"trends:{niche}:{region}:{language}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.info("trends_from_cache", niche=niche)
            return [TrendItem(**item) for item in cached]

        logger.info("discovering_trends", niche=niche, region=region)

        # Run scrapers concurrently
        tasks = [
            self._scrape_google_trends(niche, region),
            self._scrape_news_api(niche, language),
            self._scrape_hacker_news(niche),
            self._scrape_reddit_trends(niche),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_trends: list[TrendItem] = []
        for result in results:
            if isinstance(result, list):
                all_trends.extend(result)
            elif isinstance(result, Exception):
                logger.warning("scraper_error", error=str(result))

        # Deduplicate by topic similarity
        unique = self._deduplicate_trends(all_trends)

        # Score and rank
        ranked = sorted(unique, key=lambda t: t.score, reverse=True)[:limit]

        # Suggest keywords and angles
        for trend in ranked:
            if not trend.suggested_angle:
                trend.suggested_angle = self._suggest_angle(trend)

        # Cache results
        self._cache.set(cache_key, [t.to_dict() for t in ranked])

        logger.info("trends_discovered", count=len(ranked))
        return ranked

    async def _scrape_google_trends(self, niche: str, region: str) -> list[TrendItem]:
        """Obtém trending searches do Google Trends via pytrends."""
        trends: list[TrendItem] = []

        try:
            from pytrends.request import TrendReq

            async with self._semaphore:
                # Run in thread pool since pytrends is synchronous
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._fetch_google_trends_sync(niche, region),
                )
                trends.extend(result)

        except ImportError:
            logger.warning("pytrends_not_installed")
        except Exception as exc:
            logger.warning("google_trends_error", error=str(exc))

        return trends

    def _fetch_google_trends_sync(self, niche: str, region: str) -> list[TrendItem]:
        """Busca síncrona no Google Trends."""
        trends: list[TrendItem] = []
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl="pt-BR", tz=180, timeout=(10, 30))

            # Trending searches
            try:
                trending = pytrends.trending_searches(pn="brazil" if region == "BR" else "united_states")
                for idx, row in trending.head(15).iterrows():
                    topic = str(row.iloc[0]) if hasattr(row, 'iloc') else str(row[0])
                    if niche and niche.lower() not in topic.lower():
                        # Still include but with lower score
                        score = 30.0
                    else:
                        score = 80.0 - (idx * 3)

                    trends.append(TrendItem(
                        topic=topic,
                        score=max(10, score),
                        source="google_trends",
                        region=region,
                        classification="trending",
                    ))
            except Exception as exc:
                logger.debug("trending_searches_error", error=str(exc))

            # Related queries for the niche
            if niche:
                try:
                    pytrends.build_payload([niche], cat=0, timeframe="now 7-d", geo=region)
                    related = pytrends.related_queries()
                    if niche in related and related[niche].get("rising") is not None:
                        rising = related[niche]["rising"]
                        for _, row in rising.head(10).iterrows():
                            trends.append(TrendItem(
                                topic=str(row.get("query", "")),
                                score=min(100, float(row.get("value", 50))),
                                source="google_trends_related",
                                category=niche,
                                region=region,
                                classification="trending",
                            ))
                except Exception as exc:
                    logger.debug("related_queries_error", error=str(exc))

        except Exception as exc:
            logger.warning("google_trends_sync_error", error=str(exc))

        return trends

    async def _scrape_news_api(self, niche: str, language: str) -> list[TrendItem]:
        """Obtém headlines de tendência da NewsAPI."""
        trends: list[TrendItem] = []
        api_key = self.settings.news_api_key

        if not api_key:
            logger.debug("news_api_key_not_set")
            return trends

        try:
            async with self._semaphore:
                lang_code = "pt" if "pt" in language else "en"
                params: dict[str, Any] = {
                    "apiKey": api_key,
                    "language": lang_code,
                    "pageSize": 15,
                    "sortBy": "popularity",
                }

                if niche:
                    params["q"] = niche
                    url = "https://newsapi.org/v2/everything"
                else:
                    params["country"] = "br"
                    url = "https://newsapi.org/v2/top-headlines"

                response = await self._http.get(url, params=params)
                data = response.json()

                for i, article in enumerate(data.get("articles", [])[:15]):
                    title = article.get("title", "")
                    if title and "[Removed]" not in title:
                        trends.append(TrendItem(
                            topic=title,
                            score=75.0 - (i * 3),
                            source="newsapi",
                            category=niche or "geral",
                            url=article.get("url", ""),
                            description=article.get("description", "")[:200],
                            classification="trending",
                        ))

        except Exception as exc:
            logger.warning("newsapi_error", error=str(exc))

        return trends

    async def _scrape_hacker_news(self, niche: str) -> list[TrendItem]:
        """Obtém stories em alta do Hacker News."""
        trends: list[TrendItem] = []

        try:
            async with self._semaphore:
                resp = await self._http.get(
                    "https://hacker-news.firebaseio.com/v0/topstories.json"
                )
                story_ids = resp.json()[:20]

                for i, story_id in enumerate(story_ids[:15]):
                    try:
                        story_resp = await self._http.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                        )
                        story = story_resp.json()
                        title = story.get("title", "")

                        if not title:
                            continue

                        score_val = story.get("score", 0)
                        relevance = 50.0

                        if niche and niche.lower() in title.lower():
                            relevance = 85.0

                        trends.append(TrendItem(
                            topic=title,
                            score=relevance - (i * 2),
                            source="hacker_news",
                            category="technology",
                            url=story.get("url", ""),
                            classification="trending",
                        ))

                    except Exception:
                        continue

                    await asyncio.sleep(0.1)  # Rate limiting

        except Exception as exc:
            logger.warning("hackernews_error", error=str(exc))

        return trends

    async def _scrape_reddit_trends(self, niche: str) -> list[TrendItem]:
        """Obtém posts em alta do Reddit."""
        trends: list[TrendItem] = []

        if not self.settings.reddit_client_id:
            return trends

        try:
            async with self._semaphore:
                # Get OAuth token
                import httpx
                async with httpx.AsyncClient() as client:
                    auth_resp = await client.post(
                        "https://www.reddit.com/api/v1/access_token",
                        data={"grant_type": "client_credentials"},
                        auth=(
                            self.settings.reddit_client_id,
                            self.settings.reddit_client_secret,
                        ),
                        headers={"User-Agent": "BlogAI/1.0"},
                        timeout=10.0,
                    )
                    token = auth_resp.json().get("access_token")

                    if not token:
                        return trends

                    # Get hot posts from relevant subreddit
                    subreddit = niche.replace(" ", "") if niche else "technology"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "BlogAI/1.0",
                    }

                    hot_resp = await client.get(
                        f"https://oauth.reddit.com/r/{subreddit}/hot",
                        params={"limit": 15},
                        headers=headers,
                        timeout=10.0,
                    )

                    if hot_resp.status_code == 200:
                        posts = hot_resp.json().get("data", {}).get("children", [])
                        for i, post in enumerate(posts):
                            post_data = post.get("data", {})
                            title = post_data.get("title", "")
                            if title:
                                trends.append(TrendItem(
                                    topic=title,
                                    score=65.0 - (i * 3),
                                    source="reddit",
                                    category=niche or subreddit,
                                    url=f"https://reddit.com{post_data.get('permalink', '')}",
                                    classification="trending",
                                ))

        except Exception as exc:
            logger.warning("reddit_error", error=str(exc))

        return trends

    def _deduplicate_trends(self, trends: list[TrendItem]) -> list[TrendItem]:
        """Remove tendências duplicadas por similaridade de tópico."""
        unique: list[TrendItem] = []
        seen_topics: set[str] = set()

        for trend in trends:
            normalized = trend.topic.lower().strip()
            # Simple dedup by checking substring overlap
            is_dup = False
            for seen in seen_topics:
                if normalized in seen or seen in normalized:
                    is_dup = True
                    break
                # Jaccard similarity on words
                words_a = set(normalized.split())
                words_b = set(seen.split())
                if words_a and words_b:
                    overlap = len(words_a & words_b) / len(words_a | words_b)
                    if overlap > 0.6:
                        is_dup = True
                        break

            if not is_dup:
                seen_topics.add(normalized)
                unique.append(trend)

        return unique

    @staticmethod
    def _suggest_angle(trend: TrendItem) -> str:
        """Sugere um ângulo editorial para a tendência."""
        topic_lower = trend.topic.lower()

        if any(w in topic_lower for w in ["como", "tutorial", "passo a passo"]):
            return "how-to"
        elif any(w in topic_lower for w in ["melhor", "top", "ranking"]):
            return "listicle"
        elif any(w in topic_lower for w in ["vs", "versus", "comparar"]):
            return "comparativo"
        elif any(w in topic_lower for w in ["novo", "lançamento", "anúncio"]):
            return "notícia"
        else:
            return "guia"

    async def close(self) -> None:
        """Cleanup."""
        await self._http.close()
