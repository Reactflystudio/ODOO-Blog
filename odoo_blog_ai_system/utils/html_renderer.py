"""
HTML rendering helpers for composing article content.

Supports simple template placeholders and basic markdown-to-HTML fixes.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Iterable

from models.article import FAQItem, ImageInfo

TOKEN_RE = re.compile(r"{{\s*([A-Za-z0-9_]+)\s*}}")


def normalize_bold_markdown(text: str) -> str:
    """Convert **bold** markdown to <strong> in a string."""
    if "**" not in text:
        return text
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def text_to_paragraphs(text: str) -> str:
    """Convert plain text into HTML paragraphs."""
    if not text:
        return ""
    text = text.strip()
    if not text:
        return ""

    blocks = re.split(r"\n\s*\n", text)
    paragraphs: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        safe = html_lib.escape(block)
        safe = normalize_bold_markdown(safe)
        safe = safe.replace("\n", "<br>")
        paragraphs.append(f"<p>{safe}</p>")
    return "".join(paragraphs)


def build_faq_html(items: Iterable[FAQItem]) -> str:
    """Build FAQ HTML using <details> items."""
    items = list(items or [])
    if not items:
        return ""

    parts: list[str] = ['<section class="ed-faq"><h2>Perguntas Frequentes</h2>']
    for item in items:
        q = html_lib.escape(item.question.strip())
        a = html_lib.escape(item.answer.strip())
        a = normalize_bold_markdown(a)
        parts.append(
            f'<details class="faq-item"><summary>{q}</summary><p>{a}</p></details>'
        )
    parts.append("</section>")
    return "".join(parts)


def build_share_html(buttons: Iterable[str]) -> str:
    """Build a social share section."""
    buttons = [b.strip().lower() for b in (buttons or []) if b and b.strip()]
    if not buttons:
        return ""

    def btn(label: str, cls: str, onclick: str, href: str = "javascript:void(0)") -> str:
        return (
            f'<a class="ed-social-{cls}" href="{href}" '
            f'onclick="{onclick}" rel="noopener">{label}</a>'
        )

    parts: list[str] = [
        '<section class="ed-social-share">',
        "<p>Compartilhe este conteudo:</p>",
        '<div class="ed-social-links">',
    ]

    for b in buttons:
        if b == "facebook":
            onclick = (
                "window.open('https://www.facebook.com/sharer/sharer.php?u='"
                "+encodeURIComponent(window.location.href),'_blank','width=640,height=440');"
                " return false;"
            )
            parts.append(btn("Facebook", "facebook", onclick))
        elif b == "instagram":
            parts.append(
                '<a class="ed-social-instagram" href="https://www.instagram.com/" '
                'target="_blank" rel="noopener">Instagram</a>'
            )
        elif b in ("x", "twitter"):
            onclick = (
                "window.open('https://twitter.com/intent/tweet?text='"
                "+encodeURIComponent(document.title)+'&url='"
                "+encodeURIComponent(window.location.href),'_blank','width=640,height=440');"
                " return false;"
            )
            parts.append(btn("X (Twitter)", "x", onclick))
        elif b == "linkedin":
            onclick = (
                "window.open('https://www.linkedin.com/sharing/share-offsite/?url='"
                "+encodeURIComponent(window.location.href),'_blank','width=640,height=440');"
                " return false;"
            )
            parts.append(btn("LinkedIn", "linkedin", onclick))
        elif b == "whatsapp":
            onclick = (
                "window.open('https://api.whatsapp.com/send?text='"
                "+encodeURIComponent(document.title+' - '+window.location.href),"
                "'_blank'); return false;"
            )
            parts.append(btn("WhatsApp", "whatsapp", onclick))
        elif b == "telegram":
            onclick = (
                "window.open('https://t.me/share/url?url='"
                "+encodeURIComponent(window.location.href)+'&text='"
                "+encodeURIComponent(document.title),'_blank'); return false;"
            )
            parts.append(btn("Telegram", "telegram", onclick))

    parts.append("</div></section>")
    return "".join(parts)


def build_tags_html(tags: Iterable[str]) -> str:
    """Build tags HTML."""
    tags = [t.strip() for t in (tags or []) if t and t.strip()]
    if not tags:
        return ""
    safe_tags = [html_lib.escape(t) for t in tags]
    return '<div class="ed-tags">' + " ".join(
        f'<span class="ed-tag">{t}</span>' for t in safe_tags
    ) + "</div>"


def build_images_placeholder_html(images: Iterable[ImageInfo]) -> str:
    """Build a block of image placeholders with captions."""
    images = list(images or [])
    if not images:
        return ""

    parts: list[str] = []
    for i, img in enumerate(images, start=1):
        caption = img.alt_text or img.title_text or f"Imagem {i}"
        caption = html_lib.escape(caption)
        parts.append(
            f'<figure class="ed-inline-image ed-inline-image-auto">[IMAGE_{i}]'
            f"<figcaption>{caption}</figcaption></figure>"
        )
    return "".join(parts)


def inject_image_placeholders(html: str, images: Iterable[ImageInfo]) -> str:
    """
    Inject image placeholders into the HTML if none exist.
    Places images after H2 headings when possible, otherwise after the first paragraph.
    """
    images = list(images or [])
    if not images:
        return html
    if "[IMAGE_1]" in html:
        return html

    figures = [
        f'<figure class="ed-inline-image ed-inline-image-auto">[IMAGE_{i}]'
        f"<figcaption>{html_lib.escape(img.alt_text or img.title_text or f'Imagem {i}')}</figcaption></figure>"
        for i, img in enumerate(images, start=1)
    ]

    h2_pattern = re.compile(r"</h2>", re.IGNORECASE)
    matches = list(h2_pattern.finditer(html))
    if matches:
        out: list[str] = []
        last = 0
        img_idx = 0
        for m in matches:
            out.append(html[last:m.end()])
            if img_idx < len(figures):
                out.append(figures[img_idx])
                img_idx += 1
            last = m.end()
        out.append(html[last:])
        if img_idx < len(figures):
            out.append("".join(figures[img_idx:]))
        return "".join(out)

    p_match = re.search(r"</p>", html, flags=re.IGNORECASE)
    if p_match:
        idx = p_match.end()
        return html[:idx] + "".join(figures) + html[idx:]

    return html + "".join(figures)


def render_template(template: str, mapping: dict[str, str]) -> tuple[str, bool]:
    """
    Replace {{TOKEN}} placeholders with mapping values.
    Returns (rendered_html, used_any_token).
    """
    used = False

    def repl(match: re.Match) -> str:
        nonlocal used
        key = match.group(1).upper()
        if key in mapping:
            used = True
            return mapping[key]
        return match.group(0)

    rendered = TOKEN_RE.sub(repl, template)
    return rendered, used
