"""
Modelo de Relatório SEO.

Define a estrutura de checks individuais de SEO,
scores parciais e o relatório completo com recomendações.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SEOCheckStatus(str, Enum):
    """Status de um check SEO individual."""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"


class SEOCheck(BaseModel):
    """Check individual de SEO com detalhes."""

    name: str = Field(..., description="Nome do check")
    category: str = Field(
        default="on-page",
        description="Categoria (on-page, content, technical, schema)"
    )
    status: SEOCheckStatus = Field(
        default=SEOCheckStatus.SKIPPED, description="Status do check"
    )
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score (0-100)")
    weight: float = Field(
        default=1.0, ge=0.0, le=10.0, description="Peso do check no score final"
    )
    message: str = Field(default="", description="Mensagem descritiva do resultado")
    recommendation: str = Field(default="", description="Recomendação de melhoria")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Detalhes adicionais"
    )
    auto_fixable: bool = Field(
        default=False, description="Se pode ser corrigido automaticamente"
    )

    @property
    def weighted_score(self) -> float:
        """Retorna o score ponderado pelo peso."""
        return self.score * self.weight

    def pass_check(self, message: str = "") -> None:
        """Marca o check como aprovado."""
        self.status = SEOCheckStatus.PASS
        self.score = 100.0
        self.message = message or f"✅ {self.name}: OK"

    def warn_check(self, message: str, score: float = 60.0) -> None:
        """Marca o check com aviso."""
        self.status = SEOCheckStatus.WARNING
        self.score = score
        self.message = f"⚠️ {self.name}: {message}"

    def fail_check(self, message: str, recommendation: str = "") -> None:
        """Marca o check como falha."""
        self.status = SEOCheckStatus.FAIL
        self.score = 0.0
        self.message = f"❌ {self.name}: {message}"
        self.recommendation = recommendation


class SEOScore(BaseModel):
    """Score SEO parcial por categoria."""

    category: str = Field(..., description="Categoria do score")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score da categoria")
    max_score: float = Field(default=100.0, description="Score máximo possível")
    checks_passed: int = Field(default=0, description="Checks aprovados")
    checks_warned: int = Field(default=0, description="Checks com aviso")
    checks_failed: int = Field(default=0, description="Checks falhados")
    checks_total: int = Field(default=0, description="Total de checks")


class SEOReport(BaseModel):
    """Relatório SEO completo de um artigo."""

    article_id: str = Field(..., description="ID do artigo analisado")
    article_title: str = Field(default="", description="Título do artigo")

    # ── Scores ─────────────────────────────────
    overall_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Score SEO geral (0-100)"
    )
    category_scores: list[SEOScore] = Field(
        default_factory=list, description="Scores por categoria"
    )

    # ── Checks ─────────────────────────────────
    checks: list[SEOCheck] = Field(
        default_factory=list, description="Lista de checks realizados"
    )

    # ── Resumo ─────────────────────────────────
    total_checks: int = Field(default=0, description="Total de checks")
    passed_checks: int = Field(default=0, description="Checks aprovados")
    warning_checks: int = Field(default=0, description="Checks com aviso")
    failed_checks: int = Field(default=0, description="Checks falhados")

    # ── Recomendações ──────────────────────────
    critical_issues: list[str] = Field(
        default_factory=list, description="Issues críticas"
    )
    warnings: list[str] = Field(default_factory=list, description="Avisos")
    recommendations: list[str] = Field(
        default_factory=list, description="Recomendações gerais"
    )
    auto_fixable_issues: list[str] = Field(
        default_factory=list, description="Issues que podem ser auto-corrigidas"
    )

    # ── Detalhes ───────────────────────────────
    keyword_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Análise detalhada de keywords"
    )
    content_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Análise detalhada de conteúdo"
    )
    technical_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Análise técnica"
    )

    # ── Timestamps ─────────────────────────────
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Data de geração"
    )

    def calculate_overall_score(self) -> float:
        """Calcula o score geral baseado nos checks ponderados."""
        if not self.checks:
            self.overall_score = 0.0
            return self.overall_score

        total_weight = sum(c.weight for c in self.checks)
        if total_weight == 0:
            self.overall_score = 0.0
            return self.overall_score

        weighted_sum = sum(c.weighted_score for c in self.checks)
        self.overall_score = round(weighted_sum / total_weight, 1)

        # Update counts
        self.total_checks = len(self.checks)
        self.passed_checks = sum(
            1 for c in self.checks if c.status == SEOCheckStatus.PASS
        )
        self.warning_checks = sum(
            1 for c in self.checks if c.status == SEOCheckStatus.WARNING
        )
        self.failed_checks = sum(
            1 for c in self.checks if c.status == SEOCheckStatus.FAIL
        )

        # Collect issues and recommendations
        self.critical_issues = [
            c.message for c in self.checks if c.status == SEOCheckStatus.FAIL
        ]
        self.warnings = [
            c.message for c in self.checks if c.status == SEOCheckStatus.WARNING
        ]
        self.recommendations = [
            c.recommendation for c in self.checks
            if c.recommendation and c.status != SEOCheckStatus.PASS
        ]
        self.auto_fixable_issues = [
            c.name for c in self.checks
            if c.auto_fixable and c.status in (SEOCheckStatus.FAIL, SEOCheckStatus.WARNING)
        ]

        # Calculate category scores
        self._calculate_category_scores()

        return self.overall_score

    def _calculate_category_scores(self) -> None:
        """Calcula scores por categoria."""
        categories: dict[str, list[SEOCheck]] = {}
        for check in self.checks:
            categories.setdefault(check.category, []).append(check)

        self.category_scores = []
        for cat_name, cat_checks in categories.items():
            total_w = sum(c.weight for c in cat_checks) or 1.0
            weighted_s = sum(c.weighted_score for c in cat_checks)
            score = round(weighted_s / total_w, 1)

            cat_score = SEOScore(
                category=cat_name,
                score=score,
                checks_passed=sum(
                    1 for c in cat_checks if c.status == SEOCheckStatus.PASS
                ),
                checks_warned=sum(
                    1 for c in cat_checks if c.status == SEOCheckStatus.WARNING
                ),
                checks_failed=sum(
                    1 for c in cat_checks if c.status == SEOCheckStatus.FAIL
                ),
                checks_total=len(cat_checks),
            )
            self.category_scores.append(cat_score)

    @property
    def grade(self) -> str:
        """Retorna a nota do relatório (A-F)."""
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"

    def to_summary_string(self) -> str:
        """Gera um resumo textual do relatório."""
        lines = [
            f"═══ SEO Report: {self.article_title} ═══",
            f"Overall Score: {self.overall_score}/100 (Grade: {self.grade})",
            f"Checks: {self.passed_checks}✅ {self.warning_checks}⚠️ {self.failed_checks}❌ / {self.total_checks} total",
            "",
        ]
        if self.category_scores:
            lines.append("Category Scores:")
            for cs in self.category_scores:
                lines.append(f"  • {cs.category}: {cs.score}/100")
            lines.append("")

        if self.critical_issues:
            lines.append("Critical Issues:")
            for issue in self.critical_issues:
                lines.append(f"  {issue}")
            lines.append("")

        if self.warnings:
            lines.append("Warnings:")
            for warn in self.warnings:
                lines.append(f"  {warn}")
            lines.append("")

        if self.recommendations:
            lines.append("Recommendations:")
            for rec in self.recommendations[:5]:
                lines.append(f"  → {rec}")

        return "\n".join(lines)
