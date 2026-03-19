"""
Construtor de HTML Semântico para Artigos — Empurrão Digital.

Gera HTML completo, semântico e otimizado para SEO para os artigos do blog,
incluindo: meta tags OG/Twitter, Schema.org JSON-LD, CSS embutido,
hero/cover image, conteúdo estruturado, FAQ com acordeões, botões de
compartilhamento social com ícones SVG e CTAs.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from typing import Any, Optional

from models.article import Article, FAQItem, ImageInfo
from utils.logger import get_logger

logger = get_logger("html_builder")

# ──────────────────────────────────────────────
# Constantes do site
# ──────────────────────────────────────────────
SITE_NAME = "Empurrão Digital"
SITE_URL = "https://www.empurraodigital.com.br"
SITE_LOGO = f"{SITE_URL}/logo.png"
SITE_LOCALE = "pt_BR"
DEFAULT_AUTHOR = "Cristiomar Silva"
DEFAULT_AUTHOR_URL = f"{SITE_URL}/autor/cristiomar-silva"
DEFAULT_OG_IMAGE = f"{SITE_URL}/images/default-og.jpg"

# ──────────────────────────────────────────────
# SVG Icons para social share
# ──────────────────────────────────────────────
SVG_ICONS = {
    "facebook": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    "instagram": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>',
    "x": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "linkedin": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    "whatsapp": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
    "telegram": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
}

# ──────────────────────────────────────────────
# CSS embutido para o artigo
# ──────────────────────────────────────────────
ARTICLE_CSS = """
<style>
/* ─── Reset & Base ─── */
.ed-article-wrapper {
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  color: #1a1a2e;
  line-height: 1.8;
  max-width: 860px;
  margin: 0 auto;
  padding: 0 20px;
  font-size: 17px;
}
.ed-article-wrapper *, .ed-article-wrapper *::before, .ed-article-wrapper *::after {
  box-sizing: border-box;
}

/* ─── Hero / Cover ─── */
.ed-hero {
  position: relative;
  width: 100%;
  min-height: 420px;
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 40px;
  display: flex;
  align-items: flex-end;
}
.ed-hero img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ed-hero-overlay {
  position: relative;
  z-index: 2;
  width: 100%;
  padding: 40px 32px 32px;
  background: linear-gradient(0deg, rgba(0,0,0,.75) 0%, rgba(0,0,0,.35) 60%, transparent 100%);
}
.ed-hero-overlay h1 {
  color: #fff;
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.2;
  margin: 0 0 12px;
  text-shadow: 0 2px 8px rgba(0,0,0,.4);
}
.ed-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: rgba(255,255,255,.85);
  font-size: 0.85rem;
}
.ed-hero-meta span {
  display: flex;
  align-items: center;
  gap: 5px;
}

/* ─── Headings ─── */
.ed-article-wrapper h2 {
  font-size: 1.55rem;
  font-weight: 700;
  color: #16213e;
  margin: 48px 0 18px;
  padding-bottom: 10px;
  border-bottom: 3px solid #e94560;
  line-height: 1.3;
}
.ed-article-wrapper h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f3460;
  margin: 32px 0 12px;
  line-height: 1.35;
}

/* ─── Paragraphs & Text ─── */
.ed-article-wrapper p {
  margin: 0 0 18px;
  text-align: justify;
}
.ed-article-wrapper strong {
  color: #16213e;
  font-weight: 700;
}
.ed-article-wrapper blockquote {
  border-left: 4px solid #e94560;
  margin: 24px 0;
  padding: 16px 24px;
  background: #fef9f9;
  border-radius: 0 12px 12px 0;
  font-style: italic;
  color: #333;
}
.ed-article-wrapper blockquote p {
  margin: 0;
}

/* ─── Lists ─── */
.ed-article-wrapper ul, .ed-article-wrapper ol {
  margin: 16px 0 24px;
  padding-left: 28px;
}
.ed-article-wrapper li {
  margin-bottom: 8px;
}

/* ─── Tables ─── */
.ed-article-wrapper table {
  width: 100%;
  border-collapse: collapse;
  margin: 24px 0;
  font-size: 0.95rem;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,.06);
}
.ed-article-wrapper thead {
  background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
  color: #fff;
}
.ed-article-wrapper th {
  padding: 14px 16px;
  text-align: left;
  font-weight: 600;
}
.ed-article-wrapper td {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}
.ed-article-wrapper tbody tr:nth-child(even) {
  background: #f8f9fc;
}
.ed-article-wrapper tbody tr:hover {
  background: #eef1f8;
}

/* ─── Content Images ─── */
.ed-content-image {
  margin: 32px 0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,.08);
}
.ed-content-image img {
  width: 100%;
  height: auto;
  display: block;
}
.ed-content-image figcaption {
  padding: 12px 16px;
  background: #f8f9fc;
  font-size: 0.85rem;
  color: #666;
  text-align: center;
  font-style: italic;
}

/* ─── Introduction ─── */
.ed-intro {
  font-size: 1.1rem;
  color: #333;
  border-left: 4px solid #e94560;
  padding-left: 20px;
  margin-bottom: 36px;
}
.ed-intro p:last-child {
  margin-bottom: 0;
}

/* ─── Conclusion ─── */
.ed-conclusion {
  background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
  color: #fff;
  padding: 36px 32px;
  border-radius: 16px;
  margin: 48px 0 36px;
}
.ed-conclusion h2 {
  color: #fff;
  border-bottom-color: #e94560;
  margin-top: 0;
}
.ed-conclusion p {
  color: rgba(255,255,255,.9);
}

/* ─── FAQ Section ─── */
.ed-faq {
  margin: 48px 0;
}
.ed-faq > h2 {
  text-align: center;
  border-bottom: none;
  margin-bottom: 28px;
}
.ed-faq > h2::after {
  content: '';
  display: block;
  width: 60px;
  height: 3px;
  background: #e94560;
  margin: 12px auto 0;
  border-radius: 2px;
}
.faq-item {
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  margin-bottom: 12px;
  overflow: hidden;
  transition: box-shadow .2s;
}
.faq-item:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,.06);
}
.faq-item summary {
  padding: 18px 24px;
  font-weight: 600;
  font-size: 1.05rem;
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #16213e;
  background: #f8f9fc;
  transition: background .2s;
}
.faq-item summary:hover {
  background: #eef1f8;
}
.faq-item summary::after {
  content: '+';
  font-size: 1.4rem;
  font-weight: 300;
  color: #e94560;
  transition: transform .3s;
}
.faq-item[open] summary::after {
  transform: rotate(45deg);
}
.faq-item p {
  padding: 16px 24px;
  margin: 0;
  color: #444;
  line-height: 1.7;
  border-top: 1px solid #eee;
}

/* ─── Social Share ─── */
.ed-share {
  margin: 48px 0 24px;
  text-align: center;
}
.ed-share-title {
  font-size: 1rem;
  font-weight: 600;
  color: #16213e;
  margin-bottom: 16px;
}
.ed-share-buttons {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}
.ed-share-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 50px;
  color: #fff;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
  transition: transform .15s, box-shadow .15s;
  cursor: pointer;
  border: none;
}
.ed-share-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,.15);
}
.ed-share-btn svg {
  flex-shrink: 0;
}
.ed-share-btn.facebook { background: #1877f2; }
.ed-share-btn.instagram { background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); }
.ed-share-btn.x { background: #000; }
.ed-share-btn.linkedin { background: #0a66c2; }
.ed-share-btn.whatsapp { background: #25d366; }
.ed-share-btn.telegram { background: #0088cc; }

/* ─── Tags ─── */
.ed-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 24px 0;
}
.ed-tag {
  background: #eef1f8;
  color: #0f3460;
  padding: 6px 16px;
  border-radius: 50px;
  font-size: 0.8rem;
  font-weight: 600;
  transition: background .2s;
}
.ed-tag:hover {
  background: #dde4f0;
}

/* ─── CTA ─── */
.ed-cta {
  text-align: center;
  margin: 48px 0;
  padding: 40px 32px;
  background: linear-gradient(135deg, #e94560 0%, #c23152 100%);
  border-radius: 16px;
  color: #fff;
}
.ed-cta h3 {
  color: #fff;
  font-size: 1.4rem;
  margin: 0 0 12px;
}
.ed-cta p {
  color: rgba(255,255,255,.9);
  margin: 0 0 24px;
  text-align: center;
}
.ed-cta-btn {
  display: inline-block;
  padding: 14px 36px;
  background: #fff;
  color: #e94560;
  font-weight: 700;
  border-radius: 50px;
  text-decoration: none;
  font-size: 1rem;
  transition: transform .15s, box-shadow .15s;
}
.ed-cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,.2);
}

/* ─── Responsive ─── */
@media (max-width: 768px) {
  .ed-article-wrapper { font-size: 16px; padding: 0 16px; }
  .ed-hero { min-height: 300px; }
  .ed-hero-overlay h1 { font-size: 1.5rem; }
  .ed-hero-overlay { padding: 24px 20px 20px; }
  .ed-article-wrapper h2 { font-size: 1.35rem; }
  .ed-article-wrapper h3 { font-size: 1.1rem; }
  .ed-conclusion { padding: 24px 20px; }
  .ed-cta { padding: 28px 20px; }
  .ed-share-btn { padding: 8px 16px; font-size: 0.8rem; }
}
</style>
"""


class HtmlBuilder:
    """Construtor de HTML semântico completo para artigos do blog."""

    def __init__(self, article: Article) -> None:
        self.article = article
        self.author_name = article.author_name or DEFAULT_AUTHOR
        self.article_url = f"{SITE_URL}/blog/{article.slug}" if article.slug else SITE_URL
        self.cover_image_url = ""
        if article.cover_image and article.cover_image.url:
            self.cover_image_url = article.cover_image.url
        self.publish_date = (
            article.published_at or article.created_at or datetime.utcnow()
        )

    def build_full_article_html(self) -> str:
        """
        Constrói o HTML completo do artigo com:
        - Meta tags OG + Twitter Cards
        - Schema.org JSON-LD (BlogPosting + FAQPage)
        - CSS embutido
        - Hero/Cover image
        - Conteúdo estruturado
        - Imagens no conteúdo
        - FAQ com acordeões
        - Botões de compartilhamento social
        - Tags
        - CTA
        """
        parts: list[str] = []

        # 1. Meta tags (OG + Twitter)
        parts.append(self._build_meta_tags())

        # 2. Schema.org JSON-LD
        parts.append(self._build_schema_scripts())

        # 3. CSS
        parts.append(ARTICLE_CSS)

        # 4. Article wrapper start
        parts.append('<div class="ed-article-wrapper">')

        # 5. Hero / Cover Image
        parts.append(self._build_hero_section())

        # 6. Introduction
        if self.article.introduction:
            parts.append(self._build_introduction())

        # 7. Main content with images injected
        if self.article.content_html:
            parts.append(self._build_content_with_images())

        # 8. Conclusion
        if self.article.conclusion:
            parts.append(self._build_conclusion())

        # 9. FAQ Section
        if self.article.faq_items:
            parts.append(self._build_faq_section())

        # 10. CTA
        parts.append(self._build_cta())

        # 11. Tags
        if self.article.tags:
            parts.append(self._build_tags())

        # 12. Social Share
        parts.append(self._build_share_buttons())

        # 13. Wrapper end
        parts.append('</div>')

        full_html = "\n\n".join(p for p in parts if p.strip())
        return self._clean_html(full_html)

    # ──────────────────────────────────────────
    # Meta Tags (OG + Twitter)
    # ──────────────────────────────────────────

    def _build_meta_tags(self) -> str:
        """Gera meta tags Open Graph e Twitter Cards."""
        a = self.article
        og_image = self.cover_image_url or DEFAULT_OG_IMAGE
        og_image_alt = ""
        if a.cover_image and a.cover_image.alt_text:
            og_image_alt = html.escape(a.cover_image.alt_text)

        tags_meta = ""
        for tag in (a.tags or []):
            tags_meta += f'    <meta property="article:tag" content="{html.escape(tag)}">\n'

        publish_iso = self.publish_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        return f"""<!-- Open Graph -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{html.escape(self.article_url)}">
    <meta property="og:title" content="{html.escape(a.title)}">
    <meta property="og:description" content="{html.escape(a.meta_description)}">
    <meta property="og:image" content="{html.escape(og_image)}">
    <meta property="og:image:alt" content="{og_image_alt}">
    <meta property="og:site_name" content="{SITE_NAME}">
    <meta property="og:locale" content="{SITE_LOCALE}">
    <meta property="article:published_time" content="{publish_iso}">
    <meta property="article:author" content="{html.escape(self.author_name)}">
{tags_meta}
    <!-- Twitter Cards -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="{html.escape(self.article_url)}">
    <meta name="twitter:title" content="{html.escape(a.meta_title or a.title)}">
    <meta name="twitter:description" content="{html.escape(a.meta_description)}">
    <meta name="twitter:image" content="{html.escape(og_image)}">"""

    # ──────────────────────────────────────────
    # Schema.org JSON-LD
    # ──────────────────────────────────────────

    def _build_schema_scripts(self) -> str:
        """Gera scripts JSON-LD para BlogPosting e FAQPage."""
        schemas: list[str] = []

        # BlogPosting
        article_schema = self._build_article_schema()
        if article_schema:
            schemas.append(
                '<script type="application/ld+json">\n'
                + json.dumps(article_schema, indent=2, ensure_ascii=False)
                + "\n</script>"
            )

        # FAQPage
        if self.article.faq_items:
            faq_schema = self._build_faq_schema()
            if faq_schema:
                schemas.append(
                    '<script type="application/ld+json">\n'
                    + json.dumps(faq_schema, indent=2, ensure_ascii=False)
                    + "\n</script>"
                )

        return "\n".join(schemas) if schemas else ""

    def _build_article_schema(self) -> dict[str, Any]:
        """Schema BlogPosting."""
        publish_iso = self.publish_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        updated_iso = (self.article.updated_at or self.publish_date).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"
        )

        schema: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": self.article_url,
            },
            "headline": self.article.title[:110],
            "description": self.article.meta_description,
            "author": {
                "@type": "Person",
                "name": self.author_name,
                "url": DEFAULT_AUTHOR_URL,
            },
            "publisher": {
                "@type": "Organization",
                "name": SITE_NAME,
                "logo": {
                    "@type": "ImageObject",
                    "url": SITE_LOGO,
                },
            },
            "datePublished": publish_iso,
            "dateModified": updated_iso,
        }

        if self.cover_image_url:
            schema["image"] = self.cover_image_url

        if self.article.metadata.keywords_secondary:
            schema["keywords"] = ", ".join(
                [self.article.metadata.keyword_primary]
                + self.article.metadata.keywords_secondary
            )

        return schema

    def _build_faq_schema(self) -> dict[str, Any]:
        """Schema FAQPage."""
        entities = []
        for faq in self.article.faq_items:
            entities.append({
                "@type": "Question",
                "name": faq.question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.answer,
                },
            })
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": entities,
        }

    # ──────────────────────────────────────────
    # Hero / Cover
    # ──────────────────────────────────────────

    def _build_hero_section(self) -> str:
        """Hero section com imagem de capa."""
        a = self.article
        reading_time = a.metadata.reading_time_minutes or max(1, a.metadata.word_count // 200)
        date_str = self.publish_date.strftime("%d/%m/%Y")

        cover_img = ""
        if self.cover_image_url:
            alt = html.escape(
                (a.cover_image.alt_text if a.cover_image and a.cover_image.alt_text else a.title)
            )
            cover_img = f'<img src="{html.escape(self.cover_image_url)}" alt="{alt}" loading="eager">'
        else:
            # Placeholder gradient when no cover
            cover_img = '<div style="position:absolute;inset:0;background:linear-gradient(135deg,#16213e 0%,#0f3460 50%,#e94560 100%);"></div>'

        return f"""<div class="ed-hero">
    {cover_img}
    <div class="ed-hero-overlay">
        <h1>{html.escape(a.title)}</h1>
        <div class="ed-hero-meta">
            <span>✍️ {html.escape(self.author_name)}</span>
            <span>📅 {date_str}</span>
            <span>⏱️ {reading_time} min de leitura</span>
        </div>
    </div>
</div>"""

    # ──────────────────────────────────────────
    # Introduction
    # ──────────────────────────────────────────

    def _build_introduction(self) -> str:
        """Seção de introdução estilizada."""
        intro_text = self.article.introduction.strip()
        if not intro_text:
            return ""

        paragraphs = [p.strip() for p in intro_text.split("\n") if p.strip()]
        # Convert **bold** to <strong>
        html_paragraphs = []
        for p in paragraphs:
            safe = html.escape(p)
            safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
            html_paragraphs.append(f"<p>{safe}</p>")

        return f'<div class="ed-intro">\n' + "\n".join(html_paragraphs) + "\n</div>"

    # ──────────────────────────────────────────
    # Content with images
    # ──────────────────────────────────────────

    def _build_content_with_images(self) -> str:
        """Injeta imagens do conteúdo no corpo HTML."""
        content = self.article.content_html or ""

        images = list(self.article.content_images or [])
        if not images:
            return content

        # Replace [IMAGE_N] placeholders with actual figure tags
        for i, img in enumerate(images, start=1):
            placeholder = f"[IMAGE_{i}]"
            if placeholder in content:
                figure = self._build_content_figure(img, i)
                content = content.replace(placeholder, figure)

        # If no placeholders were found, inject after H2s
        if images and "[IMAGE_" not in content:
            h2_pattern = re.compile(r"</h2>", re.IGNORECASE)
            matches = list(h2_pattern.finditer(content))
            if matches:
                figures_to_inject = [
                    self._build_content_figure(img, i)
                    for i, img in enumerate(images, start=1)
                ]
                out: list[str] = []
                last = 0
                fig_idx = 0
                for m in matches:
                    out.append(content[last:m.end()])
                    if fig_idx < len(figures_to_inject):
                        out.append(figures_to_inject[fig_idx])
                        fig_idx += 1
                    last = m.end()
                out.append(content[last:])
                if fig_idx < len(figures_to_inject):
                    out.append("".join(figures_to_inject[fig_idx:]))
                content = "".join(out)

        return content

    def _build_content_figure(self, img: ImageInfo, index: int) -> str:
        """Cria um <figure> para imagem do conteúdo."""
        src = html.escape(img.url or img.local_path or "")
        alt = html.escape(img.alt_text or img.title_text or f"Imagem {index}")
        caption = html.escape(img.alt_text or img.title_text or "")

        caption_html = f"\n    <figcaption>{caption}</figcaption>" if caption else ""
        return (
            f'<figure class="ed-content-image">\n'
            f'    <img src="{src}" alt="{alt}" loading="lazy" decoding="async">'
            f'{caption_html}\n'
            f'</figure>'
        )

    # ──────────────────────────────────────────
    # Conclusion
    # ──────────────────────────────────────────

    def _build_conclusion(self) -> str:
        """Seção de conclusão estilizada."""
        text = self.article.conclusion.strip()
        if not text:
            return ""

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        html_paragraphs = []
        for p in paragraphs:
            safe = html.escape(p)
            safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
            html_paragraphs.append(f"<p>{safe}</p>")

        return (
            '<div class="ed-conclusion">\n'
            "  <h2>Conclusão</h2>\n"
            + "\n".join(f"  {p}" for p in html_paragraphs) +
            "\n</div>"
        )

    # ──────────────────────────────────────────
    # FAQ
    # ──────────────────────────────────────────

    def _build_faq_section(self) -> str:
        """Seção de FAQ com acordeões estilizados."""
        items_html = []
        for faq in self.article.faq_items:
            q = html.escape(faq.question.strip())
            a = html.escape(faq.answer.strip())
            a = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", a)
            items_html.append(
                f'<details class="faq-item">\n'
                f"  <summary>{q}</summary>\n"
                f"  <p>{a}</p>\n"
                f"</details>"
            )

        return (
            '<section class="ed-faq">\n'
            "  <h2>Perguntas Frequentes</h2>\n"
            + "\n".join(items_html) +
            "\n</section>"
        )

    # ──────────────────────────────────────────
    # CTA
    # ──────────────────────────────────────────

    def _build_cta(self) -> str:
        """Call-to-action da Empurrão Digital."""
        return f"""<div class="ed-cta">
    <h3>Precisa de Resultados Reais no Digital?</h3>
    <p>A Empurrão Digital transforma estratégia em resultado. Fale com nossos especialistas e descubra como podemos impulsionar sua presença online.</p>
    <a href="{SITE_URL}/contato" class="ed-cta-btn" target="_blank" rel="noopener">Fale Conosco</a>
</div>"""

    # ──────────────────────────────────────────
    # Tags
    # ──────────────────────────────────────────

    def _build_tags(self) -> str:
        """Seção de tags."""
        tags_html = " ".join(
            f'<span class="ed-tag">{html.escape(t)}</span>'
            for t in self.article.tags if t.strip()
        )
        return f'<div class="ed-tags">{tags_html}</div>' if tags_html else ""

    # ──────────────────────────────────────────
    # Social Share
    # ──────────────────────────────────────────

    def _build_share_buttons(self, buttons: Optional[list[str]] = None) -> str:
        """Botões de compartilhamento com ícones SVG."""
        btns = buttons or ["facebook", "instagram", "x", "linkedin", "whatsapp", "telegram"]

        onclick_map = {
            "facebook": "window.open('https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(window.location.href),'_blank','width=640,height=440');return false;",
            "instagram": "",
            "x": "window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(document.title)+'&url='+encodeURIComponent(window.location.href),'_blank','width=640,height=440');return false;",
            "linkedin": "window.open('https://www.linkedin.com/sharing/share-offsite/?url='+encodeURIComponent(window.location.href),'_blank','width=640,height=440');return false;",
            "whatsapp": "window.open('https://api.whatsapp.com/send?text='+encodeURIComponent(document.title+' - '+window.location.href),'_blank');return false;",
            "telegram": "window.open('https://t.me/share/url?url='+encodeURIComponent(window.location.href)+'&text='+encodeURIComponent(document.title),'_blank');return false;",
        }

        label_map = {
            "facebook": "Facebook",
            "instagram": "Instagram",
            "x": "X (Twitter)",
            "linkedin": "LinkedIn",
            "whatsapp": "WhatsApp",
            "telegram": "Telegram",
        }

        href_map = {
            "instagram": "https://www.instagram.com/empurraodigital/",
        }

        btn_html_parts = []
        for b in btns:
            b_lower = b.strip().lower()
            if b_lower == "twitter":
                b_lower = "x"
            icon = SVG_ICONS.get(b_lower, "")
            label = label_map.get(b_lower, b.title())
            onclick = onclick_map.get(b_lower, "")
            href = href_map.get(b_lower, "javascript:void(0)")

            onclick_attr = f' onclick="{onclick}"' if onclick else ""
            target = ' target="_blank" rel="noopener"' if b_lower == "instagram" else ""

            btn_html_parts.append(
                f'<a class="ed-share-btn {b_lower}" href="{href}"{onclick_attr}{target}>{icon} {label}</a>'
            )

        return (
            '<div class="ed-share">\n'
            '    <p class="ed-share-title">Compartilhe este conteúdo:</p>\n'
            '    <div class="ed-share-buttons">\n        '
            + "\n        ".join(btn_html_parts) +
            '\n    </div>\n'
            '</div>'
        )

    # ──────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────

    @staticmethod
    def _clean_html(html_content: str) -> str:
        """Limpa e normaliza o HTML gerado."""
        cleaned = re.sub(r"\n{3,}", "\n\n", html_content)
        cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
        return cleaned.strip()

    @staticmethod
    def build_image_tag(image: ImageInfo, lazy: bool = True) -> str:
        """Constrói uma tag <img> otimizada."""
        attrs: list[str] = [f'src="{image.url or image.local_path}"']
        if image.alt_text:
            attrs.append(f'alt="{html.escape(image.alt_text)}"')
        if image.title_text:
            attrs.append(f'title="{html.escape(image.title_text)}"')
        if image.width:
            attrs.append(f'width="{image.width}"')
        if image.height:
            attrs.append(f'height="{image.height}"')
        if lazy:
            attrs.append('loading="lazy"')
            attrs.append('decoding="async"')
        return f"<img {' '.join(attrs)} />"

    @staticmethod
    def wrap_in_figure(image_tag: str, caption: str = "", css_class: str = "ed-content-image") -> str:
        """Envolve imagem em <figure> com legenda opcional."""
        parts = [f'<figure class="{css_class}">', f"  {image_tag}"]
        if caption:
            parts.append(f"  <figcaption>{html.escape(caption)}</figcaption>")
        parts.append("</figure>")
        return "\n".join(parts)

    @staticmethod
    def build_internal_link(url: str, anchor_text: str, title: str = "") -> str:
        """Constrói um link interno com atributos SEO."""
        attrs = [f'href="{url}"']
        if title:
            attrs.append(f'title="{html.escape(title)}"')
        return f'<a {" ".join(attrs)}>{html.escape(anchor_text)}</a>'

    @staticmethod
    def build_external_link(url: str, anchor_text: str) -> str:
        """Constrói um link externo com nofollow e target _blank."""
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(anchor_text)}</a>"
        )
