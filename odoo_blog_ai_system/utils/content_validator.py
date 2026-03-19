"""
Validador de qualidade de conteúdo.

Verifica qualidade do conteúdo gerado antes da publicação:
contagem de palavras, estrutura de headings, parágrafos longos,
links, HTML válido, e mais.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger
from utils.text_processing import count_words, extract_headings, strip_html_tags

logger = get_logger("content_validator")


@dataclass
class ValidationResult:
    """Resultado de uma validação individual."""
    check_name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentValidationReport:
    """Relatório completo de validação de conteúdo."""
    is_valid: bool = True
    results: list[ValidationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    word_count: int = 0

    def add_result(self, result: ValidationResult) -> None:
        """Adiciona um resultado de validação."""
        self.results.append(result)
        if not result.passed:
            if result.severity == "error":
                self.is_valid = False
                self.errors.append(result.message)
            elif result.severity == "warning":
                self.warnings.append(result.message)
        else:
            self.info.append(result.message)

    def summary(self) -> str:
        """Gera um resumo textual do relatório."""
        lines = [
            f"Content Validation: {'✅ PASS' if self.is_valid else '❌ FAIL'}",
            f"Word Count: {self.word_count}",
            f"Results: {len(self.results)} checks",
            f"  Errors: {len(self.errors)}",
            f"  Warnings: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for e in self.errors:
                lines.append(f"  ❌ {e}")
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")
        return "\n".join(lines)


class ContentValidator:
    """Validador de qualidade de conteúdo para artigos do blog."""

    def __init__(
        self,
        min_words: int = 1500,
        max_words: int = 2500,
        max_paragraph_words: int = 300,
        min_headings: int = 3,
        max_heading_gap_words: int = 300,
        min_internal_links: int = 3,
        max_keyword_density: float = 0.03,
    ) -> None:
        self.min_words = min_words
        self.max_words = max_words
        self.max_paragraph_words = max_paragraph_words
        self.min_headings = min_headings
        self.max_heading_gap_words = max_heading_gap_words
        self.min_internal_links = min_internal_links
        self.max_keyword_density = max_keyword_density

    def validate(
        self,
        html_content: str,
        keyword_primary: str = "",
        title: str = "",
        meta_description: str = "",
        slug: str = "",
    ) -> ContentValidationReport:
        """
        Executa todas as validações no conteúdo.

        Args:
            html_content: HTML do artigo.
            keyword_primary: Keyword principal.
            title: Título do artigo.
            meta_description: Meta description.
            slug: Slug do artigo.

        Returns:
            Relatório de validação completo.
        """
        report = ContentValidationReport()
        plain_text = strip_html_tags(html_content)
        report.word_count = count_words(plain_text)

        # Run all checks
        self._check_word_count(report, plain_text)
        self._check_title(report, title, keyword_primary)
        self._check_meta_description(report, meta_description, keyword_primary)
        self._check_slug(report, slug)
        self._check_heading_structure(report, html_content)
        self._check_paragraph_length(report, html_content)
        self._check_keyword_presence(report, plain_text, keyword_primary)
        self._check_keyword_density(report, plain_text, keyword_primary)
        self._check_keyword_in_first_100(report, plain_text, keyword_primary)
        self._check_lists_presence(report, html_content)
        self._check_links(report, html_content)
        self._check_images(report, html_content)
        self._check_html_validity(report, html_content)

        return report

    def _check_word_count(self, report: ContentValidationReport, plain_text: str) -> None:
        """Verifica contagem de palavras."""
        wc = report.word_count
        if wc < self.min_words:
            report.add_result(ValidationResult(
                check_name="word_count",
                passed=False,
                message=f"Artigo muito curto: {wc} palavras (mínimo: {self.min_words})",
                severity="error",
                details={"current": wc, "min": self.min_words},
            ))
        elif wc > self.max_words:
            report.add_result(ValidationResult(
                check_name="word_count",
                passed=False,
                message=f"Artigo muito longo: {wc} palavras (máximo: {self.max_words})",
                severity="warning",
                details={"current": wc, "max": self.max_words},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="word_count",
                passed=True,
                message=f"Contagem de palavras OK: {wc}",
                details={"current": wc},
            ))

    def _check_title(
        self, report: ContentValidationReport, title: str, keyword: str
    ) -> None:
        """Verifica o título."""
        if not title:
            report.add_result(ValidationResult(
                check_name="title",
                passed=False,
                message="Título ausente",
                severity="error",
            ))
            return

        if len(title) > 60:
            report.add_result(ValidationResult(
                check_name="title_length",
                passed=False,
                message=f"Título muito longo: {len(title)} chars (max: 60)",
                severity="warning",
                details={"length": len(title)},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="title_length",
                passed=True,
                message=f"Comprimento do título OK: {len(title)} chars",
            ))

        if keyword and keyword.lower() not in title.lower():
            report.add_result(ValidationResult(
                check_name="title_keyword",
                passed=False,
                message=f"Keyword '{keyword}' não encontrada no título",
                severity="warning",
            ))
        elif keyword:
            report.add_result(ValidationResult(
                check_name="title_keyword",
                passed=True,
                message="Keyword presente no título",
            ))

    def _check_meta_description(
        self, report: ContentValidationReport, desc: str, keyword: str
    ) -> None:
        """Verifica a meta description."""
        if not desc:
            report.add_result(ValidationResult(
                check_name="meta_description",
                passed=False,
                message="Meta description ausente",
                severity="error",
            ))
            return

        if len(desc) < 120 or len(desc) > 160:
            report.add_result(ValidationResult(
                check_name="meta_description_length",
                passed=False,
                message=f"Meta description fora do ideal: {len(desc)} chars (ideal: 150-160)",
                severity="warning",
                details={"length": len(desc)},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="meta_description_length",
                passed=True,
                message=f"Meta description OK: {len(desc)} chars",
            ))

        if keyword and keyword.lower() not in desc.lower():
            report.add_result(ValidationResult(
                check_name="meta_description_keyword",
                passed=False,
                message="Keyword não encontrada na meta description",
                severity="warning",
            ))

    def _check_slug(self, report: ContentValidationReport, slug: str) -> None:
        """Verifica o slug."""
        if not slug:
            report.add_result(ValidationResult(
                check_name="slug",
                passed=False,
                message="Slug ausente",
                severity="error",
            ))
            return

        if not re.match(r"^[a-z0-9-]+$", slug):
            report.add_result(ValidationResult(
                check_name="slug_format",
                passed=False,
                message="Slug contém caracteres inválidos",
                severity="error",
            ))
        elif len(slug.split("-")) > 7:
            report.add_result(ValidationResult(
                check_name="slug_length",
                passed=False,
                message=f"Slug muito longo: {len(slug.split('-'))} palavras (max: 5-7)",
                severity="warning",
            ))
        else:
            report.add_result(ValidationResult(
                check_name="slug",
                passed=True,
                message="Slug OK",
            ))

    def _check_heading_structure(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verifica a estrutura de headings."""
        headings = extract_headings(html_content)

        if not headings:
            report.add_result(ValidationResult(
                check_name="headings",
                passed=False,
                message="Nenhum heading encontrado",
                severity="error",
            ))
            return

        h1_count = sum(1 for h in headings if h["level"] == "h1")
        h2_count = sum(1 for h in headings if h["level"] == "h2")

        if h1_count > 1:
            report.add_result(ValidationResult(
                check_name="h1_count",
                passed=False,
                message=f"Múltiplos H1 encontrados: {h1_count} (deve ser 1)",
                severity="warning",
            ))

        if h2_count < self.min_headings:
            report.add_result(ValidationResult(
                check_name="h2_count",
                passed=False,
                message=f"Poucos H2: {h2_count} (mínimo: {self.min_headings})",
                severity="warning",
                details={"count": h2_count, "min": self.min_headings},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="heading_structure",
                passed=True,
                message=f"Estrutura de headings OK: {h2_count} H2s",
            ))

    def _check_paragraph_length(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verifica se há parágrafos muito longos."""
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_content, re.DOTALL | re.IGNORECASE)
        long_paragraphs = 0

        for p in paragraphs:
            p_words = count_words(p)
            if p_words > self.max_paragraph_words:
                long_paragraphs += 1

        if long_paragraphs > 0:
            report.add_result(ValidationResult(
                check_name="paragraph_length",
                passed=False,
                message=f"{long_paragraphs} parágrafo(s) com mais de {self.max_paragraph_words} palavras",
                severity="warning",
                details={"long_paragraphs": long_paragraphs},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="paragraph_length",
                passed=True,
                message="Todos os parágrafos dentro do limite",
            ))

    def _check_keyword_presence(
        self, report: ContentValidationReport, plain_text: str, keyword: str
    ) -> None:
        """Verifica presença da keyword no conteúdo."""
        if not keyword:
            return

        if keyword.lower() not in plain_text.lower():
            report.add_result(ValidationResult(
                check_name="keyword_presence",
                passed=False,
                message=f"Keyword '{keyword}' não encontrada no conteúdo",
                severity="error",
            ))
        else:
            count = plain_text.lower().count(keyword.lower())
            report.add_result(ValidationResult(
                check_name="keyword_presence",
                passed=True,
                message=f"Keyword encontrada {count} vezes",
                details={"occurrences": count},
            ))

    def _check_keyword_density(
        self, report: ContentValidationReport, plain_text: str, keyword: str
    ) -> None:
        """Verifica densidade da keyword."""
        if not keyword:
            return

        from utils.text_processing import calculate_keyword_density
        density = calculate_keyword_density(plain_text, keyword)

        if density > self.max_keyword_density:
            report.add_result(ValidationResult(
                check_name="keyword_density",
                passed=False,
                message=(
                    f"Keyword stuffing detectado: {density:.1%} "
                    f"(máximo: {self.max_keyword_density:.1%})"
                ),
                severity="warning",
                details={"density": density, "max": self.max_keyword_density},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="keyword_density",
                passed=True,
                message=f"Densidade da keyword OK: {density:.1%}",
                details={"density": density},
            ))

    def _check_keyword_in_first_100(
        self, report: ContentValidationReport, plain_text: str, keyword: str
    ) -> None:
        """Verifica se a keyword aparece nos primeiros 100 caracteres."""
        if not keyword:
            return

        first_100 = plain_text[:100].lower()
        if keyword.lower() in first_100:
            report.add_result(ValidationResult(
                check_name="keyword_first_100",
                passed=True,
                message="Keyword presente nos primeiros 100 caracteres",
            ))
        else:
            report.add_result(ValidationResult(
                check_name="keyword_first_100",
                passed=False,
                message="Keyword ausente nos primeiros 100 caracteres",
                severity="warning",
            ))

    def _check_lists_presence(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verifica presença de listas para escaneabilidade."""
        ul_count = html_content.lower().count("<ul")
        ol_count = html_content.lower().count("<ol")
        total_lists = ul_count + ol_count

        if total_lists == 0:
            report.add_result(ValidationResult(
                check_name="lists_presence",
                passed=False,
                message="Nenhuma lista (ul/ol) encontrada — prejudica escaneabilidade",
                severity="warning",
            ))
        else:
            report.add_result(ValidationResult(
                check_name="lists_presence",
                passed=True,
                message=f"Listas encontradas: {total_lists}",
            ))

    def _check_links(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verifica presença de links internos e externos."""
        internal_links = re.findall(r'<a[^>]+href=["\'](?!/|http)', html_content, re.IGNORECASE)
        all_links = re.findall(r'<a[^>]+href=["\']([^"\']+)', html_content, re.IGNORECASE)
        relative_links = [l for l in all_links if l.startswith("/")]
        external_links = [l for l in all_links if l.startswith("http")]

        total_internal = len(relative_links) + len(internal_links)

        if total_internal < self.min_internal_links:
            report.add_result(ValidationResult(
                check_name="internal_links",
                passed=False,
                message=f"Poucos links internos: {total_internal} (mínimo: {self.min_internal_links})",
                severity="warning",
                details={"count": total_internal, "min": self.min_internal_links},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="internal_links",
                passed=True,
                message=f"Links internos OK: {total_internal}",
            ))

        # Check for generic anchor text
        generic_anchors = re.findall(
            r'<a[^>]*>(?:clique aqui|saiba mais|leia mais|click here|read more)</a>',
            html_content,
            re.IGNORECASE,
        )
        if generic_anchors:
            report.add_result(ValidationResult(
                check_name="generic_anchors",
                passed=False,
                message=f"{len(generic_anchors)} link(s) com anchor text genérico",
                severity="warning",
            ))

    def _check_images(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verifica imagens no conteúdo."""
        images = re.findall(r"<img[^>]*>", html_content, re.IGNORECASE)

        if not images:
            report.add_result(ValidationResult(
                check_name="images",
                passed=False,
                message="Nenhuma imagem encontrada no conteúdo",
                severity="warning",
            ))
            return

        # Check alt text
        missing_alt = 0
        for img in images:
            if 'alt=""' in img or "alt=" not in img:
                missing_alt += 1

        if missing_alt > 0:
            report.add_result(ValidationResult(
                check_name="image_alt_text",
                passed=False,
                message=f"{missing_alt} imagem(ns) sem alt text",
                severity="warning",
            ))
        else:
            report.add_result(ValidationResult(
                check_name="images",
                passed=True,
                message=f"Imagens OK: {len(images)} com alt text",
            ))

    def _check_html_validity(
        self, report: ContentValidationReport, html_content: str
    ) -> None:
        """Verificação básica de HTML válido."""
        # Check for unclosed tags (simplified)
        opening_tags = re.findall(r"<([a-z][a-z0-9]*)\b[^>]*/?>", html_content, re.IGNORECASE)
        closing_tags = re.findall(r"</([a-z][a-z0-9]*)\s*>", html_content, re.IGNORECASE)

        self_closing = {"img", "br", "hr", "input", "meta", "link", "source"}
        opening_filtered = [t.lower() for t in opening_tags if t.lower() not in self_closing]
        closing_filtered = [t.lower() for t in closing_tags]

        # Simple check: count mismatches
        from collections import Counter
        open_counts = Counter(opening_filtered)
        close_counts = Counter(closing_filtered)

        mismatches: list[str] = []
        for tag in set(list(open_counts.keys()) + list(close_counts.keys())):
            diff = open_counts.get(tag, 0) - close_counts.get(tag, 0)
            if abs(diff) > 0 and tag not in {"p", "li", "td", "th", "tr"}:
                mismatches.append(f"<{tag}>: {diff:+d}")

        if mismatches:
            report.add_result(ValidationResult(
                check_name="html_validity",
                passed=False,
                message=f"Possíveis tags HTML não fechadas: {', '.join(mismatches[:5])}",
                severity="warning",
                details={"mismatches": mismatches},
            ))
        else:
            report.add_result(ValidationResult(
                check_name="html_validity",
                passed=True,
                message="HTML basicamente válido",
            ))
