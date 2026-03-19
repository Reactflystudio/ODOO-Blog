"""
Sistema de Cache em disco.

Cache baseado em arquivos usando diskcache para evitar
re-processamento e chamadas desnecessárias a APIs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR, get_settings
from utils.logger import get_logger

logger = get_logger("cache")

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DiskCache:
    """Cache em disco com TTL e serialização JSON."""

    def __init__(
        self,
        namespace: str = "default",
        ttl: Optional[int] = None,
        directory: Optional[Path] = None,
    ) -> None:
        """
        Args:
            namespace: Namespace para separar caches diferentes.
            ttl: Time-to-live em segundos (None = usa config).
            directory: Diretório base do cache.
        """
        settings = get_settings()
        self.ttl = ttl or settings.cache_ttl
        self.namespace = namespace
        self.cache_dir = (directory or CACHE_DIR) / namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Optional[Any] = None

    def _get_cache(self) -> Any:
        """Retorna a instância do diskcache."""
        if self._cache is None:
            try:
                import diskcache
                self._cache = diskcache.Cache(
                    str(self.cache_dir),
                    size_limit=500 * 1024 * 1024,  # 500MB
                )
            except ImportError:
                logger.warning("diskcache_not_available", msg="Usando cache em JSON simples")
                self._cache = _SimpleJsonCache(self.cache_dir)
        return self._cache

    @staticmethod
    def _make_key(key: str) -> str:
        """Gera uma chave de cache normalizada."""
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Recupera valor do cache.

        Args:
            key: Chave do cache.
            default: Valor padrão se não encontrado.

        Returns:
            Valor armazenado ou default.
        """
        cache = self._get_cache()
        hashed_key = self._make_key(key)
        try:
            value = cache.get(hashed_key)
            if value is not None:
                logger.debug("cache_hit", key=key[:50], namespace=self.namespace)
                return value
        except Exception as exc:
            logger.warning("cache_get_error", key=key[:50], error=str(exc))
        return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Armazena valor no cache.

        Args:
            key: Chave do cache.
            value: Valor a armazenar (deve ser serializável).
            ttl: TTL específico em segundos.

        Returns:
            True se armazenado com sucesso.
        """
        cache = self._get_cache()
        hashed_key = self._make_key(key)
        expire = ttl or self.ttl
        try:
            cache.set(hashed_key, value, expire=expire)
            logger.debug("cache_set", key=key[:50], namespace=self.namespace, ttl=expire)
            return True
        except Exception as exc:
            logger.warning("cache_set_error", key=key[:50], error=str(exc))
            return False

    def delete(self, key: str) -> bool:
        """Remove uma entrada do cache."""
        cache = self._get_cache()
        hashed_key = self._make_key(key)
        try:
            cache.delete(hashed_key)
            return True
        except Exception as exc:
            logger.warning("cache_delete_error", key=key[:50], error=str(exc))
            return False

    def clear(self) -> None:
        """Limpa todo o cache do namespace."""
        cache = self._get_cache()
        try:
            cache.clear()
            logger.info("cache_cleared", namespace=self.namespace)
        except Exception as exc:
            logger.warning("cache_clear_error", error=str(exc))

    def close(self) -> None:
        """Fecha o cache."""
        if self._cache is not None:
            try:
                self._cache.close()
            except Exception:
                pass
            self._cache = None


class _SimpleJsonCache:
    """Cache JSON simples como fallback quando diskcache não está disponível."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._index_file = directory / "_index.json"
        self._index: dict[str, dict[str, Any]] = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Carrega o índice do cache."""
        if self._index_file.exists():
            try:
                return json.loads(self._index_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self) -> None:
        """Salva o índice do cache."""
        self._index_file.write_text(
            json.dumps(self._index, indent=2), encoding="utf-8"
        )

    def get(self, key: str) -> Any:
        """Recupera valor do cache."""
        import time

        entry = self._index.get(key)
        if entry is None:
            return None

        # Check TTL
        if entry.get("expire") and time.time() > entry["expire"]:
            self.delete(key)
            return None

        data_file = self.directory / f"{key}.json"
        if data_file.exists():
            try:
                return json.loads(data_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """Armazena valor no cache."""
        import time

        data_file = self.directory / f"{key}.json"
        try:
            data_file.write_text(json.dumps(value, default=str), encoding="utf-8")
            self._index[key] = {
                "created": time.time(),
                "expire": time.time() + expire if expire else None,
            }
            self._save_index()
        except (TypeError, OSError) as exc:
            logger.warning("simple_cache_set_error", error=str(exc))

    def delete(self, key: str) -> None:
        """Remove uma entrada do cache."""
        data_file = self.directory / f"{key}.json"
        if data_file.exists():
            data_file.unlink(missing_ok=True)
        self._index.pop(key, None)
        self._save_index()

    def clear(self) -> None:
        """Limpa todo o cache."""
        import shutil
        for f in self.directory.glob("*.json"):
            f.unlink(missing_ok=True)
        self._index.clear()

    def close(self) -> None:
        """No-op para compatibilidade."""
        pass


# Cache instances (singletons por namespace)
_instances: dict[str, DiskCache] = {}


def get_cache(namespace: str = "default", ttl: Optional[int] = None) -> DiskCache:
    """
    Retorna instância de cache para o namespace (singleton).

    Args:
        namespace: Namespace do cache.
        ttl: TTL em segundos.

    Returns:
        Instância de DiskCache.
    """
    if namespace not in _instances:
        _instances[namespace] = DiskCache(namespace=namespace, ttl=ttl)
    return _instances[namespace]
