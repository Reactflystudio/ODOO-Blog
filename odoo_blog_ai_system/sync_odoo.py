# -*- coding: utf-8 -*-
"""
Script de Sincronizacao com Odoo.

Conecta ao Odoo, descobre o banco de dados, autentica,
e sincroniza todos os artigos do blog existentes.
"""

import json
import sys
import xmlrpc.client
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Directories
DATA_DIR = PROJECT_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "generated_articles"
SYNC_DIR = DATA_DIR / "synced_from_odoo"
SYNC_DIR.mkdir(parents=True, exist_ok=True)
ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

# Odoo credentials
ODOO_URL = "https://www.empurraodigital.com.br"
ODOO_LOGIN = "empurraodigital@gmail.com"
ODOO_API_KEY = "abb87ff5fce3ad096f541f544d69520f3bdfe6e6"


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def discover_database():
    """Tenta descobrir o nome do banco de dados."""
    step("1. Descobrindo banco de dados...")

    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common",
        allow_none=True,
    )

    # Get version info
    try:
        version = common.version()
        print(f"  Odoo version: {version.get('server_version', 'unknown')}")
        print(f"  Protocol: {version.get('protocol_version', 'unknown')}")
    except Exception as e:
        print(f"  [WARN] version() falhou: {e}")

    # Try db list
    db_proxy = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/db",
        allow_none=True,
    )

    db_list = []
    try:
        db_list = db_proxy.list()
        print(f"  Bancos disponiveis: {db_list}")
    except Exception as e:
        print(f"  [INFO] db.list() bloqueado (normal em producao): {e}")

    # Common database names to try
    candidates = db_list if db_list else [
        "empurrao-digital-2025",
        "empurraodigital",
        "empurrao_digital",
        "empurraodigital.com.br",
        "www.empurraodigital.com.br",
        "empurrao",
        "odoo",
    ]

    return candidates


def try_authenticate(db_name):
    """Tenta autenticar com um banco de dados especifico."""
    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common",
        allow_none=True,
    )

    try:
        uid = common.authenticate(db_name, ODOO_LOGIN, ODOO_API_KEY, {})
        if uid:
            print(f"  [OK] Autenticado! DB='{db_name}', UID={uid}")
            return uid
        else:
            print(f"  [FAIL] DB='{db_name}' - autenticacao retornou False/None")
    except xmlrpc.client.Fault as e:
        print(f"  [FAIL] DB='{db_name}' - {e.faultString[:100]}")
    except Exception as e:
        print(f"  [FAIL] DB='{db_name}' - {str(e)[:100]}")

    return None


def authenticate():
    """Autentica no Odoo, testando varios nomes de banco."""
    step("2. Autenticando no Odoo...")

    candidates = discover_database()

    for db_name in candidates:
        print(f"\n  Tentando banco: '{db_name}'...")
        uid = try_authenticate(db_name)
        if uid:
            return db_name, uid

    # Try with password directly instead of API key
    print("\n  Tentando com senha direta...")
    password = "Empurrao@2026@@"
    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common",
        allow_none=True,
    )
    for db_name in candidates[:5]:
        try:
            uid = common.authenticate(db_name, ODOO_LOGIN, password, {})
            if uid:
                print(f"  [OK] Autenticado com senha! DB='{db_name}', UID={uid}")
                return db_name, uid
        except Exception:
            pass

    return None, None


def sync_blog_posts(db_name, uid):
    """Sincroniza todos os posts do blog."""
    step("3. Sincronizando artigos do blog...")

    models = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object",
        allow_none=True,
    )

    # Try with API key first, then password
    credentials = [ODOO_API_KEY, "Empurrao@2026@@"]

    for password in credentials:
        try:
            # Count total posts
            total = models.execute_kw(
                db_name, uid, password,
                'blog.post', 'search_count',
                [[]],
            )
            print(f"  Total de posts no blog: {total}")

            # Get all posts
            post_ids = models.execute_kw(
                db_name, uid, password,
                'blog.post', 'search',
                [[]],
                {'order': 'id desc'},
            )

            if not post_ids:
                print("  Nenhum post encontrado.")
                return password, []

            # Read post details
            fields = [
                'id', 'name', 'subtitle', 'content', 'blog_id',
                'website_meta_title', 'website_meta_description',
                'website_meta_keywords', 'website_published',
                'tag_ids', 'author_id', 'create_date', 'write_date',
                'visits', 'website_url',
            ]

            posts = models.execute_kw(
                db_name, uid, password,
                'blog.post', 'read',
                [post_ids],
                {'fields': fields},
            )

            print(f"  {len(posts)} posts carregados com sucesso!")
            return password, posts

        except xmlrpc.client.Fault as e:
            if "access" in str(e.faultString).lower():
                print(f"  [RETRY] Credencial falhou, tentando proxima...")
                continue
            raise
        except Exception as e:
            print(f"  [RETRY] Erro: {str(e)[:80]}")
            continue

    return None, []


def sync_blog_tags(db_name, uid, password):
    """Sincroniza tags do blog."""
    step("4. Sincronizando tags...")

    models = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object",
        allow_none=True,
    )

    try:
        tag_ids = models.execute_kw(
            db_name, uid, password,
            'blog.tag', 'search',
            [[]],
        )

        if not tag_ids:
            print("  Nenhuma tag encontrada.")
            return []

        tags = models.execute_kw(
            db_name, uid, password,
            'blog.tag', 'read',
            [tag_ids],
            {'fields': ['id', 'name']},
        )

        print(f"  {len(tags)} tags encontradas:")
        for tag in tags:
            print(f"    - [{tag['id']}] {tag['name']}")

        return tags

    except Exception as e:
        print(f"  Erro ao sincronizar tags: {e}")
        return []


def sync_blogs(db_name, uid, password):
    """Lista os blogs disponiveis."""
    step("5. Listando blogs...")

    models = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object",
        allow_none=True,
    )

    try:
        blog_ids = models.execute_kw(
            db_name, uid, password,
            'blog.blog', 'search',
            [[]],
        )

        if not blog_ids:
            print("  Nenhum blog encontrado.")
            return []

        blogs = models.execute_kw(
            db_name, uid, password,
            'blog.blog', 'read',
            [blog_ids],
            {'fields': ['id', 'name', 'subtitle']},
        )

        print(f"  {len(blogs)} blog(s) encontrado(s):")
        for blog in blogs:
            print(f"    - [{blog['id']}] {blog['name']} | {blog.get('subtitle', '')}")

        return blogs

    except Exception as e:
        print(f"  Erro ao listar blogs: {e}")
        return []


def save_synced_data(posts, tags, blogs, db_name):
    """Salva os dados sincronizados em disco."""
    step("6. Salvando dados sincronizados...")

    # Save summary
    summary = {
        "synced_at": datetime.now().isoformat(),
        "odoo_url": ODOO_URL,
        "database": db_name,
        "total_posts": len(posts),
        "total_tags": len(tags),
        "total_blogs": len(blogs),
        "posts_published": sum(1 for p in posts if p.get("website_published")),
        "posts_draft": sum(1 for p in posts if not p.get("website_published")),
    }

    summary_path = SYNC_DIR / "sync_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"  Resumo salvo em: {summary_path}")

    # Save posts index
    posts_index = []
    for post in posts:
        post_info = {
            "id": post["id"],
            "title": post.get("name", ""),
            "subtitle": post.get("subtitle", ""),
            "published": post.get("website_published", False),
            "meta_title": post.get("website_meta_title", ""),
            "meta_description": post.get("website_meta_description", ""),
            "meta_keywords": post.get("website_meta_keywords", ""),
            "blog_id": post.get("blog_id", [None, ""])[0] if isinstance(post.get("blog_id"), (list, tuple)) else post.get("blog_id"),
            "blog_name": post.get("blog_id", ["", ""])[1] if isinstance(post.get("blog_id"), (list, tuple)) and len(post.get("blog_id", [])) > 1 else "",
            "tag_ids": post.get("tag_ids", []),
            "author": post.get("author_id", [None, ""])[1] if isinstance(post.get("author_id"), (list, tuple)) and len(post.get("author_id", [])) > 1 else "",
            "visits": post.get("visits", 0),
            "url": post.get("website_url", ""),
            "created_at": post.get("create_date", ""),
            "updated_at": post.get("write_date", ""),
            "word_count": len(str(post.get("content", "")).split()) if post.get("content") else 0,
        }
        posts_index.append(post_info)

        # Save individual post HTML
        post_dir = SYNC_DIR / f"post_{post['id']}"
        post_dir.mkdir(exist_ok=True)

        # Save content HTML
        content = post.get("content", "")
        if content:
            (post_dir / "content.html").write_text(
                str(content),
                encoding="utf-8",
            )

        # Save post metadata
        (post_dir / "metadata.json").write_text(
            json.dumps(post_info, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    # Save posts index
    index_path = SYNC_DIR / "posts_index.json"
    index_path.write_text(
        json.dumps(posts_index, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"  Indice de posts salvo: {index_path}")

    # Save tags
    tags_path = SYNC_DIR / "tags.json"
    tags_path.write_text(
        json.dumps(tags, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Save blogs
    blogs_path = SYNC_DIR / "blogs.json"
    blogs_path.write_text(
        json.dumps(blogs, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"\n  Dados salvos em: {SYNC_DIR}")
    return posts_index


def print_report(posts_index, tags, blogs):
    """Imprime relatorio final."""
    step("RELATORIO FINAL")

    published = [p for p in posts_index if p["published"]]
    draft = [p for p in posts_index if not p["published"]]

    print(f"  Blogs:      {len(blogs)}")
    print(f"  Posts:      {len(posts_index)}")
    print(f"  Publicados: {len(published)}")
    print(f"  Rascunhos:  {len(draft)}")
    print(f"  Tags:       {len(tags)}")

    total_words = sum(p.get("word_count", 0) for p in posts_index)
    total_visits = sum(p.get("visits", 0) for p in posts_index)
    print(f"  Palavras:   {total_words:,}")
    print(f"  Visitas:    {total_visits:,}")

    if posts_index:
        print(f"\n  Ultimos 10 posts:")
        for p in posts_index[:10]:
            status = "[PUB]" if p["published"] else "[DRF]"
            visits = p.get("visits", 0)
            print(f"    {status} [{p['id']}] {p['title'][:60]}  ({visits} visitas)")


def main():
    print("\n" + "=" * 60)
    print("  ODOO BLOG AI SYSTEM - Sincronizacao")
    print(f"  URL: {ODOO_URL}")
    print(f"  Login: {ODOO_LOGIN}")
    print("=" * 60)

    # Authenticate
    db_name, uid = authenticate()

    if not uid:
        print("\n  [ERRO] Nao foi possivel autenticar no Odoo!")
        print("  Verifique suas credenciais e URL.")
        sys.exit(1)

    # Sync posts
    password, posts = sync_blog_posts(db_name, uid)

    if password is None:
        print("\n  [ERRO] Nao foi possivel acessar os dados!")
        sys.exit(1)

    # Sync tags
    tags = sync_blog_tags(db_name, uid, password)

    # Sync blogs
    blogs = sync_blogs(db_name, uid, password)

    # Save data
    posts_index = save_synced_data(posts, tags, blogs, db_name)

    # Report
    print_report(posts_index, tags, blogs)

    # Update .env with correct database
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        content = content.replace("ODOO_DB=empurraodigital", f"ODOO_DB={db_name}")
        if password != ODOO_API_KEY:
            content = content.replace(
                f"ODOO_PASSWORD={ODOO_API_KEY}",
                f"ODOO_PASSWORD={password}",
            )
        env_path.write_text(content, encoding="utf-8")
        print(f"\n  .env atualizado com DB='{db_name}'")

    print(f"\n{'='*60}")
    print("  Sincronizacao concluida com sucesso!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
