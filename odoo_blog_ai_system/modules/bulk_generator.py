"""
Módulo de Geração Massiva (Bulk).

Gera 100-500+ artigos em modo batch com processamento assíncrono,
checkpoint/resume, deduplicação semântica e relatório de progresso.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import (
    ArticleType,
    ContentDepth,
    DB_DIR,
    GENERATED_ARTICLES_DIR,
    LLMProvider,
    ToneOfVoice,
    get_settings,
)
from models.article import Article, ArticleStatus
from modules.ai_content_generator import AIContentGenerator
from modules.seo_optimizer import SEOOptimizer
from modules.tag_generator import TagGenerator
from utils.logger import get_logger

logger = get_logger("bulk_generator")

DB_PATH = DB_DIR / "state.db"

# Article type rotation templates
ARTICLE_TYPE_ROTATION = [
    ArticleType.GUIDE,
    ArticleType.HOW_TO,
    ArticleType.LISTICLE,
    ArticleType.COMPARISON,
    ArticleType.TUTORIAL,
    ArticleType.CASE_STUDY,
    ArticleType.REVIEW,
]


class BulkGenerator:
    """Gerador massivo de artigos com processamento assíncrono."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        concurrent: int = 5,
    ) -> None:
        """
        Args:
            provider: Provider LLM a usar.
            concurrent: Número de chamadas LLM simultâneas.
        """
        self.settings = get_settings()
        self.provider = provider
        self.concurrent = min(concurrent, self.settings.max_concurrent_llm_calls)
        self._generator = AIContentGenerator(provider=provider)
        self._optimizer = SEOOptimizer()
        self._tag_generator = TagGenerator(provider=provider)
        self._semaphore = asyncio.Semaphore(self.concurrent)
        self._db = self._init_db()

    def _init_db(self) -> sqlite3.Connection:
        """Inicializa o banco SQLite para estado e checkpoint."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bulk_jobs (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                completed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                config TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bulk_articles (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                article_type TEXT,
                status TEXT DEFAULT 'pending',
                article_data TEXT,
                error_message TEXT,
                created_at TEXT,
                FOREIGN KEY (job_id) REFERENCES bulk_jobs(id)
            )
        """)
        conn.commit()
        return conn

    async def generate_bulk(
        self,
        topic: str,
        count: int = 100,
        language: str = "",
        tone: Optional[ToneOfVoice] = None,
        depth: Optional[ContentDepth] = None,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        keywords: Optional[list[str]] = None,
        resume_job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Gera múltiplos artigos em batch.

        Args:
            topic: Tópico geral para geração.
            count: Número de artigos a gerar.
            language: Idioma.
            tone: Tom de voz.
            depth: Profundidade.
            min_words: Mínimo de palavras.
            max_words: Máximo de palavras.
            keywords: Lista de keywords específicas (opcional).
            resume_job_id: ID de job para retomar.

        Returns:
            Relatório de geração.
        """
        settings = self.settings
        effective_lang = language or settings.default_language
        effective_tone = tone or settings.default_tone
        effective_depth = depth or settings.default_depth
        effective_min = min_words or settings.min_words
        effective_max = max_words or settings.max_words

        # Resume or create new job
        if resume_job_id:
            job_id = resume_job_id
            pending_articles = self._get_pending_articles(job_id)
            logger.info("resuming_job", job_id=job_id, pending=len(pending_articles))
        else:
            import uuid
            job_id = str(uuid.uuid4())

            # Generate keywords if not provided
            if keywords:
                article_keywords = keywords[:count]
            else:
                article_keywords = await self._generate_keywords_for_topic(
                    topic, count, effective_lang
                )

            # Save job to DB
            self._save_job(job_id, topic, len(article_keywords), {
                "language": effective_lang,
                "tone": effective_tone.value,
                "depth": effective_depth.value,
                "min_words": effective_min,
                "max_words": effective_max,
            })

            # Create article entries
            pending_articles = []
            for i, kw in enumerate(article_keywords):
                article_type = ARTICLE_TYPE_ROTATION[i % len(ARTICLE_TYPE_ROTATION)]
                article_entry = {
                    "id": f"{job_id}-{i}",
                    "keyword": kw,
                    "article_type": article_type.value,
                }
                self._save_article_entry(job_id, article_entry)
                pending_articles.append(article_entry)

            logger.info(
                "bulk_job_created",
                job_id=job_id,
                topic=topic,
                total=len(article_keywords),
            )

        # Process articles concurrently
        results = await self._process_articles(
            job_id=job_id,
            pending=pending_articles,
            tone=effective_tone,
            depth=effective_depth,
            language=effective_lang,
            min_words=effective_min,
            max_words=effective_max,
        )

        # Update job status
        self._update_job_status(job_id, "completed")

        return results

    async def _process_articles(
        self,
        job_id: str,
        pending: list[dict[str, Any]],
        tone: ToneOfVoice,
        depth: ContentDepth,
        language: str,
        min_words: int,
        max_words: int,
    ) -> dict[str, Any]:
        """Processa artigos pendentes de forma concorrente."""
        results = {
            "job_id": job_id,
            "total": len(pending),
            "completed": 0,
            "failed": 0,
            "articles": [],
            "start_time": time.monotonic(),
        }

        # Create tasks with semaphore control
        tasks = []
        for entry in pending:
            task = self._generate_single_article(
                job_id=job_id,
                entry=entry,
                tone=tone,
                depth=depth,
                language=language,
                min_words=min_words,
                max_words=max_words,
            )
            tasks.append(task)

        # Process with progress reporting
        completed = 0
        for coro in asyncio.as_completed(tasks):
            try:
                article = await coro
                if article:
                    results["completed"] += 1
                    results["articles"].append({
                        "id": article.id,
                        "title": article.title,
                        "keyword": article.metadata.keyword_primary,
                        "word_count": article.metadata.word_count,
                        "seo_score": article.metadata.seo_score,
                        "status": article.status.value,
                    })
                else:
                    results["failed"] += 1
            except Exception as exc:
                results["failed"] += 1
                logger.error("article_generation_failed", error=str(exc))

            completed += 1
            # Progress log
            if completed % 5 == 0 or completed == len(pending):
                elapsed = time.monotonic() - results["start_time"]
                rate = completed / max(elapsed, 1)
                remaining = (len(pending) - completed) / max(rate, 0.01)
                logger.info(
                    "bulk_progress",
                    completed=completed,
                    total=len(pending),
                    failed=results["failed"],
                    rate_per_min=round(rate * 60, 1),
                    eta_minutes=round(remaining / 60, 1),
                )

        results["elapsed_seconds"] = round(time.monotonic() - results["start_time"], 1)
        return results

    async def _generate_single_article(
        self,
        job_id: str,
        entry: dict[str, Any],
        tone: ToneOfVoice,
        depth: ContentDepth,
        language: str,
        min_words: int,
        max_words: int,
    ) -> Optional[Article]:
        """Gera um único artigo dentro do batch."""
        keyword = entry["keyword"]
        article_type_str = entry.get("article_type", "guia")
        article_type_map = {t.value: t for t in ArticleType}
        article_type = article_type_map.get(article_type_str, ArticleType.GUIDE)

        async with self._semaphore:
            try:
                # Generate article
                article = await self._generator.generate_article(
                    keyword=keyword,
                    article_type=article_type,
                    tone=tone,
                    depth=depth,
                    language=language,
                    min_words=min_words,
                    max_words=max_words,
                    use_cache=True,
                )

                # Optimize SEO
                article, seo_report = self._optimizer.optimize(article, auto_fix=True)

                # Generate tags
                await self._tag_generator.generate_tags(article)

                # Save to disk
                self._save_article_to_disk(article)

                # Update DB
                self._update_article_entry(
                    entry["id"],
                    status="completed",
                    article_data=json.dumps(article.to_storage_dict(), default=str),
                )

                # Update job counter
                self._increment_job_counter(job_id, "completed_count")

                return article

            except Exception as exc:
                logger.error(
                    "single_article_failed",
                    keyword=keyword,
                    error=str(exc),
                )
                self._update_article_entry(
                    entry["id"],
                    status="failed",
                    error_message=str(exc),
                )
                self._increment_job_counter(job_id, "failed_count")
                return None

    async def _generate_keywords_for_topic(
        self,
        topic: str,
        count: int,
        language: str,
    ) -> list[str]:
        """Gera uma lista de keywords variadas para o tópico."""
        try:
            from modules.keyword_cluster import KeywordClusterGenerator
            cluster_gen = KeywordClusterGenerator(provider=self.provider)
            content_map = await cluster_gen.generate_cluster(
                seed_keyword=topic,
                depth=2,
                max_keywords=count,
                language=language,
            )
            keywords = [kw.keyword for kw in content_map.get_all_keywords()]
            await cluster_gen.close()

            if len(keywords) >= count:
                return keywords[:count]

            # If not enough from cluster, generate more via LLM
            remaining = count - len(keywords)
            llm = self._generator._get_provider(
                self.provider or self.settings.default_llm_provider
            )

            prompt = (
                f"Gere {remaining} tópicos de artigo de blog variados "
                f"sobre '{topic}' em {language}.\n"
                f"Cada tópico deve ser uma keyword specific de cauda longa.\n"
                f"Varie entre how-to, listicles, guias, comparativos.\n\n"
                f"Formato JSON: {{\"keywords\": [\"keyword1\", \"keyword2\", ...]}}"
            )

            response = await llm.generate_structured(prompt=prompt)
            data = json.loads(response.content)
            extra = data.get("keywords", [])
            keywords.extend(extra)

            return keywords[:count]

        except Exception as exc:
            logger.warning("keyword_generation_fallback", error=str(exc))
            # Fallback: generate simple variations
            variations = [
                f"{topic} guia completo",
                f"o que é {topic}",
                f"como usar {topic}",
                f"melhores {topic}",
                f"{topic} para iniciantes",
                f"{topic} avançado",
                f"{topic} exemplos",
                f"{topic} dicas",
                f"{topic} benefícios",
                f"{topic} ferramentas",
            ]
            while len(variations) < count:
                variations.append(f"{topic} {len(variations) + 1}")
            return variations[:count]

    def _save_article_to_disk(self, article: Article) -> None:
        """Salva artigo gerado em disco (JSON + HTML)."""
        art_dir = GENERATED_ARTICLES_DIR / article.id
        art_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        json_path = art_dir / "article.json"
        json_path.write_text(
            json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # Save HTML content
        html_path = art_dir / "content.html"
        html_path.write_text(article.content_html, encoding="utf-8")

        logger.debug("article_saved_to_disk", article_id=article.id, path=str(art_dir))

    # ──── DB helpers ──────────────────────────

    def _save_job(self, job_id: str, topic: str, total: int, config: dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        self._db.execute(
            "INSERT OR REPLACE INTO bulk_jobs (id, topic, total_count, status, config, created_at, updated_at) VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (job_id, topic, total, json.dumps(config), now, now),
        )
        self._db.commit()

    def _save_article_entry(self, job_id: str, entry: dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        self._db.execute(
            "INSERT OR IGNORE INTO bulk_articles (id, job_id, keyword, article_type, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (entry["id"], job_id, entry["keyword"], entry.get("article_type", "guia"), now),
        )
        self._db.commit()

    def _update_article_entry(
        self,
        entry_id: str,
        status: str,
        article_data: str = "",
        error_message: str = "",
    ) -> None:
        self._db.execute(
            "UPDATE bulk_articles SET status = ?, article_data = ?, error_message = ? WHERE id = ?",
            (status, article_data, error_message, entry_id),
        )
        self._db.commit()

    def _get_pending_articles(self, job_id: str) -> list[dict[str, Any]]:
        cursor = self._db.execute(
            "SELECT id, keyword, article_type FROM bulk_articles WHERE job_id = ? AND status = 'pending'",
            (job_id,),
        )
        return [
            {"id": row[0], "keyword": row[1], "article_type": row[2]}
            for row in cursor.fetchall()
        ]

    def _update_job_status(self, job_id: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        self._db.execute(
            "UPDATE bulk_jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, job_id),
        )
        self._db.commit()

    def _increment_job_counter(self, job_id: str, column: str) -> None:
        self._db.execute(
            f"UPDATE bulk_jobs SET {column} = {column} + 1, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), job_id),
        )
        self._db.commit()

    def get_job_status(self, job_id: str) -> Optional[dict[str, Any]]:
        """Retorna o status de um job."""
        cursor = self._db.execute(
            "SELECT * FROM bulk_jobs WHERE id = ?", (job_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "topic": row[1],
                "total_count": row[2],
                "completed_count": row[3],
                "failed_count": row[4],
                "status": row[5],
                "config": json.loads(row[6]) if row[6] else {},
                "created_at": row[7],
                "updated_at": row[8],
            }
        return None
