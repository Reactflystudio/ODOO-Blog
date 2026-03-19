"""
Configurações centralizadas do sistema de automação de blog SEO + Odoo.

Utiliza Pydantic Settings para validação, tipagem e carregamento
automático de variáveis de ambiente a partir do arquivo .env.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class LLMProvider(str, Enum):
    """Provedores de LLM suportados."""
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ImageProvider(str, Enum):
    """Provedores de geração de imagem suportados."""
    DALLE = "dalle"
    IMAGEN = "imagen"
    STABLE_DIFFUSION = "stable_diffusion"
    GOOGLE_IMAGEN = "google_imagen"



class ToneOfVoice(str, Enum):
    """Tons de voz para geração de conteúdo."""
    FORMAL = "formal"
    INFORMAL = "informal"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    PROFESSIONAL = "professional"


class ContentDepth(str, Enum):
    """Nível de profundidade do conteúdo."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ArticleType(str, Enum):
    """Tipos de artigo suportados."""
    HOW_TO = "how-to"
    LISTICLE = "listicle"
    GUIDE = "guia"
    COMPARISON = "comparativo"
    CASE_STUDY = "case-study"
    REVIEW = "review"
    TUTORIAL = "tutorial"


class SearchIntent(str, Enum):
    """Intenções de busca para classificação de keywords."""
    INFORMATIONAL = "informacional"
    NAVIGATIONAL = "navegacional"
    TRANSACTIONAL = "transacional"
    COMPARATIVE = "comparativa"


# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GENERATED_ARTICLES_DIR = DATA_DIR / "generated_articles"
IMAGES_DIR = DATA_DIR / "images"
KEYWORDS_DIR = DATA_DIR / "keywords"
LOGS_DIR = DATA_DIR / "logs"
DB_DIR = DATA_DIR / "db"
EXAMPLES_DIR = DATA_DIR / "examples"

# Create directories if they don't exist
for _dir in (GENERATED_ARTICLES_DIR, IMAGES_DIR, KEYWORDS_DIR, LOGS_DIR, DB_DIR, EXAMPLES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────
class Settings(BaseSettings):
    """Configurações centralizadas carregadas do .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Providers ──────────────────────────
    openai_api_key: str = Field(default="", description="Chave da API OpenAI")
    google_ai_api_key: str = Field(default="", description="Chave da API Google AI")
    anthropic_api_key: str = Field(default="", description="Chave da API Anthropic")
    ollama_url: str = Field(default="http://localhost:11434", description="URL do Ollama")
    default_llm_provider: LLMProvider = Field(
        default=LLMProvider.OLLAMA,
        description="Provedor LLM padrão",
    )
    openai_model: str = Field(default="gpt-4o", description="Modelo OpenAI")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Modelo Gemini")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", description="Modelo Anthropic")
    ollama_model: str = Field(default="qwen3:8b", description="Modelo Ollama")

    # ── Odoo Connection ────────────────────────
    odoo_url: str = Field(default="", description="URL do Odoo")
    odoo_db: str = Field(default="", description="Nome do banco Odoo")
    odoo_username: str = Field(default="", description="Usuário Odoo")
    odoo_password: str = Field(default="", description="Senha Odoo")
    odoo_blog_id: int = Field(default=4, description="ID do blog no Odoo")

    # ── Image Generation ───────────────────────
    image_provider: ImageProvider = Field(
        default=ImageProvider.GOOGLE_IMAGEN,
        description="Provedor de geração de imagem",
    )
    unsplash_api_key: str = Field(default="", description="Chave Unsplash (fallback)")
    pexels_api_key: str = Field(default="", description="Chave Pexels (fallback)")

    # ── Scraping APIs ──────────────────────────
    news_api_key: str = Field(default="", description="Chave NewsAPI")
    reddit_client_id: str = Field(default="", description="Reddit Client ID")
    reddit_client_secret: str = Field(default="", description="Reddit Client Secret")
    twitter_bearer_token: str = Field(default="", description="Twitter Bearer Token")

    # ── Content Settings ───────────────────────
    default_language: str = Field(default="pt-br", description="Idioma padrão")
    default_tone: ToneOfVoice = Field(
        default=ToneOfVoice.PROFESSIONAL,
        description="Tom de voz padrão",
    )
    default_depth: ContentDepth = Field(
        default=ContentDepth.INTERMEDIATE,
        description="Profundidade padrão do conteúdo",
    )
    min_words: int = Field(default=1500, ge=500, description="Mínimo de palavras por artigo")
    max_words: int = Field(default=2500, le=10000, description="Máximo de palavras por artigo")
    articles_per_day: int = Field(default=5, ge=1, description="Artigos por dia no agendamento")
    default_author_name: str = Field(default="Equipe Editorial", description="Nome do autor padrão")

    # ── System ─────────────────────────────────
    log_level: str = Field(default="INFO", description="Nível de log")
    cache_ttl: int = Field(default=3600, ge=60, description="TTL do cache em segundos")
    max_concurrent_llm_calls: int = Field(default=5, ge=1, le=20, description="Max chamadas LLM simultâneas")
    llm_timeout_seconds: int = Field(default=120, ge=10, le=900, description="Timeout por chamada LLM (segundos)")
    proxy_url: Optional[str] = Field(default=None, description="URL do proxy (opcional)")
    db_path: str = Field(default="", description="Caminho do banco SQLite")

    # ── SEO Defaults ──────────────────────────
    keyword_density_min: float = Field(default=0.01, description="Densidade mínima keyword principal")
    keyword_density_max: float = Field(default=0.02, description="Densidade máxima keyword principal")
    keyword_stuffing_threshold: float = Field(default=0.03, description="Limiar de keyword stuffing")
    similarity_threshold: float = Field(default=0.85, description="Limiar de similaridade semântica")

    # ── Schedule ───────────────────────────────
    schedule_start_time: str = Field(default="08:00", description="Hora de início do agendamento")
    schedule_end_time: str = Field(default="18:00", description="Hora de fim do agendamento")

    @field_validator("db_path", mode="before")
    @classmethod
    def _set_default_db_path(cls, v: str) -> str:
        if not v:
            return str(DB_DIR / "state.db")
        return v

    @field_validator("min_words", "max_words", mode="after")
    @classmethod
    def _validate_word_range(cls, v: int) -> int:
        return v  # Pydantic ge/le handles bounds

    def get_llm_api_key(self, provider: Optional[LLMProvider] = None) -> str:
        """Retorna a API key para o provedor LLM especificado."""
        provider = provider or self.default_llm_provider
        mapping = {
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.GEMINI: self.google_ai_api_key,
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.OLLAMA: "local",  # Ollama doesn't need a key
        }
        key = mapping.get(provider, "")
        if not key:
            raise ValueError(f"API key não configurada para provider: {provider.value}")
        return key

    def get_llm_model(self, provider: Optional[LLMProvider] = None) -> str:
        """Retorna o nome do modelo para o provedor LLM especificado."""
        provider = provider or self.default_llm_provider
        mapping = {
            LLMProvider.OPENAI: self.openai_model,
            LLMProvider.GEMINI: self.gemini_model,
            LLMProvider.ANTHROPIC: self.anthropic_model,
            LLMProvider.OLLAMA: self.ollama_model,
        }
        return mapping.get(provider, self.openai_model)

    @property
    def llm_provider_fallback_order(self) -> list[LLMProvider]:
        """Retorna a ordem de fallback dos providers LLM (somente os configurados)."""
        order = [self.default_llm_provider]
        for provider in LLMProvider:
            if provider not in order:
                # Only add providers that have API keys configured
                # Skip Ollama in fallback (only use if explicitly set as default)
                if provider == LLMProvider.OLLAMA:
                    continue
                try:
                    key = self.get_llm_api_key(provider)
                    if key and key != "local":
                        order.append(provider)
                except ValueError:
                    continue
        return order


# Singleton-like access
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Retorna a instância de configurações (sempre recarrega do .env)."""
    global _settings
    _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Recarrega as configurações do .env."""
    global _settings
    _settings = Settings()
    return _settings
