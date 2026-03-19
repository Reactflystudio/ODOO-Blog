"""
Testes do módulo SEO Optimizer.

Valida análise SEO, scoring e auto-fix de artigos.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.article import Article, ArticleMetadata, FAQItem
from modules.seo_optimizer import SEOOptimizer


def _make_test_article(**overrides) -> Article:
    """Cria um artigo de teste com valores padrão sensíveis."""
    defaults = {
        "title": "Guia Completo de Marketing Digital para Iniciantes",
        "slug": "guia-completo-marketing-digital-iniciantes",
        "meta_title": "Guia de Marketing Digital para Iniciantes",
        "meta_description": "Descubra como começar com marketing digital. Este guia completo ensina estratégias práticas para iniciantes alavancarem seus resultados.",
        "content_html": (
            "<h2>O que é Marketing Digital?</h2>"
            "<p>Marketing digital é o conjunto de estratégias de marketing realizadas "
            "no ambiente online. Ele permite que empresas de todos os tamanhos alcancem "
            "seu público-alvo de forma eficiente e mensurável.</p>"
            "<h2>Principais Estratégias de Marketing Digital</h2>"
            "<p>Existem diversas estratégias de marketing digital que podem ser "
            "aplicadas. Entre as mais eficientes estão o SEO, marketing de conteúdo, "
            "e-mail marketing, redes sociais e anúncios pagos.</p>"
            "<ul><li>SEO - Otimização para motores de busca</li>"
            "<li>Content Marketing - Criação de conteúdo relevante</li>"
            "<li>Email Marketing - Comunicação direta</li></ul>"
            "<h2>Como Começar com Marketing Digital</h2>"
            "<p>Para começar com marketing digital, é fundamental definir seus "
            "objetivos, conhecer seu público-alvo e escolher os canais adequados.</p>"
            "<h2>Ferramentas Essenciais de Marketing Digital</h2>"
            "<p>Algumas ferramentas essenciais incluem Google Analytics, SEMrush, "
            "Mailchimp e Hootsuite para gerenciamento de redes sociais.</p>"
            "<ol><li>Google Analytics</li><li>SEMrush</li><li>Mailchimp</li></ol>"
        ),
        "introduction": (
            "Marketing digital é uma das habilidades mais importantes da atualidade. "
            "Neste guia completo, você vai aprender tudo que precisa para começar "
            "do zero e alcançar resultados surpreendentes em suas campanhas online."
        ),
        "conclusion": "O marketing digital é essencial para qualquer negócio moderno.",
        "content_plain": "",
        "faq_items": [
            FAQItem(question="O que é marketing digital?", answer="É o conjunto de estratégias de marketing online."),
            FAQItem(question="Quanto custa?", answer="Depende da estratégia escolhida."),
            FAQItem(question="Funciona para pequenas empresas?", answer="Sim, é acessível para todos."),
        ],
        "metadata": ArticleMetadata(
            keyword_primary="marketing digital",
            keywords_secondary=["SEO", "marketing online", "estratégias digitais"],
            word_count=250,
            language="pt-br",
        ),
    }
    defaults.update(overrides)
    return Article(**defaults)


class TestSEOAnalysis:
    """Testes de análise SEO."""

    def test_analyze_returns_report(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        assert report is not None
        assert report.overall_score >= 0

    def test_good_article_scores_well(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100, max_words=5000)
        report = optimizer.analyze(article)
        # A well-structured article should score at least decently
        assert report.overall_score >= 40

    def test_checks_are_populated(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        assert len(report.checks) > 10

    def test_meta_title_check_exists(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        check_names = [c.name for c in report.checks]
        assert "Meta Title" in check_names

    def test_keyword_density_check_exists(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        check_names = [c.name for c in report.checks]
        assert "Keyword Density" in check_names


class TestSEOOptimize:
    """Testes de otimização com auto-fix."""

    def test_optimize_returns_tuple(self):
        article = _make_test_article()
        optimizer = SEOOptimizer(min_words=100)
        result = optimizer.optimize(article, auto_fix=False)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_auto_fix_truncates_long_meta_title(self):
        article = _make_test_article(meta_title="A" * 80)
        optimizer = SEOOptimizer(min_words=100)
        fixed, _ = optimizer.optimize(article, auto_fix=True)
        assert len(fixed.meta_title) <= 60

    def test_auto_fix_truncates_long_meta_desc(self):
        article = _make_test_article(meta_description="B" * 200)
        optimizer = SEOOptimizer(min_words=100)
        fixed, _ = optimizer.optimize(article, auto_fix=True)
        assert len(fixed.meta_description) <= 160


class TestSEOEdgeCases:
    """Testes de edge cases."""

    def test_empty_content(self):
        article = _make_test_article(
            content_html="", introduction="", conclusion=""
        )
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        assert report.overall_score >= 0

    def test_no_keyword(self):
        article = _make_test_article(
            metadata=ArticleMetadata(keyword_primary="", word_count=100)
        )
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        assert report.overall_score >= 0

    def test_missing_faq(self):
        article = _make_test_article(faq_items=[])
        optimizer = SEOOptimizer(min_words=100)
        report = optimizer.analyze(article)
        faq_checks = [c for c in report.checks if "FAQ" in c.name]
        assert len(faq_checks) > 0
