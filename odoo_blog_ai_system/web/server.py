"""
Web Server — Dashboard do Sistema de Automacao de Blog SEO.

Servidor FastAPI que serve o frontend e expoe a API REST
para todas as operacoes do sistema, incluindo sincronizacao com Odoo.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import random
import re
import sys
import uuid
import xmlrpc.client
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    GENERATED_ARTICLES_DIR,
    IMAGES_DIR,
    KEYWORDS_DIR,
    ArticleType,
    ContentDepth,
    LLMProvider,
    ToneOfVoice,
    get_settings,
    reload_settings,
)
import xmlrpc.client
from utils.logger import get_logger, setup_logging
from utils.html_renderer import (
    build_faq_html,
    build_images_placeholder_html,
    build_share_html,
    build_tags_html,
    inject_image_placeholders,
    normalize_bold_markdown,
    render_template,
    text_to_paragraphs,
)
from utils.html_builder import HtmlBuilder
from utils.text_processing import (
    calculate_keyword_density,
    count_words,
    strip_html_tags,
)

setup_logging()
logger = get_logger("web_server")

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

DATA_DIR = PROJECT_ROOT / "data"
SYNC_DIR = DATA_DIR / "synced_from_odoo"
TEMPLATES_DIR = DATA_DIR / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Odoo Blog AI System",
    description="Dashboard de Automacao de Blog SEO",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ──────────────────────────────────────────────
# Odoo Helper
# ──────────────────────────────────────────────

def get_odoo_connection():
    """Returns (db, uid, password, models_proxy) for Odoo XML-RPC."""
    settings = get_settings()
    url = settings.odoo_url
    db = settings.odoo_db
    login = settings.odoo_username
    password = settings.odoo_password

    if not all([url, db, login, password]):
        raise HTTPException(status_code=400, detail="Odoo nao configurado. Preencha o .env")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, login, password, {})

    if not uid:
        raise HTTPException(status_code=401, detail="Falha na autenticacao Odoo")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return db, uid, password, models


def strip_html_basic(html_str):
    """Remove HTML tags for word counting."""
    if not html_str:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', str(html_str))
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def _template_has_token(template: str, token: str) -> bool:
    if not template:
        return False
    pattern = re.compile(r"{{\s*" + re.escape(token) + r"\s*}}", re.IGNORECASE)
    return bool(pattern.search(template))


def _load_active_template() -> str:
    """
    Loads the active template HTML from disk.
    Returns empty string if no active template is set.
    """
    try:
        active_file = TEMPLATES_DIR / "_active.json"
        if not active_file.exists():
            return ""
        active_config = json.loads(active_file.read_text(encoding="utf-8"))
        template_name = active_config.get("active_template", "")
        if not template_name:
            return ""
        template_html_file = TEMPLATES_DIR / template_name / "template.html"
        if template_html_file.exists():
            return template_html_file.read_text(encoding="utf-8")
        return ""
    except Exception as exc:
        logger.warning("load_active_template_error", error=str(exc))
        return ""


def _compose_article_html(article, template_html: str = "", share_buttons: Optional[list[str]] = None) -> str:
    """
    Compose final HTML for an article.

    Priority:
    1. If template_html is provided explicitly, use it as the structural template.
    2. If there's an active template on disk, load and use it.
    3. Otherwise, use HtmlBuilder to generate a complete professional article.

    The template HTML is used as a wrapper — tokens like {{TITLE}}, {{CONTENT}},
    {{INTRO}}, {{FAQ}}, etc. are replaced with actual article content.
    """
    share_buttons = share_buttons or []

    # Try to load active template if none explicitly provided
    effective_template = template_html.strip() if template_html else ""
    if not effective_template:
        effective_template = _load_active_template()

    # ── Template mode ──
    if effective_template:
        body_html = normalize_bold_markdown(article.content_html or "")
        intro_html = text_to_paragraphs(article.introduction)
        conclusion_html = text_to_paragraphs(article.conclusion)
        faq_html = build_faq_html(article.faq_items)
        share_html = build_share_html(share_buttons)
        tags_html = build_tags_html(article.tags)
        images_html = build_images_placeholder_html(article.content_images)

        if not _template_has_token(effective_template, "IMAGES"):
            body_html = inject_image_placeholders(body_html, article.content_images)

        full_content_html = "".join(
            [intro_html, body_html, conclusion_html, faq_html, share_html]
        )
        has_explicit_slots = any(
            _template_has_token(effective_template, token)
            for token in ("INTRO", "CONCLUSION", "FAQ", "SHARE", "IMAGES", "TAGS")
        )
        content_value = body_html if has_explicit_slots else full_content_html

        # Build cover image URL
        cover_url = ""
        cover_alt = ""
        if article.cover_image:
            cover_url = article.cover_image.url or article.cover_image.local_path or ""
            cover_alt = article.cover_image.alt_text or article.title or ""

        # Build author and date info
        author_name = article.author_name or "Equipe Blog"
        from datetime import datetime as dt
        pub_date = article.published_at or article.created_at or dt.utcnow()
        date_str = pub_date.strftime("%d/%m/%Y")
        reading_time = article.metadata.reading_time_minutes or max(1, article.metadata.word_count // 200)

        mapping = {
            "TITLE": html_lib.escape(article.title or ""),
            "SUBTITLE": html_lib.escape(article.subtitle or ""),
            "META_TITLE": html_lib.escape(article.meta_title or article.title or ""),
            "META_DESCRIPTION": html_lib.escape(article.meta_description or ""),
            "SLUG": html_lib.escape(article.slug or ""),
            "INTRO": intro_html,
            "BODY": body_html,
            "CONTENT": content_value,
            "CONCLUSION": conclusion_html,
            "FAQ": faq_html,
            "SHARE": share_html,
            "IMAGES": images_html,
            "TAGS": tags_html,
            "COVER_IMAGE_URL": html_lib.escape(cover_url),
            "COVER_IMAGE_ALT": html_lib.escape(cover_alt),
            "AUTHOR": html_lib.escape(author_name),
            "DATE": date_str,
            "READING_TIME": str(reading_time),
            "CANONICAL_URL": html_lib.escape(article.canonical_url or ""),
        }

        rendered, used = render_template(effective_template, mapping)
        if used:
            return rendered

    # ── Default mode: HtmlBuilder (professional structure) ──
    try:
        builder = HtmlBuilder(article)
        return builder.build_full_article_html()
    except Exception as exc:
        logger.error("html_builder_error", error=str(exc))
        # Fallback to simple concatenation
        body_html = normalize_bold_markdown(article.content_html or "")
        intro_html = text_to_paragraphs(article.introduction)
        conclusion_html = text_to_paragraphs(article.conclusion)
        faq_html = build_faq_html(article.faq_items)
        share_html = build_share_html(share_buttons)
        body_html = inject_image_placeholders(body_html, article.content_images)
        return "".join([intro_html, body_html, conclusion_html, faq_html, share_html])


# ──────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str
    article_type: str = "guia"
    tone: str = "professional"
    depth: str = "intermediate"
    language: str = "pt-br"
    min_words: int = 1500
    max_words: int = 2500
    provider: str = ""


class BulkGenerateRequest(BaseModel):
    topic: str
    count: int = 10
    language: str = "pt-br"
    tone: str = "professional"
    depth: str = "intermediate"
    min_words: int = 1500
    max_words: int = 2500
    concurrent: int = 5


class ClusterRequest(BaseModel):
    seed: str
    depth: int = 2
    max_keywords: int = 50


class TrendsRequest(BaseModel):
    niche: str = "tecnologia"
    region: str = "BR"
    limit: int = 20


class PublishRequest(BaseModel):
    article_id: str
    dry_run: bool = False


class EmpurraoGenerateRequest(BaseModel):
    count: int = 1
    topics: list[str] = []
    article_type: str = "guia"
    primary_keyword: str = "marketing digital politico"
    secondary_keywords: list[str] = []
    tone: str = "Profissional, Didatico, Tecnico, Inspirador"
    depth: str = "intermediate_advanced"
    min_chars: int = 3000
    max_chars: int = 30000
    audiences: list[str] = []
    google_api_key: str = ""
    image_instructions: str = ""
    min_images: int = 1
    max_images: int = 2
    image_ratio: str = "16:9"
    context: str = ""
    html_template: str = ""
    faq_min: int = 3
    faq_max: int = 7
    share_buttons: list[str] = []
    language: str = "pt-br"
    provider: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

# ──────────────────────────────────────────────
# Routes — Pages
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main dashboard."""
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────
# Routes — Odoo Sync
# ──────────────────────────────────────────────

@app.post("/api/odoo/sync")
async def sync_odoo():
    """Sincroniza artigos, tags e blogs do Odoo."""
    try:
        db, uid, password, models = get_odoo_connection()
        settings = get_settings()

        SYNC_DIR.mkdir(parents=True, exist_ok=True)

        # Sync blogs
        blog_ids = models.execute_kw(db, uid, password, 'blog.blog', 'search', [[]])
        blogs = models.execute_kw(db, uid, password, 'blog.blog', 'read', [blog_ids],
                                  {'fields': ['id', 'name', 'subtitle']}) if blog_ids else []

        # Sync tags
        tag_ids = models.execute_kw(db, uid, password, 'blog.tag', 'search', [[]])
        tags = models.execute_kw(db, uid, password, 'blog.tag', 'read', [tag_ids],
                                 {'fields': ['id', 'name']}) if tag_ids else []

        # Sync posts
        post_ids = models.execute_kw(db, uid, password, 'blog.post', 'search', [[]],
                                     {'order': 'id desc'})

        posts = []
        if post_ids:
            fields = [
                'id', 'name', 'subtitle', 'content', 'blog_id',
                'website_meta_title', 'website_meta_description',
                'website_meta_keywords', 'website_published',
                'tag_ids', 'author_id', 'create_date', 'write_date',
                'visits', 'website_url',
            ]
            posts = models.execute_kw(db, uid, password, 'blog.post', 'read',
                                      [post_ids], {'fields': fields})

        # Save posts
        posts_index = []
        for post in posts:
            content_text = strip_html_basic(post.get("content", ""))
            word_count = len(content_text.split()) if content_text else 0

            blog_id_val = post.get("blog_id")
            blog_id = blog_id_val[0] if isinstance(blog_id_val, (list, tuple)) and blog_id_val else None
            blog_name = blog_id_val[1] if isinstance(blog_id_val, (list, tuple)) and len(blog_id_val) > 1 else ""

            author_val = post.get("author_id")
            author_name = author_val[1] if isinstance(author_val, (list, tuple)) and len(author_val) > 1 else ""

            post_info = {
                "id": post["id"],
                "title": post.get("name", ""),
                "subtitle": post.get("subtitle", ""),
                "published": post.get("website_published", False),
                "meta_title": post.get("website_meta_title", "") or "",
                "meta_description": post.get("website_meta_description", "") or "",
                "meta_keywords": post.get("website_meta_keywords", "") or "",
                "blog_id": blog_id,
                "blog_name": blog_name,
                "tag_ids": post.get("tag_ids", []),
                "author": author_name,
                "visits": post.get("visits", 0),
                "url": post.get("website_url", ""),
                "created_at": str(post.get("create_date", "")),
                "updated_at": str(post.get("write_date", "")),
                "word_count": word_count,
            }
            posts_index.append(post_info)

            # Save individual post
            post_dir = SYNC_DIR / f"post_{post['id']}"
            post_dir.mkdir(exist_ok=True)
            content = post.get("content", "")
            if content:
                (post_dir / "content.html").write_text(str(content), encoding="utf-8")
            (post_dir / "metadata.json").write_text(
                json.dumps(post_info, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

        # Save index files
        (SYNC_DIR / "posts_index.json").write_text(
            json.dumps(posts_index, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (SYNC_DIR / "tags.json").write_text(
            json.dumps(tags, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (SYNC_DIR / "blogs.json").write_text(
            json.dumps(blogs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        # Save summary
        summary = {
            "synced_at": datetime.now().isoformat(),
            "odoo_url": settings.odoo_url,
            "database": db,
            "total_posts": len(posts),
            "total_tags": len(tags),
            "total_blogs": len(blogs),
            "posts_published": sum(1 for p in posts_index if p["published"]),
            "posts_draft": sum(1 for p in posts_index if not p["published"]),
        }
        (SYNC_DIR / "sync_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        return {
            "success": True,
            "total_posts": len(posts),
            "total_tags": len(tags),
            "total_blogs": len(blogs),
            "published": summary["posts_published"],
            "drafts": summary["posts_draft"],
            "synced_at": summary["synced_at"],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("sync_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/odoo/status")
async def odoo_status():
    """Retorna status da conexao Odoo e dados sincronizados."""
    summary_file = SYNC_DIR / "sync_summary.json"

    result = {
        "connected": False,
        "synced": False,
        "last_sync": None,
        "total_posts": 0,
        "published": 0,
        "drafts": 0,
        "total_tags": 0,
        "total_blogs": 0,
        "odoo_url": "",
        "database": "",
    }

    settings = get_settings()
    result["odoo_url"] = settings.odoo_url or ""
    result["connected"] = bool(settings.odoo_url and settings.odoo_username and settings.odoo_password)

    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            result["synced"] = True
            result["last_sync"] = summary.get("synced_at")
            result["total_posts"] = summary.get("total_posts", 0)
            result["published"] = summary.get("posts_published", 0)
            result["drafts"] = summary.get("posts_draft", 0)
            result["total_tags"] = summary.get("total_tags", 0)
            result["total_blogs"] = summary.get("total_blogs", 0)
            result["database"] = summary.get("database", "")
        except Exception:
            pass

    return result


@app.get("/api/odoo/posts")
async def odoo_posts(limit: int = 100, offset: int = 0, published: Optional[str] = None):
    """Lista posts sincronizados do Odoo."""
    index_file = SYNC_DIR / "posts_index.json"
    if not index_file.exists():
        return {"posts": [], "total": 0}

    posts = json.loads(index_file.read_text(encoding="utf-8"))

    # Filter
    if published == "true":
        posts = [p for p in posts if p.get("published")]
    elif published == "false":
        posts = [p for p in posts if not p.get("published")]

    total = len(posts)
    posts = posts[offset: offset + limit]

    return {"posts": posts, "total": total}


@app.get("/api/odoo/posts/{post_id}")
async def odoo_post_detail(post_id: int):
    """Retorna detalhes de um post do Odoo."""
    post_dir = SYNC_DIR / f"post_{post_id}"
    meta_file = post_dir / "metadata.json"
    html_file = post_dir / "content.html"

    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Post nao encontrado")

    data = json.loads(meta_file.read_text(encoding="utf-8"))
    if html_file.exists():
        data["content_html"] = html_file.read_text(encoding="utf-8")

    return data


@app.get("/api/odoo/tags")
async def odoo_tags():
    """Lista tags sincronizadas."""
    tags_file = SYNC_DIR / "tags.json"
    if not tags_file.exists():
        return {"tags": []}
    tags = json.loads(tags_file.read_text(encoding="utf-8"))
    return {"tags": tags, "total": len(tags)}


@app.get("/api/odoo/blogs")
async def odoo_blogs():
    """Lista blogs sincronizados."""
    blogs_file = SYNC_DIR / "blogs.json"
    if not blogs_file.exists():
        return {"blogs": []}
    blogs = json.loads(blogs_file.read_text(encoding="utf-8"))
    return {"blogs": blogs}


# ──────────────────────────────────────────────
# Routes — Status & Articles (Combined)
# ──────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Retorna status geral — combina gerados + sincronizados."""
    settings = reload_settings()

    # Generated articles stats
    gen_count = 0
    total_words_gen = 0
    total_cost = 0.0
    seo_scores = []

    if GENERATED_ARTICLES_DIR.exists():
        for art_dir in GENERATED_ARTICLES_DIR.iterdir():
            if art_dir.is_dir():
                json_file = art_dir / "article.json"
                if json_file.exists():
                    try:
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        gen_count += 1
                        meta = data.get("metadata", {})
                        total_words_gen += meta.get("word_count", 0)
                        total_cost += meta.get("generation_cost_usd", 0)
                        seo = meta.get("seo_score", 0)
                        if seo > 0:
                            seo_scores.append(seo)
                    except Exception:
                        pass

    avg_seo = sum(seo_scores) / len(seo_scores) if seo_scores else 0

    # Odoo synced stats
    odoo_posts = 0
    odoo_published = 0
    odoo_drafts = 0
    odoo_words = 0
    odoo_visits = 0
    odoo_tags = 0
    last_sync = None

    summary_file = SYNC_DIR / "sync_summary.json"
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            odoo_posts = summary.get("total_posts", 0)
            odoo_published = summary.get("posts_published", 0)
            odoo_drafts = summary.get("posts_draft", 0)
            odoo_tags = summary.get("total_tags", 0)
            last_sync = summary.get("synced_at")
        except Exception:
            pass

    index_file = SYNC_DIR / "posts_index.json"
    if index_file.exists():
        try:
            posts = json.loads(index_file.read_text(encoding="utf-8"))
            odoo_words = sum(p.get("word_count", 0) for p in posts)
            odoo_visits = sum(p.get("visits", 0) for p in posts)
        except Exception:
            pass

    return {
        "articles_generated": gen_count,
        "odoo_posts": odoo_posts,
        "odoo_published": odoo_published,
        "odoo_drafts": odoo_drafts,
        "odoo_tags": odoo_tags,
        "odoo_visits": odoo_visits,
        "total_words": total_words_gen + odoo_words,
        "total_cost_usd": round(total_cost, 4),
        "avg_seo_score": round(avg_seo, 1),
        "last_sync": last_sync,
        "default_provider": settings.default_llm_provider.value,
        "default_language": settings.default_language,
        "odoo_url": settings.odoo_url or "Nao configurado",
        "articles_per_day": settings.articles_per_day,
    }


@app.get("/api/articles")
async def list_articles(limit: int = 50, offset: int = 0):
    """Lista artigos gerados pelo sistema AI."""
    articles = []
    if not GENERATED_ARTICLES_DIR.exists():
        return {"articles": [], "total": 0}

    all_dirs = sorted(
        [d for d in GENERATED_ARTICLES_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime, reverse=True,
    )
    total = len(all_dirs)

    for art_dir in all_dirs[offset: offset + limit]:
        json_file = art_dir / "article.json"
        if json_file.exists():
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                articles.append({
                    "id": data.get("id", art_dir.name),
                    "title": data.get("title", "Sem titulo"),
                    "slug": data.get("slug", ""),
                    "status": data.get("status", "unknown"),
                    "keyword": data.get("metadata", {}).get("keyword_primary", ""),
                    "word_count": data.get("metadata", {}).get("word_count", 0),
                    "seo_score": data.get("metadata", {}).get("seo_score", 0),
                    "provider": data.get("metadata", {}).get("llm_provider", ""),
                    "cost": data.get("metadata", {}).get("generation_cost_usd", 0),
                    "created_at": data.get("created_at", ""),
                    "article_type": data.get("metadata", {}).get("article_type", ""),
                })
            except Exception:
                pass

    return {"articles": articles, "total": total}


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str):
    """Retorna detalhes de um artigo."""
    art_dir = GENERATED_ARTICLES_DIR / article_id
    json_file = art_dir / "article.json"
    html_file = art_dir / "content.html"

    if not json_file.exists():
        raise HTTPException(status_code=404, detail="Artigo nao encontrado")

    data = json.loads(json_file.read_text(encoding="utf-8"))
    if html_file.exists():
        data["content_html_full"] = html_file.read_text(encoding="utf-8")
    return data


@app.post("/api/generate")
async def generate_article(req: GenerateRequest):
    """Gera um novo artigo."""
    try:
        from modules.ai_content_generator import AIContentGenerator
        from modules.seo_optimizer import SEOOptimizer

        tone_map = {t.value: t for t in ToneOfVoice}
        depth_map = {d.value: d for d in ContentDepth}
        type_map = {t.value: t for t in ArticleType}
        prov_map = {p.value: p for p in LLMProvider}

        # Force reload settings to pick up .env changes
        fresh_settings = reload_settings()
        selected_provider = prov_map.get(req.provider) if req.provider else fresh_settings.default_llm_provider

        gen = AIContentGenerator(
            provider=selected_provider,
        )
        article = await gen.generate_article(
            keyword=req.topic,
            article_type=type_map.get(req.article_type, ArticleType.GUIDE),
            tone=tone_map.get(req.tone, ToneOfVoice.PROFESSIONAL),
            depth=depth_map.get(req.depth, ContentDepth.INTERMEDIATE),
            language=req.language,
            min_words=req.min_words,
            max_words=req.max_words,
        )
        optimizer = SEOOptimizer()
        article, report = optimizer.optimize(article, auto_fix=True)

        art_dir = GENERATED_ARTICLES_DIR / article.id
        art_dir.mkdir(parents=True, exist_ok=True)
        (art_dir / "article.json").write_text(
            json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (art_dir / "content.html").write_text(article.content_html, encoding="utf-8")

        return {
            "success": True,
            "article": {
                "id": article.id, "title": article.title, "slug": article.slug,
                "word_count": article.metadata.word_count,
                "seo_score": report.overall_score, "grade": report.grade,
                "provider": article.metadata.llm_provider,
                "cost": article.metadata.generation_cost_usd,
            },
        }
    except Exception as exc:
        logger.error("generate_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/generate/empurrao")
async def generate_empurrao(req: EmpurraoGenerateRequest):
    """Gera artigo(s) com configuracao completa Empurrao Digital."""
    try:
        import traceback
        from modules.ai_content_generator import AIContentGenerator
        from modules.seo_optimizer import SEOOptimizer

        audiences_str = ", ".join(req.audiences) if req.audiences else "Politicos, Pre-candidatos, Partidos politicos"
        secondary_kw_str = ", ".join(req.secondary_keywords) if req.secondary_keywords else ""
        share_btns = req.share_buttons if req.share_buttons else ["facebook", "instagram", "x", "linkedin", "whatsapp", "telegram"]

        # Convert chars to approximate words (avg 5 chars per word in Portuguese)
        min_words = max(req.min_chars // 5, 500)
        max_words = min(req.max_chars // 5, 6000)

        generated_articles = []

        for i in range(req.count):
            topic = req.topics[i] if i < len(req.topics) else (
                req.topics[0] if req.topics else req.primary_keyword
            )

            # Build master prompt
            master_context = f"""
CONTEXTO INSTITUCIONAL:
{req.context or 'Agencia Empurrao Digital - Marketing digital politico desde 2018, Goiania-GO, atendimento nacional.'}

REGRAS OBRIGATORIAS:
- A agencia referenciada deve ser sempre a Empurrao Digital
- Publico-alvo: {audiences_str}
- Tom de voz: {req.tone}
- Nivel de profundidade: {req.depth.replace('_', ' ')}
- Palavra-chave principal: {req.primary_keyword}
- Palavras-chave secundarias: {secondary_kw_str}
- Idioma: Portugues Brasileiro (pt-BR)
- Tamanho: entre {req.min_chars} e {req.max_chars} caracteres

ESTILO DE ESCRITA OBRIGATORIO:
- Linguagem clara, humana e natural - SEM textos roboticos
- Paragrafos curtos e escanaveis
- Uso de listas quando necessario
- Exemplos praticos do cenario politico brasileiro
- Uso natural das palavras-chave (sem keyword stuffing)
- Texto justificado
- Alternar entre texto normal e **negrito** em trechos importantes
- Tom de publicitario experiente
- Valorizar experiencia e autoridade da Empurrao Digital quando fizer sentido
- Escreva como se estivesse conversando com o leitor, de forma estrategica

ESTRUTURA OBRIGATORIA DO ARTIGO:
1. Titulo principal forte e otimizado para SEO (tag H1)
2. Meta Title (max 60 caracteres)
3. Meta Description (max 155 caracteres, compelling)
4. Slug otimizado (ex: marketing-politico-eleicoes-2026)
5. Tags do artigo (5-10 tags relevantes)
6. Introducao cativante (2-3 paragrafos)
7. Secoes com H2 (minimo 4 secoes)
8. Subtopicos com H3 quando necessario
9. Conclusao forte com call-to-action
10. FAQ interativa com acordeoes ({req.faq_min} a {req.faq_max} perguntas)
    - Cada pergunta deve usar a estrutura HTML:
    <details class="faq-item"><summary>Pergunta aqui?</summary><p>Resposta aqui.</p></details>
11. Secao de compartilhamento social com botoes clicaveis para: {', '.join(share_btns)}
    - Use icones SVG inline para cada rede social
    - Os botoes devem usar JavaScript window.open() para compartilhar a URL da pagina

APRENDIZADO MESTRE:
Reescreva o conteudo como um publicitario experiente, utilizando linguagem natural, simples, envolvente e persuasiva.
O objetivo e que o post soe humano, estrategico e facil de entender.
Os conteudos devem ter forca de comunicacao, impacto e clareza.
"""

            prov_map = {p.value: p for p in LLMProvider}
            selected_provider = prov_map.get(req.provider) if req.provider else None

            # Force reload settings to pick up .env changes
            fresh_settings = reload_settings()

            # If no provider explicitly requested, use the one from .env
            if not selected_provider:
                selected_provider = fresh_settings.default_llm_provider

            custom_keys = {}
            if req.gemini_api_key:
                custom_keys[LLMProvider.GEMINI] = req.gemini_api_key
            if req.openai_api_key:
                custom_keys[LLMProvider.OPENAI] = req.openai_api_key
            if req.anthropic_api_key:
                custom_keys[LLMProvider.ANTHROPIC] = req.anthropic_api_key

            logger.info("empurrao_provider_selection", requested=req.provider, resolved=selected_provider)

            gen = AIContentGenerator(
                provider=selected_provider,
                custom_api_keys=custom_keys,
            )

            article = await gen.generate_article(
                keyword=topic,
                article_type=ArticleType.GUIDE,
                tone=ToneOfVoice.PROFESSIONAL,
                depth=ContentDepth.INTERMEDIATE,
                language="pt-br",
                min_words=min_words,
                max_words=max_words,
                extra_context=master_context,
            )

            # Optimize SEO
            optimizer = SEOOptimizer()
            article, report = optimizer.optimize(article, auto_fix=True)

            # Basic tags from keywords (fallback when no tag generator is used)
            tags: list[str] = []
            seen_tags: set[str] = set()
            for t in [req.primary_keyword] + (req.secondary_keywords or []):
                t = t.strip()
                key = t.lower()
                if t and key not in seen_tags:
                    tags.append(t)
                    seen_tags.add(key)
            article.tags = tags[:10]

            # Generate Images
            from modules.image_generator import ImageGenerator
            from config import ImageProvider
            img_gen = ImageGenerator()
            if req.google_api_key:
                img_gen.provider = ImageProvider.GOOGLE_IMAGEN
                img_gen.api_key_override = req.google_api_key

            # Decide total image count (includes cover)
            min_images = max(0, req.min_images)
            max_images = max(min_images, req.max_images)
            total_images = 0
            if max_images > 0:
                total_images = random.randint(min_images, max_images) if max_images > min_images else max_images

            if total_images > 0:
                content_img_count = max(0, total_images - 1)
                article = await img_gen.generate_article_images(
                    article=article,
                    cover_style=req.image_instructions or "modern, professional, minimalist, brazilian political marketing",
                    content_image_count=content_img_count,
                    aspect_ratio=req.image_ratio,
                )

            # Compose final HTML (template or default)
            article.content_html = _compose_article_html(
                article,
                template_html=req.html_template or "",
                share_buttons=share_btns,
            )
            plain = strip_html_tags(article.content_html)
            article.content_plain = plain
            article.metadata.word_count = count_words(plain)
            article.metadata.reading_time_minutes = max(1, article.metadata.word_count // 200)
            article.metadata.keyword_density = calculate_keyword_density(plain, article.metadata.keyword_primary)

            # Save
            art_dir = GENERATED_ARTICLES_DIR / article.id
            art_dir.mkdir(parents=True, exist_ok=True)

            # Save config used
            config_data = {
                "empurrao_config": {
                    "topic": topic,
                    "primary_keyword": req.primary_keyword,
                    "secondary_keywords": req.secondary_keywords,
                    "audiences": req.audiences,
                    "tone": req.tone,
                    "depth": req.depth,
                    "min_chars": req.min_chars,
                    "max_chars": req.max_chars,
                    "faq_range": f"{req.faq_min}-{req.faq_max}",
                    "share_buttons": share_btns,
                    "image_config": {
                        "min": req.min_images,
                        "max": req.max_images,
                        "ratio": req.image_ratio,
                        "google_api_key": "configured" if req.google_api_key else "missing",
                        "instructions": req.image_instructions,
                    },
                    "html_template": (req.html_template[:200] + "...") if req.html_template and len(req.html_template) > 200 else req.html_template,
                    "context": req.context[:200] + "..." if len(req.context) > 200 else req.context,
                },
            }

            storage = article.to_storage_dict()
            storage.update(config_data)

            (art_dir / "article.json").write_text(
                json.dumps(storage, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            (art_dir / "content.html").write_text(article.content_html, encoding="utf-8")

            generated_articles.append({
                "id": article.id,
                "title": article.title,
                "slug": article.slug,
                "word_count": article.metadata.word_count,
                "seo_score": report.overall_score,
                "grade": report.grade,
            })

        return {
            "success": True,
            "articles_generated": len(generated_articles),
            "articles": generated_articles,
        }

    except Exception as exc:
        logger.error("empurrao_generate_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/generate/bulk")
async def generate_bulk(req: BulkGenerateRequest):
    """Geracao em massa."""
    try:
        from modules.bulk_generator import BulkGenerator
        tone_map = {t.value: t for t in ToneOfVoice}
        depth_map = {d.value: d for d in ContentDepth}
        gen = BulkGenerator(concurrent=req.concurrent)
        results = await gen.generate_bulk(
            topic=req.topic, count=req.count, language=req.language,
            tone=tone_map.get(req.tone, ToneOfVoice.PROFESSIONAL),
            depth=depth_map.get(req.depth, ContentDepth.INTERMEDIATE),
            min_words=req.min_words, max_words=req.max_words,
        )
        return {"success": True, "results": results}
    except Exception as exc:
        logger.error("bulk_generate_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/keywords/cluster")
async def generate_cluster(req: ClusterRequest):
    """Gera cluster de keywords."""
    try:
        from modules.keyword_cluster import KeywordClusterGenerator
        gen = KeywordClusterGenerator(max_keywords=req.max_keywords)
        content_map = await gen.generate_cluster(
            seed_keyword=req.seed, depth=req.depth, max_keywords=req.max_keywords)
        await gen.close()
        KEYWORDS_DIR.mkdir(parents=True, exist_ok=True)
        out = KEYWORDS_DIR / f"cluster_{req.seed.replace(' ', '_')}.json"
        out.write_text(json.dumps(content_map.to_storage_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return {
            "success": True, "total_keywords": content_map.total_keywords,
            "clusters": [
                {"intent": cl.intent.value, "keyword_count": len(cl.keywords),
                 "keywords": [{"keyword": kw.keyword, "priority": kw.priority,
                               "opportunity_score": kw.opportunity_score,
                               "article_type": kw.article_type.value} for kw in cl.keywords[:15]]}
                for cl in content_map.clusters
            ],
        }
    except Exception as exc:
        logger.error("cluster_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/trends")
async def discover_trends(req: TrendsRequest):
    """Descobre tendencias."""
    try:
        from modules.trend_scraper import TrendScraper
        scraper = TrendScraper()
        results = await scraper.discover_trends(niche=req.niche, region=req.region, limit=req.limit)
        await scraper.close()
        return {"success": True, "trends": [t.to_dict() for t in results]}
    except Exception as exc:
        logger.error("trends_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/publish")
async def publish_article(req: PublishRequest):
    """Publica artigo no Odoo."""
    try:
        from models.article import Article
        from modules.odoo_publisher import OdooPublisher
        art_file = GENERATED_ARTICLES_DIR / req.article_id / "article.json"
        if not art_file.exists():
            raise HTTPException(status_code=404, detail="Artigo nao encontrado")
        article = Article.from_storage_dict(json.loads(art_file.read_text(encoding="utf-8")))
        publisher = OdooPublisher()
        post_id = publisher.publish_article(article, dry_run=req.dry_run)
        if not req.dry_run:
            art_file.write_text(json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return {"success": True, "odoo_post_id": post_id}
    except Exception as exc:
        logger.error("publish_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/optimize/{article_id}")
async def optimize_article(article_id: str):
    """Otimiza um artigo."""
    try:
        from models.article import Article
        from modules.seo_optimizer import SEOOptimizer
        art_file = GENERATED_ARTICLES_DIR / article_id / "article.json"
        if not art_file.exists():
            raise HTTPException(status_code=404, detail="Artigo nao encontrado")
        article = Article.from_storage_dict(json.loads(art_file.read_text(encoding="utf-8")))
        optimizer = SEOOptimizer()
        article, report = optimizer.optimize(article, auto_fix=True)
        art_file.write_text(json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return {
            "success": True, "seo_score": report.overall_score, "grade": report.grade,
            "checks": [{"name": c.name, "category": c.category,
                         "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
                         "score": c.score, "message": c.message, "recommendation": c.recommendation}
                        for c in report.checks],
        }
    except Exception as exc:
        logger.error("optimize_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/backlinks/report")
async def backlinks_report():
    """Relatorio de backlinks."""
    try:
        from modules.backlink_system import BacklinkSystem
        system = BacklinkSystem()
        return system.generate_health_report()
    except Exception as exc:
        logger.error("backlinks_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: str):
    """Deleta artigo."""
    import shutil
    art_dir = GENERATED_ARTICLES_DIR / article_id
    if not art_dir.exists():
        raise HTTPException(status_code=404, detail="Artigo nao encontrado")
    shutil.rmtree(art_dir)
    return {"success": True}


@app.get("/api/config")
async def get_config():
    """Configuracao atual."""
    settings = get_settings()
    return {
        "default_provider": settings.default_llm_provider.value,
        "default_language": settings.default_language,
        "default_tone": settings.default_tone.value,
        "default_depth": settings.default_depth.value,
        "min_words": settings.min_words,
        "max_words": settings.max_words,
        "articles_per_day": settings.articles_per_day,
        "odoo_url": settings.odoo_url or "",
        "odoo_db": settings.odoo_db or "",
        "odoo_configured": bool(settings.odoo_url and settings.odoo_username),
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.google_ai_api_key),
        "image_provider": settings.image_provider.value,
    }


@app.post("/api/config/reload")
async def reload_config():
    """Recarrega configuracoes do .env."""
    try:
        settings = reload_settings()
        return {
            "success": True,
            "default_provider": settings.default_llm_provider.value,
            "gemini_configured": bool(settings.google_ai_api_key),
            "openai_configured": bool(settings.openai_api_key),
        }
    except Exception as exc:
        logger.error("config_reload_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/diag/odoo")
async def diag_odoo():
    """Diagnostico de conexao com Odoo."""
    settings = get_settings()
    try:
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(settings.odoo_db, settings.odoo_username, settings.odoo_password, {})
        if not uid:
            return {"success": False, "error": "Autenticacao falhou"}
        
        models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")
        blogs = models.execute_kw(settings.odoo_db, uid, settings.odoo_password, 'blog.blog', 'search_read', [[]], {'fields': ['id', 'name']})
        
        # Get latest posts
        posts = models.execute_kw(settings.odoo_db, uid, settings.odoo_password, 'blog.post', 'search_read', [[]], {'fields': ['id', 'name', 'blog_id'], 'limit': 5, 'order': 'id desc'})

        return {
            "success": True,
            "uid": uid,
            "blogs": blogs,
            "posts": posts,
            "current_blog_id": settings.odoo_blog_id,
            "blog_exists": any(b['id'] == settings.odoo_blog_id for b in blogs)
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}

@app.post("/api/examples/upload")
async def upload_example(file: UploadFile = File(...)):
    """Faz upload de um arquivo HTML como exemplo de estilo."""
    if not file.filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .html são permitidos.")
    from config import EXAMPLES_DIR
    
    content = await file.read()
    try:
        # Save to examples dir
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
        dest = EXAMPLES_DIR / safe_filename
        dest.write_bytes(content)
        return {"success": True, "filename": safe_filename}
    except Exception as exc:
        logger.error("upload_example_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/examples")
async def list_examples():
    """Lista exemplos de estilo disponíveis."""
    from config import EXAMPLES_DIR
    try:
        files = []
        for f in EXAMPLES_DIR.glob("*.html"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_ctime).isoformat()
            })
        return {"success": True, "examples": files}
    except Exception as exc:
        logger.error("list_examples_error", error=str(exc))
        return {"success": False, "error": str(exc)}


@app.delete("/api/examples/{filename}")
async def delete_example(filename: str):
    """Remove um exemplo de estilo."""
    from config import EXAMPLES_DIR
    try:
        target = EXAMPLES_DIR / filename
        if target.exists() and target.parent == EXAMPLES_DIR:
            target.unlink()
            return {"success": True}
        raise HTTPException(status_code=404, detail="Exemplo não encontrado")
    except Exception as exc:
        logger.error("delete_example_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Template Management — Upload/Manage HTML+Images
# ──────────────────────────────────────────────

from fastapi import Form
from typing import List


@app.post("/api/template/upload")
async def upload_template(
    html_file: UploadFile = File(...),
    images: List[UploadFile] = File(default=[]),
    name: str = Form(default="default"),
    set_active: bool = Form(default=True),
):
    """
    Faz upload de um template HTML + imagens de referência.

    O template será salvo em data/templates/<name>/
    com o HTML e todas as imagens de referência.
    Se set_active=True, este template se torna o template ativo
    para geração de artigos.
    """
    try:
        if not html_file.filename or not html_file.filename.lower().endswith(".html"):
            raise HTTPException(status_code=400, detail="O arquivo principal deve ser .html")

        # Sanitize template name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        template_dir = TEMPLATES_DIR / safe_name
        template_dir.mkdir(parents=True, exist_ok=True)
        images_dir = template_dir / "images"
        images_dir.mkdir(exist_ok=True)

        # Save HTML
        html_content = await html_file.read()
        html_path = template_dir / "template.html"
        html_path.write_bytes(html_content)

        # Save images
        saved_images = []
        for img_file in images:
            if img_file.filename:
                safe_img_name = re.sub(r'[^a-zA-Z0-9._-]', '_', img_file.filename)
                img_data = await img_file.read()
                img_path = images_dir / safe_img_name
                img_path.write_bytes(img_data)
                saved_images.append(safe_img_name)

        # Save metadata
        metadata = {
            "name": safe_name,
            "html_file": "template.html",
            "images": saved_images,
            "created_at": datetime.utcnow().isoformat(),
            "active": set_active,
        }
        (template_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Set as active template
        if set_active:
            active_config = {"active_template": safe_name}
            (TEMPLATES_DIR / "_active.json").write_text(
                json.dumps(active_config), encoding="utf-8"
            )

        # Also save to examples dir for the LLM context
        from config import EXAMPLES_DIR
        EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        example_dest = EXAMPLES_DIR / f"template_{safe_name}.html"
        example_dest.write_bytes(html_content)

        logger.info("template_uploaded", name=safe_name, images=len(saved_images), active=set_active)

        return {
            "success": True,
            "template_name": safe_name,
            "html_size": len(html_content),
            "images_count": len(saved_images),
            "images": saved_images,
            "is_active": set_active,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("template_upload_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/template/active")
async def get_active_template():
    """Retorna informações sobre o template ativo."""
    try:
        active_file = TEMPLATES_DIR / "_active.json"
        if not active_file.exists():
            return {"success": True, "active_template": None, "message": "Nenhum template ativo. O sistema usa o template padrão."}

        active_config = json.loads(active_file.read_text(encoding="utf-8"))
        template_name = active_config.get("active_template", "")
        template_dir = TEMPLATES_DIR / template_name

        if not template_dir.exists():
            return {"success": True, "active_template": None, "message": "Template ativo não encontrado."}

        metadata_file = template_dir / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        html_file = template_dir / "template.html"
        html_preview = ""
        if html_file.exists():
            full_html = html_file.read_text(encoding="utf-8")
            html_preview = full_html[:500] + ("..." if len(full_html) > 500 else "")

        return {
            "success": True,
            "active_template": template_name,
            "metadata": metadata,
            "html_preview": html_preview,
        }

    except Exception as exc:
        logger.error("get_active_template_error", error=str(exc))
        return {"success": False, "error": str(exc)}


@app.get("/api/templates")
async def list_templates():
    """Lista todos os templates disponíveis."""
    try:
        templates = []
        active_name = ""
        active_file = TEMPLATES_DIR / "_active.json"
        if active_file.exists():
            active_name = json.loads(active_file.read_text(encoding="utf-8")).get("active_template", "")

        for d in TEMPLATES_DIR.iterdir():
            if d.is_dir():
                meta_file = d / "metadata.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    meta["is_active"] = (d.name == active_name)
                    templates.append(meta)

        return {"success": True, "templates": templates}

    except Exception as exc:
        logger.error("list_templates_error", error=str(exc))
        return {"success": False, "error": str(exc)}


@app.post("/api/template/activate/{template_name}")
async def activate_template(template_name: str):
    """Define um template como ativo."""
    try:
        template_dir = TEMPLATES_DIR / template_name
        if not template_dir.exists():
            raise HTTPException(status_code=404, detail="Template não encontrado")

        active_config = {"active_template": template_name}
        (TEMPLATES_DIR / "_active.json").write_text(
            json.dumps(active_config), encoding="utf-8"
        )
        return {"success": True, "active_template": template_name}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("activate_template_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/template/{template_name}")
async def delete_template(template_name: str):
    """Remove um template."""
    import shutil
    try:
        template_dir = TEMPLATES_DIR / template_name
        if not template_dir.exists():
            raise HTTPException(status_code=404, detail="Template não encontrado")

        shutil.rmtree(template_dir)

        # If it was the active template, clear active
        active_file = TEMPLATES_DIR / "_active.json"
        if active_file.exists():
            active_config = json.loads(active_file.read_text(encoding="utf-8"))
            if active_config.get("active_template") == template_name:
                active_file.unlink()

        return {"success": True}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_template_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("\n[*] Odoo Blog AI System - Dashboard")
    print("    http://localhost:8000\n")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
