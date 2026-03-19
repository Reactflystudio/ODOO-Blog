"""
Modelo de dados de Keywords e Clusters.

Define a estrutura para keywords, clusters de keywords e
mapas de conteúdo para SEO programático.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from config import ArticleType, SearchIntent


class Keyword(BaseModel):
    """Modelo de uma keyword individual."""

    keyword: str = Field(..., min_length=1, description="Texto da keyword")
    slug: str = Field(default="", description="Slug da keyword")
    intent: SearchIntent = Field(
        default=SearchIntent.INFORMATIONAL,
        description="Intenção de busca",
    )
    priority: str = Field(default="medium", description="Prioridade (high/medium/low)")
    article_type: ArticleType = Field(
        default=ArticleType.GUIDE,
        description="Tipo de artigo sugerido",
    )
    estimated_volume: int = Field(default=0, ge=0, description="Volume estimado de buscas")
    estimated_difficulty: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Dificuldade estimada (0-1)"
    )
    opportunity_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Score de oportunidade"
    )
    source: str = Field(
        default="",
        description="Fonte da keyword (autocomplete, paa, related, llm, etc.)",
    )
    assigned_article_id: Optional[str] = Field(
        default=None, description="ID do artigo atribuído"
    )
    is_assigned: bool = Field(default=False, description="Se já foi atribuída a um artigo")
    parent_keyword: Optional[str] = Field(
        default=None, description="Keyword pai (se derivada)"
    )
    variations: list[str] = Field(default_factory=list, description="Variações da keyword")
    serp_features: list[str] = Field(
        default_factory=list,
        description="Features presentes na SERP (featured snippet, PAA, etc.)",
    )
    competitors: list[str] = Field(
        default_factory=list,
        description="Domínios competidores nas primeiras posições",
    )

    def calculate_opportunity_score(self) -> float:
        """Calcula o score de oportunidade baseado em volume vs dificuldade."""
        if self.estimated_volume <= 0:
            self.opportunity_score = 0.0
            return self.opportunity_score

        # Formula: (volume_normalizado * (1 - dificuldade)) * multiplicador_de_intenção
        volume_normalized = min(self.estimated_volume / 10000, 1.0) * 100
        intent_multiplier = {
            SearchIntent.TRANSACTIONAL: 1.5,
            SearchIntent.COMPARATIVE: 1.3,
            SearchIntent.INFORMATIONAL: 1.0,
            SearchIntent.NAVIGATIONAL: 0.7,
        }.get(self.intent, 1.0)

        self.opportunity_score = round(
            volume_normalized * (1 - self.estimated_difficulty) * intent_multiplier, 2
        )
        return self.opportunity_score

    def set_priority_from_score(self) -> str:
        """Define prioridade baseada no score de oportunidade."""
        if self.opportunity_score >= 70:
            self.priority = "high"
        elif self.opportunity_score >= 40:
            self.priority = "medium"
        else:
            self.priority = "low"
        return self.priority


class KeywordCluster(BaseModel):
    """Cluster de keywords agrupadas por intenção de busca."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID do cluster")
    intent: SearchIntent = Field(..., description="Intenção de busca do cluster")
    keywords: list[Keyword] = Field(default_factory=list, description="Keywords do cluster")
    primary_keyword: Optional[str] = Field(
        default=None, description="Keyword principal do cluster"
    )
    suggested_pillar_title: str = Field(
        default="", description="Título sugerido para artigo pilar"
    )

    @property
    def keyword_count(self) -> int:
        """Retorna a quantidade de keywords no cluster."""
        return len(self.keywords)

    @property
    def high_priority_count(self) -> int:
        """Retorna a quantidade de keywords de alta prioridade."""
        return sum(1 for kw in self.keywords if kw.priority == "high")

    def sort_by_priority(self) -> None:
        """Ordena keywords por score de oportunidade (decrescente)."""
        priority_map = {"high": 3, "medium": 2, "low": 1}
        self.keywords.sort(
            key=lambda kw: (priority_map.get(kw.priority, 0), kw.opportunity_score),
            reverse=True,
        )

    def add_keyword(self, keyword: Keyword) -> None:
        """Adiciona keyword ao cluster, evitando duplicatas."""
        existing_texts = {kw.keyword.lower().strip() for kw in self.keywords}
        if keyword.keyword.lower().strip() not in existing_texts:
            self.keywords.append(keyword)


class InterlinkMapping(BaseModel):
    """Mapeamento de interlink entre artigos."""
    from_article_id: str = Field(..., description="ID do artigo de origem")
    to_article_id: str = Field(..., description="ID do artigo de destino")
    anchor_text: str = Field(..., description="Texto âncora do link")
    from_keyword: str = Field(default="", description="Keyword do artigo de origem")
    to_keyword: str = Field(default="", description="Keyword do artigo de destino")


class ContentMap(BaseModel):
    """Mapa de conteúdo completo para uma seed keyword."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID do content map")
    seed_keyword: str = Field(..., description="Keyword semente")
    clusters: list[KeywordCluster] = Field(
        default_factory=list, description="Clusters de keywords"
    )
    pillar_article: Optional[dict[str, Any]] = Field(
        default=None,
        description="Informações do artigo pilar",
    )
    interlinks: list[InterlinkMapping] = Field(
        default_factory=list, description="Mapeamento de interlinks"
    )
    total_keywords: int = Field(default=0, description="Total de keywords descobertas")
    total_articles_planned: int = Field(default=0, description="Total de artigos planejados")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Data de criação")

    def calculate_totals(self) -> None:
        """Calcula totais do content map."""
        self.total_keywords = sum(c.keyword_count for c in self.clusters)
        self.total_articles_planned = self.total_keywords + (1 if self.pillar_article else 0)

    def get_all_keywords(self) -> list[Keyword]:
        """Retorna todas as keywords de todos os clusters."""
        all_kws: list[Keyword] = []
        for cluster in self.clusters:
            all_kws.extend(cluster.keywords)
        return all_kws

    def get_keywords_by_priority(self, priority: str) -> list[Keyword]:
        """Retorna keywords filtradas por prioridade."""
        return [kw for kw in self.get_all_keywords() if kw.priority == priority]

    def to_storage_dict(self) -> dict[str, Any]:
        """Serializa para armazenamento."""
        return self.model_dump(mode="json")

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> ContentMap:
        """Deserializa de dicionário armazenado."""
        return cls.model_validate(data)
