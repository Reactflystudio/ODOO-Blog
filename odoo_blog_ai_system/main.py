"""
CLI Principal -- Sistema de Automacao de Blog SEO + Odoo.

Interface de linha de comando usando Typer para todas as operações:
geração, pesquisa, publicação, otimização e relatórios.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    ArticleType,
    ContentDepth,
    LLMProvider,
    ToneOfVoice,
    get_settings,
)
from utils.logger import setup_logging

app = typer.Typer(
    name="odoo-blog-ai",
    help="Sistema de Automação de Blog SEO + Odoo",
    add_completion=False,
)
console = Console()


def _run_async(coro):
    """Executa uma coroutine no event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ──────────────────────────────────────────────
# GENERATE COMMANDS
# ──────────────────────────────────────────────

@app.command()
def generate(
    topic: str = typer.Argument(..., help="Tópico/keyword principal do artigo"),
    tone: str = typer.Option("professional", help="Tom de voz (formal/informal/technical/professional)"),
    depth: str = typer.Option("intermediate", help="Profundidade (beginner/intermediate/advanced)"),
    language: str = typer.Option("pt-br", "--lang", help="Idioma"),
    article_type: str = typer.Option("guia", "--type", help="Tipo (guia/how-to/listicle/comparativo)"),
    min_words: int = typer.Option(1500, help="Mínimo de palavras"),
    max_words: int = typer.Option(2500, help="Máximo de palavras"),
    provider: str = typer.Option("", help="Provider LLM (openai/gemini)"),
) -> None:
    """Gera um artigo unico otimizado para SEO."""
    setup_logging()

    console.print(Panel(
        f"[bold cyan]Gerando artigo sobre:[/bold cyan] {topic}",
        title="Content Generator",
    ))

    async def _generate():
        from modules.ai_content_generator import AIContentGenerator
        from modules.seo_optimizer import SEOOptimizer

        tone_map = {t.value: t for t in ToneOfVoice}
        depth_map = {d.value: d for d in ContentDepth}
        type_map = {t.value: t for t in ArticleType}
        prov_map = {p.value: p for p in LLMProvider}

        gen = AIContentGenerator(
            provider=prov_map.get(provider) if provider else None,
        )

        article = await gen.generate_article(
            keyword=topic,
            article_type=type_map.get(article_type, ArticleType.GUIDE),
            tone=tone_map.get(tone, ToneOfVoice.PROFESSIONAL),
            depth=depth_map.get(depth, ContentDepth.INTERMEDIATE),
            language=language,
            min_words=min_words,
            max_words=max_words,
        )

        # Optimize
        optimizer = SEOOptimizer()
        article, report = optimizer.optimize(article, auto_fix=True)

        # Save
        from config import GENERATED_ARTICLES_DIR
        art_dir = GENERATED_ARTICLES_DIR / article.id
        art_dir.mkdir(parents=True, exist_ok=True)
        (art_dir / "article.json").write_text(
            json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (art_dir / "content.html").write_text(article.content_html, encoding="utf-8")

        # Display results
        table = Table(title="Artigo Gerado")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor", style="green")
        table.add_row("Título", article.title)
        table.add_row("Slug", article.slug)
        table.add_row("Palavras", str(article.metadata.word_count))
        table.add_row("SEO Score", f"{report.overall_score}/100 ({report.grade})")
        table.add_row("Provider", article.metadata.llm_provider)
        table.add_row("Custo", f"${article.metadata.generation_cost_usd:.4f}")
        table.add_row("ID", article.id)
        table.add_row("Arquivo", str(art_dir))
        console.print(table)
        console.print(f"\n{report.to_summary_string()}")

    _run_async(_generate())


@app.command()
def generate_bulk(
    topic: str = typer.Argument(..., help="Tópico geral"),
    count: int = typer.Option(10, help="Número de artigos"),
    concurrent: int = typer.Option(5, help="Chamadas LLM simultâneas"),
    language: str = typer.Option("pt-br", "--lang", help="Idioma"),
    tone: str = typer.Option("professional", help="Tom de voz"),
    depth: str = typer.Option("intermediate", help="Profundidade"),
    min_words: int = typer.Option(1500, "--min-words", help="Mínimo de palavras"),
    max_words: int = typer.Option(2500, "--max-words", help="Máximo de palavras"),
    provider: str = typer.Option("", help="Provider LLM"),
    resume: str = typer.Option("", help="ID do job para retomar"),
) -> None:
    """📦 Gera múltiplos artigos em batch."""
    setup_logging()

    console.print(Panel(
        f"[bold cyan]Geração em massa:[/bold cyan] {count} artigos sobre '{topic}'",
        title="Bulk Generator",
    ))

    async def _bulk():
        from modules.bulk_generator import BulkGenerator

        tone_map = {t.value: t for t in ToneOfVoice}
        depth_map = {d.value: d for d in ContentDepth}
        prov_map = {p.value: p for p in LLMProvider}

        gen = BulkGenerator(
            provider=prov_map.get(provider) if provider else None,
            concurrent=concurrent,
        )

        results = await gen.generate_bulk(
            topic=topic,
            count=count,
            language=language,
            tone=tone_map.get(tone, ToneOfVoice.PROFESSIONAL),
            depth=depth_map.get(depth, ContentDepth.INTERMEDIATE),
            min_words=min_words,
            max_words=max_words,
            resume_job_id=resume if resume else None,
        )

        # Display summary
        console.print(Panel(
            f"[green]✅ Completos: {results['completed']}[/green] | "
            f"[red]❌ Falhas: {results['failed']}[/red] | "
            f"Tempo: {results.get('elapsed_seconds', 0):.0f}s",
            title="Resultado",
        ))

        if results.get("articles"):
            table = Table(title="Artigos Gerados")
            table.add_column("#", style="dim")
            table.add_column("Título", style="cyan")
            table.add_column("Palavras", justify="right")
            table.add_column("SEO", justify="right")
            for i, art in enumerate(results["articles"][:20], 1):
                table.add_row(
                    str(i),
                    art["title"][:60],
                    str(art["word_count"]),
                    f"{art['seo_score']:.0f}",
                )
            console.print(table)

    _run_async(_bulk())


# ──────────────────────────────────────────────
# RESEARCH COMMANDS
# ──────────────────────────────────────────────

@app.command()
def trends(
    niche: str = typer.Option("tecnologia", help="Nicho/indústria"),
    region: str = typer.Option("BR", help="Região"),
    limit: int = typer.Option(20, help="Máximo de resultados"),
) -> None:
    """Descobre topicos em alta de multiplas fontes."""
    setup_logging()

    console.print(Panel(f"[bold]Buscando tendencias:[/bold] {niche} ({region})", title="Trend Scraper"))

    async def _trends():
        from modules.trend_scraper import TrendScraper

        scraper = TrendScraper()
        results = await scraper.discover_trends(niche=niche, region=region, limit=limit)
        await scraper.close()

        table = Table(title=f"Tendências - {niche}")
        table.add_column("#", style="dim")
        table.add_column("Tópico", style="cyan")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Fonte", style="yellow")
        table.add_column("Tipo", style="magenta")
        table.add_column("Ângulo", style="blue")

        for i, trend in enumerate(results, 1):
            table.add_row(
                str(i),
                trend.topic[:60],
                f"{trend.score:.0f}",
                trend.source,
                trend.classification,
                trend.suggested_angle,
            )

        console.print(table)

    _run_async(_trends())


@app.command()
def cluster(
    seed: str = typer.Argument(..., help="Keyword semente"),
    depth_level: int = typer.Option(2, "--depth", help="Profundidade de expansão (1-3)"),
    max_keywords: int = typer.Option(50, "--max-keywords", help="Máximo de keywords"),
) -> None:
    """🌐 Gera cluster de keywords a partir de uma seed."""
    setup_logging()

    console.print(Panel(f"[bold]Cluster de keywords:[/bold] {seed}", title="Keyword Cluster"))

    async def _cluster():
        from modules.keyword_cluster import KeywordClusterGenerator

        gen = KeywordClusterGenerator(max_keywords=max_keywords)
        content_map = await gen.generate_cluster(
            seed_keyword=seed,
            depth=depth_level,
            max_keywords=max_keywords,
        )
        await gen.close()

        # Display clusters
        for cl in content_map.clusters:
            table = Table(title=f"Cluster: {cl.intent.value}")
            table.add_column("Keyword", style="cyan")
            table.add_column("Prioridade", style="green")
            table.add_column("Tipo", style="yellow")
            table.add_column("Score", justify="right")

            for kw in cl.keywords[:15]:
                table.add_row(
                    kw.keyword[:60],
                    kw.priority,
                    kw.article_type.value,
                    f"{kw.opportunity_score:.0f}",
                )
            console.print(table)

        console.print(f"\n📊 Total: {content_map.total_keywords} keywords em {len(content_map.clusters)} clusters")

        # Save
        from config import KEYWORDS_DIR
        output = KEYWORDS_DIR / f"cluster_{seed.replace(' ', '_')}.json"
        output.write_text(
            json.dumps(content_map.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        console.print(f"💾 Salvo em: {output}")

    _run_async(_cluster())


# ──────────────────────────────────────────────
# PUBLISH COMMANDS
# ──────────────────────────────────────────────

@app.command()
def publish(
    article_id: str = typer.Option("", help="ID do artigo para publicar"),
    all_pending: bool = typer.Option(False, "--all-pending", help="Publicar todos os pendentes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simular sem efetuar"),
) -> None:
    """📤 Publica artigos no Odoo."""
    setup_logging()

    from modules.odoo_publisher import OdooPublisher
    from config import GENERATED_ARTICLES_DIR

    publisher = OdooPublisher()

    if not publisher.check_connectivity():
        console.print("[red]❌ Não foi possível conectar ao Odoo[/red]")
        raise typer.Exit(1)

    console.print("[green]✅ Conectado ao Odoo[/green]")

    if article_id:
        art_file = GENERATED_ARTICLES_DIR / article_id / "article.json"
        if not art_file.exists():
            console.print(f"[red]Artigo não encontrado: {article_id}[/red]")
            raise typer.Exit(1)

        article = Article.from_storage_dict(
            json.loads(art_file.read_text(encoding="utf-8"))
        )
        post_id = publisher.publish_article(article, dry_run=dry_run)
        console.print(f"[green]✅ Publicado! Odoo ID: {post_id}[/green]")

    elif all_pending:
        articles = []
        for art_dir in GENERATED_ARTICLES_DIR.iterdir():
            json_file = art_dir / "article.json"
            if json_file.exists():
                art = Article.from_storage_dict(
                    json.loads(json_file.read_text(encoding="utf-8"))
                )
                if art.status in (ArticleStatus.READY, ArticleStatus.OPTIMIZED, ArticleStatus.GENERATED):
                    articles.append(art)

        console.print(f"Items: {len(articles)} artigos pendentes para publicacao")
        results = publisher.batch_publish(articles, dry_run=dry_run)

        console.print(Panel(
            f"[green]✅ Publicados: {results['published']}[/green] | "
            f"[red]❌ Falhas: {results['failed']}[/red] | "
            f"⏭️ Ignorados: {results['skipped']}",
            title="Resultado",
        ))
    else:
        console.print("[yellow]Especifique --article-id ou --all-pending[/yellow]")


@app.command()
def schedule(
    articles_per_day: int = typer.Option(5, help="Artigos por dia"),
    start_time: str = typer.Option("08:00", help="Hora de início"),
    end_time: str = typer.Option("18:00", help="Hora de fim"),
    daemon: bool = typer.Option(False, help="Executar como daemon"),
) -> None:
    """⏰ Gerencia agendamento de publicações."""
    setup_logging()

    from modules.scheduler import PublicationScheduler

    scheduler = PublicationScheduler(
        articles_per_day=articles_per_day,
        start_time=start_time,
        end_time=end_time,
    )

    if daemon:
        console.print("[cyan]🔄 Iniciando daemon de agendamento...[/cyan]")
        scheduler.start_daemon()
    else:
        # Process pending and show overview
        results = scheduler.process_pending()
        overview = scheduler.get_schedule_overview()

        console.print(Panel(json.dumps(overview, indent=2, default=str), title="📅 Visão Geral"))

        if results["total_pending"] > 0:
            console.print(
                f"Processados: {results['published']} publicados, {results['failed']} falhas"
            )


# ──────────────────────────────────────────────
# OPTIMIZATION COMMANDS
# ──────────────────────────────────────────────

@app.command()
def optimize(
    article_id: str = typer.Option("", help="ID do artigo"),
    all_articles: bool = typer.Option(False, "--all", help="Otimizar todos"),
    fix_auto: bool = typer.Option(False, "--fix-auto", help="Aplicar correções automáticas"),
) -> None:
    """🔧 Otimiza artigos para SEO."""
    setup_logging()

    from config import GENERATED_ARTICLES_DIR
    from modules.seo_optimizer import SEOOptimizer

    optimizer = SEOOptimizer()

    if article_id:
        art_file = GENERATED_ARTICLES_DIR / article_id / "article.json"
        if not art_file.exists():
            console.print(f"[red]Artigo não encontrado: {article_id}[/red]")
            raise typer.Exit(1)

        article = Article.from_storage_dict(
            json.loads(art_file.read_text(encoding="utf-8"))
        )
        article, report = optimizer.optimize(article, auto_fix=fix_auto)
        console.print(report.to_summary_string())

        if fix_auto:
            art_file.write_text(
                json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            console.print("[green]✅ Correções aplicadas e salvas[/green]")

    elif all_articles:
        count = 0
        for art_dir in GENERATED_ARTICLES_DIR.iterdir():
            json_file = art_dir / "article.json"
            if json_file.exists():
                art = Article.from_storage_dict(
                    json.loads(json_file.read_text(encoding="utf-8"))
                )
                art, report = optimizer.optimize(art, auto_fix=fix_auto)
                console.print(f"{art.title[:50]}: {report.overall_score:.0f}/100 ({report.grade})")
                if fix_auto:
                    json_file.write_text(
                        json.dumps(art.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8",
                    )
                count += 1
        console.print(f"\n✅ {count} artigos analisados")
    else:
        console.print("[yellow]Especifique --article-id ou --all[/yellow]")


@app.command()
def backlinks(
    rebuild: bool = typer.Option(False, "--rebuild", help="Reconstruir grafo completo"),
    report: bool = typer.Option(False, "--report", help="Gerar relatório de saúde"),
) -> None:
    """🔗 Gerencia sistema de links internos."""
    setup_logging()

    from modules.backlink_system import BacklinkSystem

    system = BacklinkSystem()

    if rebuild:
        from config import GENERATED_ARTICLES_DIR
        articles = []
        for art_dir in GENERATED_ARTICLES_DIR.iterdir():
            json_file = art_dir / "article.json"
            if json_file.exists():
                art = Article.from_storage_dict(
                    json.loads(json_file.read_text(encoding="utf-8"))
                )
                articles.append(art)

        health = system.rebuild_graph(articles)
        console.print(Panel(json.dumps(health, indent=2, default=str), title="🔗 Grafo Reconstruído"))

    elif report:
        health = system.generate_health_report()
        console.print(Panel(json.dumps(health, indent=2, default=str), title="🔗 Saúde do Grafo"))
    else:
        console.print("[yellow]Especifique --rebuild ou --report[/yellow]")


# ──────────────────────────────────────────────
# STATUS & REPORTS
# ──────────────────────────────────────────────

@app.command()
def status() -> None:
    """Mostra status geral do sistema."""
    setup_logging()

    from config import GENERATED_ARTICLES_DIR, IMAGES_DIR, KEYWORDS_DIR

    art_count = sum(1 for d in GENERATED_ARTICLES_DIR.iterdir() if d.is_dir()) if GENERATED_ARTICLES_DIR.exists() else 0
    img_count = sum(1 for f in IMAGES_DIR.iterdir() if f.is_file()) if IMAGES_DIR.exists() else 0
    kw_count = sum(1 for f in KEYWORDS_DIR.iterdir() if f.is_file()) if KEYWORDS_DIR.exists() else 0

    settings = get_settings()

    table = Table(title="Status do Sistema")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Artigos Gerados", str(art_count))
    table.add_row("Imagens", str(img_count))
    table.add_row("Arquivos de Keywords", str(kw_count))
    table.add_row("Provider LLM Padrão", settings.default_llm_provider.value)
    table.add_row("Idioma Padrão", settings.default_language)
    table.add_row("Odoo URL", settings.odoo_url or "[não configurado]")
    table.add_row("Artigos/dia", str(settings.articles_per_day))
    console.print(table)


@app.command()
def generate_from_cluster(
    seed: str = typer.Argument(..., help="Keyword semente"),
    max_articles: int = typer.Option(10, help="Máximo de artigos"),
    concurrent: int = typer.Option(5, help="Chamadas simultâneas"),
) -> None:
    """🌐 Gera artigos a partir de um cluster de keywords."""
    setup_logging()

    console.print(Panel(f"[bold]Gerando a partir do cluster:[/bold] {seed}", title="Cluster -> Articles"))

    async def _gen_from_cluster():
        from modules.keyword_cluster import KeywordClusterGenerator
        from modules.bulk_generator import BulkGenerator

        # Generate cluster
        cluster_gen = KeywordClusterGenerator(max_keywords=max_articles * 2)
        content_map = await cluster_gen.generate_cluster(seed_keyword=seed, depth=2)
        await cluster_gen.close()

        # Get top keywords
        all_kws = content_map.get_all_keywords()
        all_kws.sort(key=lambda k: k.opportunity_score, reverse=True)
        top_keywords = [kw.keyword for kw in all_kws[:max_articles]]

        console.print(f"{len(top_keywords)} keywords selecionadas para geracao")

        # Generate articles
        bulk = BulkGenerator(concurrent=concurrent)
        results = await bulk.generate_bulk(
            topic=seed,
            count=len(top_keywords),
            keywords=top_keywords,
        )

        console.print(Panel(
            f"[green]✅ {results['completed']} artigos gerados[/green] | "
            f"[red]❌ {results['failed']} falhas[/red]",
            title="Resultado",
        ))

    _run_async(_gen_from_cluster())


# Import Article at module level for publish command
from models.article import Article, ArticleStatus


@app.command()
def auto(
    topic: str = typer.Argument(..., help="Tópico/keyword principal do artigo"),
    count: int = typer.Option(1, "--count", "-n", help="Número de artigos a gerar"),
    tone: str = typer.Option("professional", help="Tom de voz"),
    depth: str = typer.Option("intermediate", help="Profundidade"),
    language: str = typer.Option("pt-br", "--lang", help="Idioma"),
    article_type: str = typer.Option("guia", "--type", help="Tipo de artigo"),
    min_words: int = typer.Option(1500, help="Mínimo de palavras"),
    max_words: int = typer.Option(2500, help="Máximo de palavras"),
    provider: str = typer.Option("", help="Provider LLM (gemini/openai/ollama)"),
    publish_now: bool = typer.Option(True, "--publish/--no-publish", help="Publicar imediatamente"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simular sem publicar"),
) -> None:
    """Pipeline completo: Gera, otimiza e publica artigos automaticamente."""
    setup_logging()

    console.print(Panel(
        f"[bold cyan]Pipeline Automatico[/bold cyan]\n"
        f"Topico: {topic} | Artigos: {count} | Provider: {provider or 'padrao'}",
        title="Auto Pipeline",
    ))

    async def _auto():
        from modules.ai_content_generator import AIContentGenerator
        from modules.seo_optimizer import SEOOptimizer
        from modules.tag_generator import TagGenerator
        from modules.odoo_publisher import OdooPublisher

        tone_map = {t.value: t for t in ToneOfVoice}
        depth_map = {d.value: d for d in ContentDepth}
        type_map = {t.value: t for t in ArticleType}
        prov_map = {p.value: p for p in LLMProvider}

        sel_provider = prov_map.get(provider) if provider else None
        sel_tone = tone_map.get(tone, ToneOfVoice.PROFESSIONAL)
        sel_depth = depth_map.get(depth, ContentDepth.INTERMEDIATE)
        sel_type = type_map.get(article_type, ArticleType.GUIDE)

        gen = AIContentGenerator(provider=sel_provider)
        optimizer = SEOOptimizer()
        tag_gen = TagGenerator(provider=sel_provider)

        # Connect to Odoo if publishing
        publisher = None
        if publish_now and not dry_run:
            publisher = OdooPublisher()
            if not publisher.check_connectivity():
                console.print("[red]❌ Não foi possível conectar ao Odoo. Artigos serão salvos localmente.[/red]")
                publisher = None
            else:
                console.print("[green]✅ Conectado ao Odoo[/green]")

        # Generate keywords for multiple articles
        keywords_to_generate = [topic]
        if count > 1:
            try:
                llm_prov = gen._get_provider(sel_provider or get_settings().default_llm_provider)
                prompt = (
                    f"Gere {count} tópicos de artigo de blog variados "
                    f"sobre '{topic}' em {language}.\n"
                    f"Cada tópico deve ser uma keyword específica de cauda longa.\n"
                    f"Varie entre how-to, listicles, guias, comparativos.\n\n"
                    f"Formato JSON: {{\"keywords\": [\"keyword1\", \"keyword2\", ...]}}"
                )
                response = await llm_prov.generate_structured(prompt=prompt)
                import json as _json
                data = _json.loads(response.content)
                keywords_to_generate = data.get("keywords", [topic])[:count]
                if not keywords_to_generate:
                    keywords_to_generate = [topic]
            except Exception as exc:
                console.print(f"[yellow]AVISO: Usando topico unico: {exc}[/yellow]")
                keywords_to_generate = [topic]

        console.print(f"\nKeywords para geracao: {len(keywords_to_generate)}")
        for i, kw in enumerate(keywords_to_generate, 1):
            console.print(f"  {i}. {kw}")

        results = {"generated": 0, "published": 0, "failed": 0}

        for i, keyword in enumerate(keywords_to_generate, 1):
            console.print(f"\n{'-' * 60}")
            console.print(f"[bold cyan]INFO: [{i}/{len(keywords_to_generate)}] Gerando: {keyword}[/bold cyan]")

            try:
                # Step 1: Generate article
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                    task = progress.add_task("Gerando conteúdo com IA...", total=None)
                    article = await gen.generate_article(
                        keyword=keyword,
                        article_type=sel_type,
                        tone=sel_tone,
                        depth=sel_depth,
                        language=language,
                        min_words=min_words,
                        max_words=max_words,
                    )
                    progress.remove_task(task)

                console.print(f"  OK: Artigo gerado: [green]{article.title}[/green]")
                console.print(f"     Palavras: {article.metadata.word_count} | Provider: {article.metadata.llm_provider}")

                # Step 2: Optimize SEO
                article, seo_report = optimizer.optimize(article, auto_fix=True)
                console.print(f"  OK: SEO Score: {seo_report.overall_score:.0f}/100 ({seo_report.grade})")

                # Step 3: Generate tags
                try:
                    tags = await tag_gen.generate_tags(article)
                    console.print(f"  OK: Tags: {', '.join(tags[:5])}")
                except Exception as tag_exc:
                    console.print(f"  AVISO: Tags: erro ({tag_exc})")

                # Step 4: Save to disk
                from config import GENERATED_ARTICLES_DIR
                art_dir = GENERATED_ARTICLES_DIR / article.id
                art_dir.mkdir(parents=True, exist_ok=True)
                (art_dir / "article.json").write_text(
                    json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                (art_dir / "content.html").write_text(article.content_html, encoding="utf-8")
                console.print(f"  OK: Salvo em: {art_dir}")

                results["generated"] += 1

                # Step 5: Publish to Odoo
                if publisher and not dry_run:
                    try:
                        # Resolve tags in Odoo
                        if article.tags:
                            tag_ids = publisher.resolve_tags(article.tags[:7])
                            article.tag_ids = tag_ids

                        # Mark as ready
                        article.mark_as_ready()

                        post_id = publisher.publish_article(article, publish=True)
                        console.print(f"  OK: Publicado no Odoo! Post ID: [bold green]{post_id}[/bold green]")
                        results["published"] += 1

                        # Update saved file
                        (art_dir / "article.json").write_text(
                            json.dumps(article.to_storage_dict(), indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8",
                        )
                    except Exception as pub_exc:
                        console.print(f"  ERRO: Erro ao publicar: {pub_exc}")
                elif dry_run:
                    console.print("  INFO: Dry-run: publicação simulada")

            except Exception as exc:
                results["failed"] += 1
                console.print(f"  ERRO: Falha: {exc}")
                import traceback
                console.print(f"     {traceback.format_exc()[-200:]}")

        # Final summary
        console.print(f"\n{'=' * 60}")
        console.print(Panel(
            f"[green]OK: Gerados: {results['generated']}[/green] | "
            f"[blue]Publicados: {results['published']}[/blue] | "
            f"[red]Erro: Falhas: {results['failed']}[/red]",
            title="Resultado Final",
        ))

    _run_async(_auto())


if __name__ == "__main__":
    app()
