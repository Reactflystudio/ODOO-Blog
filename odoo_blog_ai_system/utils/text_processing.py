"""
Utilidades de processamento de texto e NLP.

Funções para slugificação, contagem de palavras, extração de entidades,
cálculo de legibilidade e manipulação de texto para SEO.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from utils.logger import get_logger

logger = get_logger("text_processing")


def slugify(text: str, max_length: int = 80) -> str:
    """
    Gera um slug SEO-friendly a partir de texto.

    Args:
        text: Texto para converter em slug.
        max_length: Comprimento máximo do slug.

    Returns:
        Slug normalizado (lowercase, hifenizado, sem stopwords).
    """
    # Normalize unicode characters
    slug = unicodedata.normalize("NFKD", text)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    slug = slug.lower()
    # Remove special characters
    slug = re.sub(r"[^\w\s-]", "", slug)
    # Replace whitespace with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove repeated hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    # Remove common Portuguese stopwords from slug
    stopwords_pt = {
        "de", "da", "do", "das", "dos", "a", "o", "as", "os",
        "em", "no", "na", "nos", "nas", "um", "uma", "uns", "umas",
        "e", "ou", "que", "para", "por", "com", "se", "como",
        "mais", "seu", "sua", "seus", "suas",
    }
    parts = slug.split("-")
    filtered = [p for p in parts if p not in stopwords_pt and len(p) > 1]

    if not filtered:
        filtered = parts  # Fallback: keep all if everything was filtered

    slug = "-".join(filtered)

    # Truncate to max_length (cut at word boundary)
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]

    return slug


def count_words(text: str) -> int:
    """
    Conta as palavras em um texto (ignorando tags HTML).

    Args:
        text: Texto (pode conter HTML).

    Returns:
        Número de palavras.
    """
    clean = strip_html_tags(text)
    words = clean.split()
    return len(words)


def strip_html_tags(html_text: str) -> str:
    """
    Remove todas as tags HTML de um texto.

    Args:
        html_text: Texto com tags HTML.

    Returns:
        Texto puro sem tags.
    """
    # Remove script and style blocks
    clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Decode HTML entities
    import html
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def calculate_keyword_density(text: str, keyword: str) -> float:
    """
    Calcula a densidade de uma keyword no texto.

    Args:
        text: Texto puro (sem HTML).
        keyword: Keyword para verificar.

    Returns:
        Densidade como decimal (e.g., 0.015 = 1.5%).
    """
    if not text or not keyword:
        return 0.0

    clean_text = strip_html_tags(text).lower()
    keyword_lower = keyword.lower().strip()

    word_count = count_words(clean_text)
    if word_count == 0:
        return 0.0

    # Count keyword occurrences (as phrase)
    keyword_occurrences = clean_text.count(keyword_lower)
    keyword_word_count = len(keyword_lower.split())

    density = (keyword_occurrences * keyword_word_count) / word_count
    return round(density, 4)


def extract_headings(html_content: str) -> list[dict[str, str]]:
    """
    Extrai headings (H1-H6) do HTML.

    Args:
        html_content: HTML do artigo.

    Returns:
        Lista de dicts com level e text de cada heading.
    """
    pattern = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
    headings: list[dict[str, str]] = []
    for match in pattern.finditer(html_content):
        level = match.group(1)
        text = strip_html_tags(match.group(2)).strip()
        headings.append({"level": f"h{level}", "text": text})
    return headings


def calculate_readability_score(text: str) -> float:
    """
    Calcula um score de legibilidade adaptado para português.

    Baseado no índice de Flesch-Kincaid adaptado para PT-BR.
    Score de 0-100 (maior = mais fácil de ler).

    Args:
        text: Texto puro sem HTML.

    Returns:
        Score de legibilidade (0-100).
    """
    clean = strip_html_tags(text) if "<" in text else text
    sentences = re.split(r"[.!?]+", clean)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return 0.0

    words = clean.split()
    if not words:
        return 0.0

    # Count syllables (simplified for Portuguese)
    total_syllables = sum(_count_syllables_pt(w) for w in words)

    num_sentences = len(sentences)
    num_words = len(words)

    # Flesch Reading Ease adapted for Portuguese
    # FRE = 248.835 - (1.015 * ASL) - (84.6 * ASW)
    asl = num_words / num_sentences  # Average Sentence Length
    asw = total_syllables / num_words  # Average Syllables per Word

    score = 248.835 - (1.015 * asl) - (84.6 * asw)
    return round(max(0.0, min(100.0, score)), 1)


def _count_syllables_pt(word: str) -> int:
    """
    Conta sílabas de uma palavra em português (simplificado).

    Args:
        word: Palavra para contar sílabas.

    Returns:
        Número estimado de sílabas.
    """
    word = word.lower().strip()
    if len(word) <= 2:
        return 1

    vowels = set("aeiouáàâãéèêíìîóòôõúùû")
    count = 0
    prev_was_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel

    return max(1, count)


def extract_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """
    Extrai as primeiras N frases de um texto.

    Args:
        text: Texto puro.
        max_sentences: Número máximo de frases.

    Returns:
        Lista de frases.
    """
    clean = strip_html_tags(text) if "<" in text else text
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    return [s.strip() for s in sentences[:max_sentences] if s.strip()]


def truncate_text(text: str, max_length: int = 160, suffix: str = "...") -> str:
    """
    Trunca texto no limite de caracteres sem cortar palavras.

    Args:
        text: Texto original.
        max_length: Comprimento máximo.
        suffix: Sufixo a adicionar se truncado.

    Returns:
        Texto truncado.
    """
    if len(text) <= max_length:
        return text

    truncated = text[: max_length - len(suffix)]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated.rstrip(".,;:!? ") + suffix


def extract_first_n_chars(html_content: str, n: int = 100) -> str:
    """
    Extrai os primeiros N caracteres de texto puro do HTML.

    Args:
        html_content: Conteúdo HTML.
        n: Número de caracteres.

    Returns:
        Primeiros N caracteres de texto puro.
    """
    clean = strip_html_tags(html_content)
    return clean[:n] if len(clean) >= n else clean


def normalize_keyword(keyword: str) -> str:
    """
    Normaliza uma keyword: lowercase, trim, remove duplicated spaces.

    Args:
        keyword: Keyword para normalizar.

    Returns:
        Keyword normalizada.
    """
    normalized = keyword.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def remove_accents(text: str) -> str:
    """
    Remove acentos de um texto.

    Args:
        text: Texto com acentos.

    Returns:
        Texto sem acentos.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def extract_named_entities_simple(text: str) -> list[str]:
    """
    Extrai entidades nomeadas de forma simplificada (baseado em regex).

    Identifica palavras capitalizadas que provavelmente são nomes próprios,
    organizações ou tecnologias.

    Args:
        text: Texto puro.

    Returns:
        Lista de possíveis entidades nomeadas.
    """
    clean = strip_html_tags(text) if "<" in text else text
    # Find sequences of capitalized words (2+ words together or known patterns)
    pattern = re.compile(r"\b([A-Z][a-záàâãéêíóôõúç]+(?:\s+[A-Z][a-záàâãéêíóôõúç]+)*)\b")
    entities = pattern.findall(clean)

    # Filter out sentence starters (heuristic: if preceded by period)
    unique_entities: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        normalized = entity.strip()
        if normalized.lower() not in seen and len(normalized) > 2:
            seen.add(normalized.lower())
            unique_entities.append(normalized)

    return unique_entities
