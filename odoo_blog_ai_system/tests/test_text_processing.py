"""
Testes do módulo text_processing.

Cobre funções puras que não dependem de serviços externos.
"""

import pytest
import sys
from pathlib import Path

# Garante que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.text_processing import (
    calculate_keyword_density,
    calculate_readability_score,
    count_words,
    extract_headings,
    extract_sentences,
    remove_accents,
    slugify,
    strip_html_tags,
    truncate_text,
)


class TestSlugify:
    """Testes para a função slugify."""

    def test_basic_slugify(self):
        assert slugify("Hello World") == "hello-world"

    def test_accents_removed(self):
        result = slugify("Automação de Marketing Digital")
        assert "automacao" in result
        assert "marketing" in result
        assert "digital" in result

    def test_special_characters_removed(self):
        result = slugify("What is SEO? A Guide! (2024)")
        assert "?" not in result
        assert "!" not in result
        assert "(" not in result

    def test_multiple_hyphens_collapsed(self):
        result = slugify("Hello   ---   World")
        assert "--" not in result

    def test_max_length(self):
        long_text = "a very long title that goes on and on " * 10
        result = slugify(long_text, max_length=60)
        assert len(result) <= 60

    def test_empty_string(self):
        assert slugify("") == ""


class TestCountWords:
    """Testes para contagem de palavras."""

    def test_plain_text(self):
        assert count_words("Hello world foo bar") == 4

    def test_html_tags_stripped(self):
        assert count_words("<p>Hello <strong>world</strong></p>") == 2

    def test_empty_string(self):
        assert count_words("") == 0

    def test_whitespace_only(self):
        assert count_words("   \n\t  ") == 0


class TestStripHtmlTags:
    """Testes para remoção de tags HTML."""

    def test_basic_strip(self):
        assert strip_html_tags("<p>Hello</p>") == "Hello"

    def test_nested_tags(self):
        result = strip_html_tags("<div><p>Hello <strong>world</strong></p></div>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_no_tags(self):
        assert strip_html_tags("plain text") == "plain text"


class TestKeywordDensity:
    """Testes para cálculo de densidade de keyword."""

    def test_basic_density(self):
        text = "marketing digital é importante. marketing digital funciona."
        density = calculate_keyword_density(text, "marketing digital")
        assert density > 0

    def test_zero_for_empty(self):
        assert calculate_keyword_density("", "keyword") == 0.0

    def test_zero_when_absent(self):
        assert calculate_keyword_density("hello world", "python") == 0.0

    def test_case_insensitive(self):
        text = "SEO é importante. seo funciona. Seo ajuda."
        density = calculate_keyword_density(text, "SEO")
        assert density > 0


class TestExtractHeadings:
    """Testes para extração de headings."""

    def test_extract_h2(self):
        html = "<h2>Seção 1</h2><p>texto</p><h2>Seção 2</h2>"
        headings = extract_headings(html)
        assert len(headings) == 2
        assert headings[0]["level"] == "h2"
        assert headings[0]["text"] == "Seção 1"

    def test_mixed_levels(self):
        html = "<h1>Título</h1><h2>Sub</h2><h3>Sub-sub</h3>"
        headings = extract_headings(html)
        assert len(headings) == 3

    def test_no_headings(self):
        html = "<p>Sem headings aqui</p>"
        assert extract_headings(html) == []


class TestReadabilityScore:
    """Testes para score de legibilidade."""

    def test_returns_float(self):
        text = "Esta é uma frase simples. Outra frase curta. Texto fácil de ler."
        score = calculate_readability_score(text)
        assert isinstance(score, float)

    def test_positive_score(self):
        text = "O marketing digital ajuda empresas. " * 10
        score = calculate_readability_score(text)
        assert score > 0

    def test_empty_text(self):
        score = calculate_readability_score("")
        assert score == 0.0


class TestExtractSentences:
    """Testes para extração de sentenças."""

    def test_basic_extraction(self):
        text = "Primeira frase. Segunda frase. Terceira frase."
        sentences = extract_sentences(text, max_sentences=2)
        assert len(sentences) == 2

    def test_single_sentence(self):
        text = "Apenas uma frase."
        sentences = extract_sentences(text, max_sentences=5)
        assert len(sentences) == 1


class TestRemoveAccents:
    """Testes para remoção de acentos."""

    def test_portuguese_accents(self):
        assert remove_accents("automação") == "automacao"
        assert remove_accents("início") == "inicio"
        assert remove_accents("atuação") == "atuacao"

    def test_no_accents(self):
        assert remove_accents("hello world") == "hello world"


class TestTruncateText:
    """Testes para truncamento de texto."""

    def test_short_text_unchanged(self):
        assert truncate_text("short", 100) == "short"

    def test_long_text_truncated(self):
        text = "a very long text that needs to be truncated to fit the limit"
        result = truncate_text(text, 20)
        assert len(result) <= 23  # 20 + "..."

    def test_ends_with_ellipsis(self):
        result = truncate_text("a" * 100, 10)
        assert result.endswith("...")
