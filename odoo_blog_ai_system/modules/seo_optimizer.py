"""
Módulo de Otimização SEO Automática.

Analisa e otimiza artigos para melhor performance nos motores de busca.
Gera relatório SEO detalhado com score 0-100 e recomendações.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from models.article import Article
from models.seo_report import SEOCheck, SEOCheckStatus, SEOReport
from utils.content_validator import ContentValidator
from utils.logger import get_logger
from utils.text_processing import (
    calculate_keyword_density,
    calculate_readability_score,
    count_words,
    extract_first_n_chars,
    extract_headings,
    strip_html_tags,
)

logger = get_logger("seo_optimizer")


class SEOOptimizer:
    """Otimizador SEO automático para artigos do blog."""

    def __init__(
        self,
        keyword_density_min: float = 0.01,
        keyword_density_max: float = 0.02,
        keyword_stuffing_threshold: float = 0.03,
        min_words: int = 1500,
        max_words: int = 2500,
    ) -> None:
        from config import get_settings
        settings = get_settings()
        self.kd_min = keyword_density_min or settings.keyword_density_min
        self.kd_max = keyword_density_max or settings.keyword_density_max
        self.kd_stuffing = keyword_stuffing_threshold or settings.keyword_stuffing_threshold
        self.min_words = min_words
        self.max_words = max_words
        self.content_validator = ContentValidator(
            min_words=self.min_words,
            max_words=self.max_words,
        )

    def analyze(self, article: Article) -> SEOReport:
        """
        Analisa um artigo e gera relatório SEO completo.

        Args:
            article: Artigo a ser analisado.

        Returns:
            Relatório SEO com score e recomendações.
        """
        logger.info("seo_analysis_start", article_id=article.id, title=article.title)

        report = SEOReport(
            article_id=article.id,
            article_title=article.title,
        )

        keyword = article.metadata.keyword_primary
        plain_text = strip_html_tags(article.content_html)
        full_text = f"{article.introduction} {plain_text} {article.conclusion}"

        # ── ON-PAGE SEO CHECKS ─────────────────
        self._check_meta_title(report, article)
        self._check_meta_description(report, article)
        self._check_slug(report, article, keyword)
        self._check_heading_hierarchy(report, article)
        self._check_keyword_density(report, full_text, keyword)
        self._check_keyword_first_100(report, full_text, keyword)
        self._check_keyword_in_headings(report, article, keyword)
        self._check_canonical_url(report, article)

        # ── CONTENT QUALITY CHECKS ─────────────
        self._check_word_count(report, full_text)
        self._check_paragraph_length(report, article)
        self._check_readability(report, full_text)
        self._check_lists_and_structure(report, article)
        self._check_images(report, article)

        # ── LINK CHECKS ───────────────────────
        self._check_internal_links(report, article)
        self._check_external_links(report, article)

        # ── SCHEMA MARKUP CHECKS ──────────────
        self._check_article_schema(report, article)
        self._check_faq_schema(report, article)

        # ── CONTENT QUALITY ────────────────────
        self._check_faq_section(report, article)
        self._check_introduction(report, article)
        self._check_conclusion(report, article)

        # Calculate overall score
        report.calculate_overall_score()

        # Store analysis details
        report.keyword_analysis = {
            "primary": keyword,
            "density": calculate_keyword_density(full_text, keyword),
            "count": full_text.lower().count(keyword.lower()) if keyword else 0,
            "secondary_count": len(article.metadata.keywords_secondary),
        }
        report.content_analysis = {
            "word_count": count_words(full_text),
            "readability_score": calculate_readability_score(full_text),
            "heading_count": len(extract_headings(article.content_html)),
            "paragraph_count": len(re.findall(r"<p[^>]*>", article.content_html, re.IGNORECASE)),
        }

        logger.info(
            "seo_analysis_complete",
            article_id=article.id,
            score=report.overall_score,
            grade=report.grade,
        )

        return report

    def optimize(self, article: Article, auto_fix: bool = False) -> tuple[Article, SEOReport]:
        """
        Analisa e opcionalmente aplica correções automáticas.

        Args:
            article: Artigo a otimizar.
            auto_fix: Se True, aplica correções automáticas possíveis.

        Returns:
            Tupla (artigo_otimizado, relatório_seo).
        """
        report = self.analyze(article)

        if auto_fix:
            article = self._apply_auto_fixes(article, report)
            # Re-analyze after fixes
            report = self.analyze(article)

        # Update article metadata
        article.metadata.seo_score = report.overall_score
        article.metadata.readability_score = calculate_readability_score(
            article.content_plain or strip_html_tags(article.content_html)
        )

        if report.overall_score >= 70:
            article.mark_as_optimized(report.overall_score)
        else:
            logger.warning(
                "seo_score_low",
                article_id=article.id,
                score=report.overall_score,
                msg="Artigo precisa de melhorias manuais",
            )

        return article, report

    # ──────────────────────────────────────────
    # Individual SEO Checks
    # ──────────────────────────────────────────

    def _check_meta_title(self, report: SEOReport, article: Article) -> None:
        """Verifica o meta title."""
        check = SEOCheck(
            name="Meta Title",
            category="on-page",
            weight=2.0,
            auto_fixable=True,
        )

        meta_title = article.meta_title or article.title
        keyword = article.metadata.keyword_primary

        if not meta_title:
            check.fail_check("Meta title ausente", "Adicione um meta title com a keyword principal")
        elif len(meta_title) > 60:
            check.warn_check(
                f"Meta title muito longo: {len(meta_title)} chars (max: 60)",
                score=60.0,
            )
            check.recommendation = "Reduza o meta title para no máximo 60 caracteres"
        elif keyword and keyword.lower() not in meta_title.lower():
            check.warn_check("Keyword ausente no meta title", score=50.0)
            check.recommendation = f"Inclua '{keyword}' no meta title"
        else:
            check.pass_check(f"Meta title OK ({len(meta_title)} chars)")

        report.checks.append(check)

    def _check_meta_description(self, report: SEOReport, article: Article) -> None:
        """Verifica a meta description."""
        check = SEOCheck(
            name="Meta Description",
            category="on-page",
            weight=2.0,
            auto_fixable=True,
        )

        desc = article.meta_description
        keyword = article.metadata.keyword_primary

        if not desc:
            check.fail_check("Meta description ausente")
            check.recommendation = "Adicione uma meta description de 150-160 caracteres"
        elif len(desc) < 120:
            check.warn_check(f"Meta description curta: {len(desc)} chars", score=60.0)
            check.recommendation = "Expanda a meta description para 150-160 caracteres"
        elif len(desc) > 160:
            check.warn_check(f"Meta description longa: {len(desc)} chars", score=70.0)
            check.recommendation = "Reduza a meta description para máximo 160 caracteres"
        elif keyword and keyword.lower() not in desc.lower():
            check.warn_check("Keyword ausente na meta description", score=60.0)
        else:
            check.pass_check(f"Meta description OK ({len(desc)} chars)")

        report.checks.append(check)

    def _check_slug(self, report: SEOReport, article: Article, keyword: str) -> None:
        """Verifica o slug."""
        check = SEOCheck(name="URL Slug", category="on-page", weight=1.5, auto_fixable=True)

        slug = article.slug
        if not slug:
            check.fail_check("Slug ausente")
        elif not re.match(r"^[a-z0-9-]+$", slug):
            check.fail_check("Slug contém caracteres inválidos")
            check.auto_fixable = True
        elif len(slug.split("-")) > 7:
            check.warn_check("Slug muito longo", score=70.0)
        elif keyword:
            from utils.text_processing import remove_accents
            kw_slug = remove_accents(keyword.lower()).replace(" ", "-")
            # Check if at least part of keyword is in slug
            kw_parts = set(kw_slug.split("-"))
            slug_parts = set(slug.split("-"))
            overlap = kw_parts & slug_parts
            if len(overlap) >= min(2, len(kw_parts)):
                check.pass_check("Slug OK com keyword")
            else:
                check.warn_check("Keyword ausente no slug", score=60.0)
        else:
            check.pass_check("Slug OK")

        report.checks.append(check)

    def _check_heading_hierarchy(self, report: SEOReport, article: Article) -> None:
        """Verifica a hierarquia de headings."""
        check = SEOCheck(
            name="Heading Hierarchy",
            category="content",
            weight=2.0,
        )

        headings = extract_headings(article.content_html)
        h2_count = sum(1 for h in headings if h["level"] == "h2")
        h1_in_content = sum(1 for h in headings if h["level"] == "h1")

        if h1_in_content > 0:
            check.warn_check(
                f"H1 encontrado no conteúdo ({h1_in_content}x) — deve estar apenas no título",
                score=60.0,
            )
        elif h2_count < 3:
            check.warn_check(f"Poucos H2: {h2_count} (recomendado: 4-8)", score=60.0)
        elif h2_count >= 4:
            check.pass_check(f"Hierarquia de headings OK: {h2_count} H2s")
        else:
            check.warn_check(f"H2s razoáveis: {h2_count}", score=80.0)

        check.details = {"h2_count": h2_count, "headings": headings[:10]}
        report.checks.append(check)

    def _check_keyword_density(self, report: SEOReport, text: str, keyword: str) -> None:
        """Verifica a densidade da keyword."""
        check = SEOCheck(
            name="Keyword Density",
            category="on-page",
            weight=2.5,
            auto_fixable=False,
        )

        if not keyword:
            check.pass_check("Sem keyword definida")
            report.checks.append(check)
            return

        density = calculate_keyword_density(text, keyword)

        if density > self.kd_stuffing:
            check.fail_check(
                f"Keyword stuffing: {density:.1%} (máx: {self.kd_stuffing:.1%})",
                recommendation="Reduza a frequência da keyword no texto",
            )
        elif density < self.kd_min:
            check.warn_check(
                f"Densidade baixa: {density:.1%} (ideal: {self.kd_min:.1%}-{self.kd_max:.1%})",
                score=50.0,
            )
            check.recommendation = "Aumente a presença natural da keyword"
        elif density > self.kd_max:
            check.warn_check(
                f"Densidade um pouco alta: {density:.1%}",
                score=70.0,
            )
        else:
            check.pass_check(f"Densidade OK: {density:.1%}")

        check.details = {"density": density, "ideal_range": f"{self.kd_min:.1%}-{self.kd_max:.1%}"}
        report.checks.append(check)

    def _check_keyword_first_100(self, report: SEOReport, text: str, keyword: str) -> None:
        """Verifica keyword nos primeiros 100 caracteres."""
        check = SEOCheck(name="Keyword nos Primeiros 100 Chars", category="on-page", weight=1.5)

        if not keyword:
            check.pass_check("Sem keyword definida")
        else:
            first_100 = extract_first_n_chars(text, 100)
            if keyword.lower() in first_100.lower():
                check.pass_check("Keyword presente nos primeiros 100 chars")
            else:
                check.warn_check("Keyword ausente nos primeiros 100 chars", score=40.0)
                check.recommendation = "Mova a keyword para o início do conteúdo"
                check.auto_fixable = True

        report.checks.append(check)

    def _check_keyword_in_headings(self, report: SEOReport, article: Article, keyword: str) -> None:
        """Verifica presença da keyword nos headings."""
        check = SEOCheck(name="Keyword nos Headings", category="on-page", weight=1.5)

        if not keyword:
            check.pass_check("Sem keyword definida")
            report.checks.append(check)
            return

        headings = extract_headings(article.content_html)
        h2_with_kw = sum(
            1 for h in headings
            if h["level"] == "h2" and keyword.lower() in h["text"].lower()
        )

        if h2_with_kw == 0:
            check.warn_check("Keyword ausente de todos os H2s", score=40.0)
            check.recommendation = f"Inclua '{keyword}' em pelo menos 1 heading H2"
        elif h2_with_kw >= 2:
            check.pass_check(f"Keyword presente em {h2_with_kw} H2s")
        else:
            check.pass_check(f"Keyword presente em {h2_with_kw} H2")

        report.checks.append(check)

    def _check_canonical_url(self, report: SEOReport, article: Article) -> None:
        """Verifica URL canônica."""
        check = SEOCheck(name="URL Canônica", category="technical", weight=1.0)
        if article.canonical_url:
            check.pass_check("URL canônica definida")
        else:
            check.warn_check("URL canônica não definida", score=70.0)
            check.auto_fixable = True
        report.checks.append(check)

    def _check_word_count(self, report: SEOReport, text: str) -> None:
        """Verifica contagem de palavras."""
        check = SEOCheck(name="Contagem de Palavras", category="content", weight=2.0)
        wc = count_words(text)
        if wc < self.min_words:
            check.fail_check(
                f"Muito curto: {wc} palavras (mín: {self.min_words})",
                recommendation=f"Adicione mais {self.min_words - wc} palavras",
            )
        elif wc > self.max_words * 1.5:
            check.warn_check(f"Muito longo: {wc} palavras", score=70.0)
        else:
            check.pass_check(f"Contagem OK: {wc} palavras")
        check.details = {"word_count": wc}
        report.checks.append(check)

    def _check_paragraph_length(self, report: SEOReport, article: Article) -> None:
        """Verifica parágrafos longos."""
        check = SEOCheck(name="Comprimento dos Parágrafos", category="content", weight=1.5)
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", article.content_html, re.DOTALL | re.IGNORECASE)
        long_p = sum(1 for p in paragraphs if count_words(strip_html_tags(p)) > 300)

        if long_p > 0:
            check.warn_check(
                f"{long_p} parágrafo(s) com 300+ palavras",
                score=60.0,
            )
            check.recommendation = "Quebre parágrafos longos em partes menores"
        else:
            check.pass_check("Parágrafos dentro do limite")

        report.checks.append(check)

    def _check_readability(self, report: SEOReport, text: str) -> None:
        """Verifica legibilidade."""
        check = SEOCheck(name="Legibilidade", category="content", weight=1.5)
        score = calculate_readability_score(text)

        if score >= 60:
            check.pass_check(f"Legibilidade boa: {score:.0f}/100")
        elif score >= 40:
            check.warn_check(f"Legibilidade razoável: {score:.0f}/100", score=60.0)
        else:
            check.warn_check(f"Legibilidade baixa: {score:.0f}/100", score=40.0)
            check.recommendation = "Simplifique frases e use vocabulário mais acessível"

        check.details = {"readability_score": score}
        report.checks.append(check)

    def _check_lists_and_structure(self, report: SEOReport, article: Article) -> None:
        """Verifica presença de listas e elementos estruturais."""
        check = SEOCheck(name="Elementos de Escaneabilidade", category="content", weight=1.5)

        html = article.content_html
        has_ul = "<ul" in html.lower()
        has_ol = "<ol" in html.lower()
        has_table = "<table" in html.lower()
        has_blockquote = "<blockquote" in html.lower()

        elements = sum([has_ul, has_ol, has_table, has_blockquote])

        if elements >= 3:
            check.pass_check(f"Boa escaneabilidade: {elements} tipos de elementos")
        elif elements >= 1:
            check.warn_check(f"Escaneabilidade razoável: {elements} tipo(s)", score=70.0)
        else:
            check.warn_check("Sem listas ou tabelas — adicione para melhorar escaneabilidade", score=40.0)

        report.checks.append(check)

    def _check_images(self, report: SEOReport, article: Article) -> None:
        """Verifica imagens e alt text."""
        check = SEOCheck(name="Imagens", category="content", weight=1.5)
        images = re.findall(r"<img[^>]*>", article.content_html, re.IGNORECASE)

        if not images and not article.cover_image:
            check.warn_check("Nenhuma imagem — adicione imagens", score=40.0)
        elif images:
            missing_alt = sum(1 for img in images if 'alt=""' in img or "alt=" not in img)
            if missing_alt > 0:
                check.warn_check(f"{missing_alt} imagem(ns) sem alt text", score=60.0)
                check.auto_fixable = True
            else:
                check.pass_check(f"{len(images)} imagem(ns) com alt text")
        else:
            check.pass_check("Imagem de capa definida")

        report.checks.append(check)

    def _check_internal_links(self, report: SEOReport, article: Article) -> None:
        """Verifica links internos."""
        check = SEOCheck(name="Links Internos", category="on-page", weight=2.0, auto_fixable=True)
        internal_count = len(article.internal_links)
        html_internal = len(re.findall(r'href=["\']/', article.content_html))
        total = internal_count + html_internal

        if total < 3:
            check.warn_check(f"Poucos links internos: {total} (mín: 3)", score=40.0)
            check.recommendation = "Adicione pelo menos 3 links internos relevantes"
        else:
            check.pass_check(f"Links internos OK: {total}")

        article.metadata.internal_links_count = total
        report.checks.append(check)

    def _check_external_links(self, report: SEOReport, article: Article) -> None:
        """Verifica links externos."""
        check = SEOCheck(name="Links Externos", category="on-page", weight=1.0)
        external_count = len(article.external_links)
        html_external = len(re.findall(r'href=["\']https?://', article.content_html))
        total = external_count + html_external

        if total == 0:
            check.warn_check("Sem links externos", score=60.0)
            check.recommendation = "Adicione 1-2 links para fontes autoritativas"
        elif total > 10:
            check.warn_check(f"Muitos links externos: {total}", score=70.0)
        else:
            check.pass_check(f"Links externos OK: {total}")

        article.metadata.external_links_count = total
        report.checks.append(check)

    def _check_article_schema(self, report: SEOReport, article: Article) -> None:
        """Verifica schema markup de artigo."""
        check = SEOCheck(name="Article Schema", category="schema", weight=1.0, auto_fixable=True)
        if article.schema_markup.article_schema:
            check.pass_check("Article schema definido")
        else:
            check.warn_check("Article schema ausente", score=50.0)
            check.recommendation = "Adicione schema markup Article (JSON-LD)"
        report.checks.append(check)

    def _check_faq_schema(self, report: SEOReport, article: Article) -> None:
        """Verifica schema markup FAQ."""
        check = SEOCheck(name="FAQ Schema", category="schema", weight=1.0, auto_fixable=True)
        if article.faq_items:
            if article.schema_markup.faq_schema:
                check.pass_check("FAQ schema definido")
            else:
                check.warn_check("FAQ presente mas schema ausente", score=50.0)
                check.auto_fixable = True
        else:
            check.warn_check("Sem seção FAQ", score=70.0)
        report.checks.append(check)

    def _check_faq_section(self, report: SEOReport, article: Article) -> None:
        """Verifica a presença e qualidade da FAQ."""
        check = SEOCheck(name="Seção FAQ", category="content", weight=1.0)
        if len(article.faq_items) >= 3:
            check.pass_check(f"FAQ com {len(article.faq_items)} itens")
        elif article.faq_items:
            check.warn_check(f"FAQ com poucos itens: {len(article.faq_items)} (ideal: 3-5)", score=60.0)
        else:
            check.warn_check("Seção FAQ ausente", score=50.0)
        report.checks.append(check)

    def _check_introduction(self, report: SEOReport, article: Article) -> None:
        """Verifica a introdução."""
        check = SEOCheck(name="Introdução", category="content", weight=1.0)
        if article.introduction:
            wc = count_words(article.introduction)
            if 100 <= wc <= 250:
                check.pass_check(f"Introdução OK: {wc} palavras")
            elif wc < 100:
                check.warn_check(f"Introdução curta: {wc} palavras", score=60.0)
            else:
                check.warn_check(f"Introdução longa: {wc} palavras", score=70.0)
        else:
            check.warn_check("Introdução ausente", score=40.0)
        report.checks.append(check)

    def _check_conclusion(self, report: SEOReport, article: Article) -> None:
        """Verifica a conclusão."""
        check = SEOCheck(name="Conclusão", category="content", weight=1.0)
        if article.conclusion:
            check.pass_check("Conclusão presente")
        else:
            check.warn_check("Conclusão ausente", score=50.0)
        report.checks.append(check)

    # ──────────────────────────────────────────
    # Auto-fix
    # ──────────────────────────────────────────

    def _apply_auto_fixes(self, article: Article, report: SEOReport) -> Article:
        """Aplica correções automáticas quando possível."""
        logger.info("applying_auto_fixes", article_id=article.id)

        # Fix meta title length
        if article.meta_title and len(article.meta_title) > 60:
            article.meta_title = article.meta_title[:57] + "..."

        # Fix meta description length
        if article.meta_description and len(article.meta_description) > 160:
            article.meta_description = article.meta_description[:157] + "..."

        # Fix slug
        if not article.slug and article.title:
            from utils.text_processing import slugify
            article.slug = slugify(article.title)

        # Generate schema markup if missing
        if not article.schema_markup.article_schema:
            from utils.html_builder import HtmlBuilder
            builder = HtmlBuilder(article)
            article.schema_markup.article_schema = builder._build_article_schema()

        if article.faq_items and not article.schema_markup.faq_schema:
            from utils.html_builder import HtmlBuilder
            builder = HtmlBuilder(article)
            article.schema_markup.faq_schema = builder._build_faq_schema()

        return article
