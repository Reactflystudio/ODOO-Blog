"""
Logger estruturado para o sistema.

Configuração centralizada de logging usando structlog para logs
estruturados com contexto (article_id, keyword, módulo, etc.).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from config import LOGS_DIR, get_settings


_logging_configured = False


def setup_logging(log_level: str | None = None) -> None:
    """
    Configura o sistema de logging estruturado.

    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Se None, usa o valor do .env.
    """
    global _logging_configured
    if _logging_configured:
        return

    settings = get_settings()
    level_name = (log_level or settings.log_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    # File handler
    log_file = LOGS_DIR / "system.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Structlog configuration
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(sort_keys=True)
            if level_name != "DEBUG"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _logging_configured = True


def get_logger(name: str, **initial_context: Any) -> structlog.BoundLogger:
    """
    Retorna um logger estruturado com contexto.

    Args:
        name: Nome do módulo/componente.
        **initial_context: Contexto inicial (article_id, keyword, etc.).

    Returns:
        Logger estruturado com contexto.
    """
    setup_logging()
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
