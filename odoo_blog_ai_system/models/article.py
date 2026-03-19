"""
Modelo de dados do Artigo.

Define a estrutura completa de um artigo gerado pelo sistema,
incluindo metadados, conteúdo, informações SEO e status de publicação.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ArticleStatus(str, Enum):
    """Status do ciclo de vida do artigo."""
    DRAFT = "draft"
    GENERATED = "generated"
    OPTIMIZED = "optimized"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class FAQItem(BaseModel):
    """Item de FAQ com pergunta e resposta."""
    question: str = Field(..., min_length=10, description="Pergunta da FAQ")
    answer: str = Field(..., min_length=20, description="Resposta da FAQ")


class ImageInfo(BaseModel):
    """Informações de uma imagem associada ao artigo."""
    url: str = Field(default="", description="URL da imagem")
    local_path: str = Field(default="", description="Caminho local da imagem")
    alt_text: str = Field(default="", max_length=125, description="Alt text da imagem")
    title_text: str = Field(default="", description="Title text da imagem")
    filename: str = Field(default="", description="Nome do arquivo SEO-friendly")
    width: int = Field(default=0, description="Largura em pixels")
    height: int = Field(default=0, description="Altura em pixels")
    is_cover: bool = Field(default=False, description="Se é a imagem de capa")
    odoo_attachment_id: Optional[int] = Field(default=None, description="ID do attachment no Odoo")


class ArticleMetadata(BaseModel):
    """Metadados do artigo para rastreamento e SEO."""
    keyword_primary: str = Field(default="", description="Keyword principal")
    keywords_secondary: list[str] = Field(default_factory=list, description="Keywords secundárias")
    keywords_lsi: list[str] = Field(default_factory=list, description="Keywords LSI")
    search_intent: str = Field(default="informacional", description="Intenção de busca")
    article_type: str = Field(default="guia", description="Tipo de artigo")
    tone: str = Field(default="professional", description="Tom de voz")
    depth: str = Field(default="intermediate", description="Nível de profundidade")
    language: str = Field(default="pt-br", description="Idioma")
    word_count: int = Field(default=0, description="Contagem de palavras")
    reading_time_minutes: int = Field(default=0, description="Tempo estimado de leitura")
    seo_score: float = Field(default=0.0, ge=0, le=100, description="Score SEO (0-100)")
    readability_score: float = Field(default=0.0, description="Score de legibilidade")
    keyword_density: float = Field(default=0.0, description="Densidade da keyword principal")
    internal_links_count: int = Field(default=0, description="Quantidade de links internos")
    external_links_count: int = Field(default=0, description="Quantidade de links externos")
    llm_provider: str = Field(default="", description="Provider LLM usado na geração")
    llm_model: str = Field(default="", description="Modelo LLM usado na geração")
    generation_cost_usd: float = Field(default=0.0, description="Custo estimado de geração (USD)")
    generation_time_seconds: float = Field(default=0.0, description="Tempo de geração em segundos")


class SchemaMarkup(BaseModel):
    """Schema markup JSON-LD para o artigo."""
    article_schema: dict[str, Any] = Field(default_factory=dict, description="Article schema")
    faq_schema: dict[str, Any] = Field(default_factory=dict, description="FAQ schema")
    breadcrumb_schema: dict[str, Any] = Field(default_factory=dict, description="Breadcrumb schema")
    organization_schema: dict[str, Any] = Field(default_factory=dict, description="Organization schema")
    author_schema: dict[str, Any] = Field(default_factory=dict, description="Author schema")


class Article(BaseModel):
    """Modelo completo de um artigo do blog."""

    # ── Identificação ──────────────────────────
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único do artigo")
    odoo_post_id: Optional[int] = Field(default=None, description="ID do post no Odoo")

    # ── Conteúdo Principal ─────────────────────
    title: str = Field(default="", max_length=80, description="Título principal (H1)")
    subtitle: str = Field(default="", max_length=160, description="Subtítulo")
    slug: str = Field(default="", max_length=100, description="Slug SEO-friendly")
    meta_title: str = Field(default="", max_length=60, description="Meta title")
    meta_description: str = Field(default="", max_length=160, description="Meta description")
    content_html: str = Field(default="", description="Conteúdo HTML completo")
    introduction: str = Field(default="", description="Introdução em texto puro")
    conclusion: str = Field(default="", description="Conclusão em texto puro")
    content_plain: str = Field(default="", description="Conteúdo em texto puro (para análises)")

    # ── FAQ ─────────────────────────────────────
    faq_items: list[FAQItem] = Field(default_factory=list, description="Itens de FAQ")

    # ── Imagens ─────────────────────────────────
    cover_image: Optional[ImageInfo] = Field(default=None, description="Imagem de capa")
    content_images: list[ImageInfo] = Field(default_factory=list, description="Imagens no corpo")

    # ── Tags e Categorias ──────────────────────
    tags: list[str] = Field(default_factory=list, description="Tags do artigo")
    tag_ids: list[int] = Field(default_factory=list, description="IDs de tags no Odoo")
    blog_id: int = Field(default=1, description="ID do blog no Odoo")
    category: str = Field(default="", description="Categoria principal")

    # ── SEO e Metadados ────────────────────────
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata, description="Metadados")
    schema_markup: SchemaMarkup = Field(default_factory=SchemaMarkup, description="Schema markup")
    canonical_url: str = Field(default="", description="URL canônica")

    # ── Links ──────────────────────────────────
    internal_links: list[dict[str, str]] = Field(
        default_factory=list,
        description="Links internos [{url, anchor, target_article_id}]"
    )
    external_links: list[dict[str, str]] = Field(
        default_factory=list,
        description="Links externos [{url, anchor}]"
    )

    # ── Status e Timestamps ────────────────────
    status: ArticleStatus = Field(default=ArticleStatus.DRAFT, description="Status do artigo")
    author_name: str = Field(default="Equipe Editorial", description="Nome do autor")
    author_id: Optional[int] = Field(default=None, description="ID do autor no Odoo")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Data de criação")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Última atualização")
    published_at: Optional[datetime] = Field(default=None, description="Data de publicação")
    scheduled_at: Optional[datetime] = Field(default=None, description="Data agendada para publicação")

    # ── Cluster / Linking ──────────────────────
    cluster_id: Optional[str] = Field(default=None, description="ID do cluster de keywords")
    is_pillar: bool = Field(default=False, description="Se é um artigo pilar")
    parent_pillar_id: Optional[str] = Field(default=None, description="ID do artigo pilar pai")

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, v: str) -> str:
        """Normaliza o slug para ser SEO-friendly."""
        if v:
            return v.lower().strip().replace(" ", "-")
        return v

    @property
    def is_published(self) -> bool:
        """Verifica se o artigo está publicado."""
        return self.status == ArticleStatus.PUBLISHED

    @property
    def is_ready_to_publish(self) -> bool:
        """Verifica se o artigo está pronto para publicação."""
        return self.status in (ArticleStatus.READY, ArticleStatus.SCHEDULED)

    def mark_as_generated(self) -> None:
        """Marca o artigo como gerado."""
        self.status = ArticleStatus.GENERATED
        self.updated_at = datetime.utcnow()

    def mark_as_optimized(self, seo_score: float = 0.0) -> None:
        """Marca o artigo como otimizado."""
        self.status = ArticleStatus.OPTIMIZED
        self.metadata.seo_score = seo_score
        self.updated_at = datetime.utcnow()

    def mark_as_ready(self) -> None:
        """Marca o artigo como pronto para publicação."""
        self.status = ArticleStatus.READY
        self.updated_at = datetime.utcnow()

    def mark_as_published(self, odoo_post_id: int) -> None:
        """Marca o artigo como publicado."""
        self.status = ArticleStatus.PUBLISHED
        self.odoo_post_id = odoo_post_id
        self.published_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self) -> None:
        """Marca o artigo como falha."""
        self.status = ArticleStatus.FAILED
        self.updated_at = datetime.utcnow()

    def to_odoo_dict(self) -> dict[str, Any]:
        """Converte para dicionário compatível com campos do Odoo blog.post."""
        data: dict[str, Any] = {
            "name": self.title,
            "subtitle": self.subtitle,
            "content": self.content_html,
            "blog_id": self.blog_id,
            "website_meta_title": self.meta_title or self.title[:60],
            "website_meta_description": self.meta_description,
            "website_meta_keywords": ", ".join(
                [self.metadata.keyword_primary] + self.metadata.keywords_secondary
            ),
            "website_published": self.status == ArticleStatus.PUBLISHED,
        }
        if self.tag_ids:
            data["tag_ids"] = [(6, 0, self.tag_ids)]
        if self.author_id:
            data["author_id"] = self.author_id
        if self.scheduled_at:
            data["post_date"] = self.scheduled_at.strftime("%Y-%m-%d %H:%M:%S")
        if self.cover_image and self.cover_image.odoo_attachment_id:
            import json
            cover_props = json.dumps({
                "background-image": f"url('/web/image/{self.cover_image.odoo_attachment_id}')",
                "background_type": "image",
                "resize_class": "o_record_has_cover o_half_screen_height",
                "opacity": "0",
            })
            data["cover_properties"] = cover_props
        return data

    def to_storage_dict(self) -> dict[str, Any]:
        """Serializa para armazenamento em JSON."""
        return self.model_dump(mode="json")

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> Article:
        """Deserializa de dicionário armazenado."""
        return cls.model_validate(data)
