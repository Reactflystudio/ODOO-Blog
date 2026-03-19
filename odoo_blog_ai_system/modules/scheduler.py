"""
Módulo de Agendamento de Publicações.

Gerencia fila de publicação com distribuição inteligente,
horários otimizados e integração com APScheduler.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from config import DB_DIR, get_settings
from models.article import Article, ArticleStatus
from modules.odoo_publisher import OdooPublisher
from utils.logger import get_logger

logger = get_logger("scheduler")

SCHEDULE_DB = DB_DIR / "schedule.db"


class PublicationScheduler:
    """Agendador de publicações do blog."""

    def __init__(
        self,
        articles_per_day: int = 0,
        start_time: str = "",
        end_time: str = "",
    ) -> None:
        """
        Args:
            articles_per_day: Artigos por dia (0 = usa config).
            start_time: Hora de início (HH:MM).
            end_time: Hora de fim (HH:MM).
        """
        settings = get_settings()
        self.articles_per_day = articles_per_day or settings.articles_per_day
        self.start_time = start_time or settings.schedule_start_time
        self.end_time = end_time or settings.schedule_end_time
        self._publisher: Optional[OdooPublisher] = None
        self._db = self._init_db()

    def _init_db(self) -> sqlite3.Connection:
        """Inicializa o banco de agendamento."""
        SCHEDULE_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SCHEDULE_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL UNIQUE,
                article_data TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                published_at TEXT,
                odoo_post_id INTEGER,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        return conn

    def _get_publisher(self) -> OdooPublisher:
        """Retorna o publisher Odoo."""
        if self._publisher is None:
            self._publisher = OdooPublisher()
        return self._publisher

    def schedule_article(
        self,
        article: Article,
        scheduled_at: Optional[datetime] = None,
        priority: int = 0,
    ) -> datetime:
        """
        Agenda um artigo para publicação.

        Args:
            article: Artigo a agendar.
            scheduled_at: Data/hora específica (ou auto-detectar próximo slot).
            priority: Prioridade (maior = mais urgente).

        Returns:
            Data/hora agendada.
        """
        if scheduled_at is None:
            scheduled_at = self._get_next_available_slot()

        article.status = ArticleStatus.SCHEDULED
        article.scheduled_at = scheduled_at

        # Save to queue
        self._db.execute(
            """INSERT OR REPLACE INTO schedule_queue
               (article_id, article_data, scheduled_at, priority, status)
               VALUES (?, ?, ?, ?, 'queued')""",
            (
                article.id,
                json.dumps(article.to_storage_dict(), default=str),
                scheduled_at.isoformat(),
                priority,
            ),
        )
        self._db.commit()

        logger.info(
            "article_scheduled",
            article_id=article.id,
            title=article.title,
            scheduled_at=scheduled_at.isoformat(),
            priority=priority,
        )

        return scheduled_at

    def schedule_batch(
        self,
        articles: list[Article],
        start_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """
        Agenda múltiplos artigos distribuídos ao longo dos dias.

        Args:
            articles: Lista de artigos a agendar.
            start_date: Data de início (ou amanhã).

        Returns:
            Lista com informações de agendamento.
        """
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        schedule_info: list[dict[str, Any]] = []
        slots = self._generate_time_slots(
            start_date=start_date,
            article_count=len(articles),
        )

        for article, slot in zip(articles, slots):
            scheduled_dt = self.schedule_article(article, scheduled_at=slot)
            schedule_info.append({
                "article_id": article.id,
                "title": article.title,
                "scheduled_at": scheduled_dt.isoformat(),
            })

        logger.info(
            "batch_scheduled",
            total=len(schedule_info),
            start=slots[0].isoformat() if slots else "N/A",
            end=slots[-1].isoformat() if slots else "N/A",
        )

        return schedule_info

    def _generate_time_slots(
        self,
        start_date: datetime,
        article_count: int,
    ) -> list[datetime]:
        """
        Gera slots de tempo distribuídos ao longo dos dias.

        Args:
            start_date: Data de início.
            article_count: Número de artigos.

        Returns:
            Lista de datetimes para cada artigo.
        """
        start_h, start_m = map(int, self.start_time.split(":"))
        end_h, end_m = map(int, self.end_time.split(":"))

        total_minutes = (end_h * 60 + end_m) - (start_h * 60 + start_m)
        if self.articles_per_day > 1:
            interval = total_minutes // self.articles_per_day
        else:
            interval = total_minutes

        slots: list[datetime] = []
        current_date = start_date
        articles_today = 0

        # Optimal posting hours (engagement-based)
        optimal_hours = [9, 10, 11, 14, 15, 16]

        for i in range(article_count):
            if articles_today >= self.articles_per_day:
                current_date += timedelta(days=1)
                articles_today = 0

            if articles_today < len(optimal_hours):
                hour = optimal_hours[articles_today]
            else:
                hour = start_h + (articles_today * interval // 60)

            minute = (articles_today * 13) % 60  # Varied minutes

            slot = current_date.replace(
                hour=min(hour, end_h),
                minute=minute,
                second=0,
                microsecond=0,
            )
            slots.append(slot)
            articles_today += 1

        return slots

    def _get_next_available_slot(self) -> datetime:
        """Encontra o próximo slot disponível para publicação."""
        # Get last scheduled time
        cursor = self._db.execute(
            "SELECT scheduled_at FROM schedule_queue ORDER BY scheduled_at DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if row:
            last_scheduled = datetime.fromisoformat(row[0])
            # Count articles on that day
            day_start = last_scheduled.replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)

            cursor2 = self._db.execute(
                "SELECT COUNT(*) FROM schedule_queue WHERE scheduled_at >= ? AND scheduled_at < ?",
                (day_start.isoformat(), day_end.isoformat()),
            )
            count_today = cursor2.fetchone()[0]

            if count_today < self.articles_per_day:
                # Add to same day
                slots = self._generate_time_slots(day_start, count_today + 1)
                return slots[-1]
            else:
                # Next day
                slots = self._generate_time_slots(day_start + timedelta(days=1), 1)
                return slots[0]
        else:
            # First schedule - tomorrow
            tomorrow = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return tomorrow

    def get_pending_publications(self) -> list[dict[str, Any]]:
        """Retorna publicações pendentes ordenadas por horário."""
        now = datetime.now().isoformat()
        cursor = self._db.execute(
            """SELECT article_id, article_data, scheduled_at, priority
               FROM schedule_queue
               WHERE status = 'queued' AND scheduled_at <= ?
               ORDER BY priority DESC, scheduled_at ASC""",
            (now,),
        )
        return [
            {
                "article_id": row[0],
                "article_data": row[1],
                "scheduled_at": row[2],
                "priority": row[3],
            }
            for row in cursor.fetchall()
        ]

    def process_pending(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Processa publicações pendentes que já atingiram o horário.

        Args:
            dry_run: Simular sem efetuar.

        Returns:
            Relatório de processamento.
        """
        pending = self.get_pending_publications()

        results = {
            "total_pending": len(pending),
            "published": 0,
            "failed": 0,
            "errors": [],
        }

        if not pending:
            logger.info("no_pending_publications")
            return results

        publisher = self._get_publisher()

        for item in pending:
            article_id = item["article_id"]

            try:
                article_data = json.loads(item["article_data"])
                article = Article.from_storage_dict(article_data)

                if dry_run:
                    logger.info("dry_run_publish", title=article.title)
                    results["published"] += 1
                    continue

                post_id = publisher.publish_article(article, publish=True)

                # Update queue
                self._db.execute(
                    """UPDATE schedule_queue
                       SET status = 'published', published_at = ?, odoo_post_id = ?
                       WHERE article_id = ?""",
                    (datetime.now().isoformat(), post_id, article_id),
                )
                self._db.commit()
                results["published"] += 1

                logger.info(
                    "scheduled_article_published",
                    article_id=article_id,
                    odoo_id=post_id,
                )

            except Exception as exc:
                results["failed"] += 1
                results["errors"].append({"article_id": article_id, "error": str(exc)})

                self._db.execute(
                    """UPDATE schedule_queue
                       SET status = 'failed', error_message = ?
                       WHERE article_id = ?""",
                    (str(exc), article_id),
                )
                self._db.commit()

                logger.error("scheduled_publish_failed", article_id=article_id, error=str(exc))

        return results

    def get_schedule_overview(self) -> dict[str, Any]:
        """Retorna visão geral do agendamento."""
        cursor = self._db.execute("""
            SELECT status, COUNT(*) as count
            FROM schedule_queue
            GROUP BY status
        """)

        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Upcoming
        upcoming_cursor = self._db.execute("""
            SELECT article_id, scheduled_at
            FROM schedule_queue
            WHERE status = 'queued'
            ORDER BY scheduled_at
            LIMIT 10
        """)

        upcoming = [
            {"article_id": row[0], "scheduled_at": row[1]}
            for row in upcoming_cursor.fetchall()
        ]

        return {
            "status_counts": status_counts,
            "upcoming": upcoming,
            "articles_per_day": self.articles_per_day,
            "time_window": f"{self.start_time} - {self.end_time}",
        }

    def start_daemon(self, check_interval_seconds: int = 60) -> None:
        """
        Inicia o agendador como daemon que verifica publicações pendentes.

        Args:
            check_interval_seconds: Intervalo de verificação em segundos.
        """
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler

            scheduler = BlockingScheduler()
            scheduler.add_job(
                self.process_pending,
                "interval",
                seconds=check_interval_seconds,
                id="publish_checker",
            )

            logger.info(
                "scheduler_daemon_started",
                interval_s=check_interval_seconds,
            )

            scheduler.start()

        except ImportError:
            logger.warning("apscheduler_not_installed", msg="Usando loop simples")
            import time
            while True:
                self.process_pending()
                time.sleep(check_interval_seconds)
        except KeyboardInterrupt:
            logger.info("scheduler_daemon_stopped")
