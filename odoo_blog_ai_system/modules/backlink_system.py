"""
Sistema de Backlinks Internos.

Mantém um grafo de conteúdo para gerenciar links internos entre artigos,
garantindo uma distribuição saudável de PageRank interno.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR, get_settings
from models.article import Article
from utils.logger import get_logger
from utils.text_processing import strip_html_tags

logger = get_logger("backlink_system")

GRAPH_FILE = DATA_DIR / "db" / "link_graph.json"


class BacklinkSystem:
    """Sistema de gerenciamento de links internos entre artigos."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._graph: Optional[Any] = None
        self._articles: dict[str, dict[str, Any]] = {}
        self._load_graph()

    def _load_graph(self) -> None:
        """Carrega o grafo de links do disco."""
        try:
            import networkx as nx
            self._graph = nx.DiGraph()

            if GRAPH_FILE.exists():
                data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
                self._articles = data.get("articles", {})
                for edge in data.get("edges", []):
                    self._graph.add_edge(
                        edge["from"],
                        edge["to"],
                        anchor=edge.get("anchor", ""),
                        weight=edge.get("weight", 1.0),
                    )
                logger.info("link_graph_loaded", nodes=self._graph.number_of_nodes(), edges=self._graph.number_of_edges())
            else:
                logger.info("link_graph_new")

        except ImportError:
            logger.warning("networkx_not_available", msg="Usando grafo simplificado")
            self._graph = _SimpleGraph()
            if GRAPH_FILE.exists():
                data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
                self._articles = data.get("articles", {})
                for edge in data.get("edges", []):
                    self._graph.add_edge(edge["from"], edge["to"], anchor=edge.get("anchor", ""))

    def _save_graph(self) -> None:
        """Salva o grafo em disco."""
        edges: list[dict[str, Any]] = []

        if hasattr(self._graph, "edges"):
            for u, v, data in self._graph.edges(data=True):
                edges.append({
                    "from": u,
                    "to": v,
                    "anchor": data.get("anchor", ""),
                    "weight": data.get("weight", 1.0),
                })

        save_data = {
            "articles": self._articles,
            "edges": edges,
        }

        GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        GRAPH_FILE.write_text(json.dumps(save_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("link_graph_saved")

    def add_article(self, article: Article) -> None:
        """
        Adiciona um artigo ao grafo de links.

        Args:
            article: Artigo a adicionar.
        """
        self._articles[article.id] = {
            "title": article.title,
            "slug": article.slug,
            "keyword": article.metadata.keyword_primary,
            "url": f"/blog/{article.slug}",
            "is_pillar": article.is_pillar,
            "cluster_id": article.cluster_id,
            "odoo_post_id": article.odoo_post_id,
        }

        if hasattr(self._graph, "add_node"):
            self._graph.add_node(article.id)

        logger.info("article_added_to_graph", article_id=article.id, title=article.title)

    def add_link(
        self,
        from_article_id: str,
        to_article_id: str,
        anchor_text: str,
    ) -> bool:
        """
        Adiciona um link entre dois artigos.

        Args:
            from_article_id: ID do artigo de origem.
            to_article_id: ID do artigo de destino.
            anchor_text: Texto âncora.

        Returns:
            True se o link foi adicionado.
        """
        if from_article_id == to_article_id:
            return False

        # Check for generic anchor text
        generic_anchors = {"clique aqui", "saiba mais", "leia mais", "click here", "read more", "veja"}
        if anchor_text.lower().strip() in generic_anchors:
            logger.warning("generic_anchor_rejected", anchor=anchor_text)
            return False

        self._graph.add_edge(from_article_id, to_article_id, anchor=anchor_text)
        logger.debug("link_added", from_id=from_article_id, to_id=to_article_id, anchor=anchor_text)
        return True

    def find_related_articles(
        self,
        article: Article,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Encontra artigos relacionados para linking.

        Args:
            article: Artigo de referência.
            max_results: Máximo de resultados.

        Returns:
            Lista de artigos relacionados com informações para linking.
        """
        keyword = article.metadata.keyword_primary.lower()
        keyword_words = set(keyword.split())
        related: list[tuple[str, float]] = []

        for art_id, art_data in self._articles.items():
            if art_id == article.id:
                continue

            other_keyword = art_data.get("keyword", "").lower()
            other_words = set(other_keyword.split())

            # Calculate relevance score based on keyword overlap
            overlap = keyword_words & other_words
            if overlap:
                score = len(overlap) / max(len(keyword_words), len(other_words))
                related.append((art_id, score))

            # Also check cluster membership
            if (article.cluster_id and art_data.get("cluster_id") == article.cluster_id):
                # Boost score for same cluster
                existing_scores = {r[0]: r[1] for r in related}
                if art_id in existing_scores:
                    related = [(aid, s + 0.3 if aid == art_id else s) for aid, s in related]
                else:
                    related.append((art_id, 0.3))

        # Sort by relevance
        related.sort(key=lambda x: x[1], reverse=True)

        results: list[dict[str, Any]] = []
        for art_id, score in related[:max_results]:
            art_data = self._articles[art_id]
            results.append({
                "article_id": art_id,
                "title": art_data["title"],
                "slug": art_data["slug"],
                "keyword": art_data["keyword"],
                "url": art_data["url"],
                "relevance_score": round(score, 2),
            })

        return results

    def insert_internal_links(
        self,
        article: Article,
        max_links: int = 5,
        max_links_per_200_words: int = 1,
    ) -> Article:
        """
        Insere links internos no conteúdo do artigo.

        Args:
            article: Artigo para inserir links.
            max_links: Máximo de links a inserir.
            max_links_per_200_words: Máximo de links por 200 palavras.

        Returns:
            Artigo com links internos inseridos.
        """
        related = self.find_related_articles(article, max_results=max_links + 2)

        if not related:
            logger.info("no_related_articles", article_id=article.id)
            return article

        html = article.content_html
        links_inserted = 0
        word_count = len(strip_html_tags(html).split())
        max_total_links = min(max_links, word_count // 200 * max_links_per_200_words)
        max_total_links = max(3, max_total_links)

        for rel in related:
            if links_inserted >= max_total_links:
                break

            keyword_to_link = rel["keyword"]
            url = rel["url"]
            anchor = keyword_to_link

            # Find a natural place to insert the link
            # Look for the keyword in the text (case-insensitive, outside existing links)
            pattern = re.compile(
                rf'(?<!["\'>])({re.escape(keyword_to_link)})(?!["\'])',
                re.IGNORECASE,
            )

            def replace_first(match: re.Match) -> str:
                return f'<a href="{url}" title="{rel["title"]}">{match.group(1)}</a>'

            new_html, count = pattern.subn(replace_first, html, count=1)

            if count > 0:
                html = new_html
                links_inserted += 1
                self.add_link(article.id, rel["article_id"], anchor)
                article.internal_links.append({
                    "url": url,
                    "anchor": anchor,
                    "target_article_id": rel["article_id"],
                })

        article.content_html = html
        article.metadata.internal_links_count = links_inserted

        logger.info(
            "internal_links_inserted",
            article_id=article.id,
            count=links_inserted,
        )

        return article

    def update_old_articles_links(
        self,
        new_article: Article,
        articles: list[Article],
        max_backlinks: int = 3,
    ) -> list[Article]:
        """
        Atualiza artigos antigos para linkar para o novo artigo.

        Args:
            new_article: Novo artigo publicado.
            articles: Lista de artigos existentes.
            max_backlinks: Máximo de backlinks a adicionar.

        Returns:
            Lista de artigos atualizados.
        """
        updated: list[Article] = []
        keyword = new_article.metadata.keyword_primary
        url = f"/blog/{new_article.slug}"
        backlinks_added = 0

        for old_article in articles:
            if backlinks_added >= max_backlinks:
                break
            if old_article.id == new_article.id:
                continue

            plain = strip_html_tags(old_article.content_html).lower()
            if keyword.lower() in plain:
                # Check if link already exists
                if url in old_article.content_html:
                    continue

                pattern = re.compile(
                    rf'(?<!["\'>])({re.escape(keyword)})(?!["\'])',
                    re.IGNORECASE,
                )

                new_html, count = pattern.subn(
                    f'<a href="{url}" title="{new_article.title}">\\1</a>',
                    old_article.content_html,
                    count=1,
                )

                if count > 0:
                    old_article.content_html = new_html
                    self.add_link(old_article.id, new_article.id, keyword)
                    updated.append(old_article)
                    backlinks_added += 1

        logger.info(
            "old_articles_updated",
            new_article_id=new_article.id,
            updated_count=len(updated),
        )

        return updated

    def generate_health_report(self) -> dict[str, Any]:
        """
        Gera relatório de saúde do grafo de links.

        Returns:
            Dict com métricas e problemas identificados.
        """
        total_articles = len(self._articles)

        if total_articles == 0:
            return {
                "total_articles": 0,
                "total_links": 0,
                "health_score": 0,
                "issues": ["Nenhum artigo no grafo"],
            }

        total_edges = self._graph.number_of_edges() if hasattr(self._graph, "number_of_edges") else 0

        # Find orphan articles (no incoming or outgoing links)
        orphans: list[str] = []
        low_inbound: list[str] = []
        low_outbound: list[str] = []

        for art_id in self._articles:
            if hasattr(self._graph, "in_degree") and hasattr(self._graph, "out_degree"):
                in_deg = self._graph.in_degree(art_id) if art_id in self._graph else 0
                out_deg = self._graph.out_degree(art_id) if art_id in self._graph else 0
            else:
                in_deg = 0
                out_deg = 0

            if in_deg == 0 and out_deg == 0:
                orphans.append(self._articles[art_id].get("title", art_id))
            elif in_deg < 2:
                low_inbound.append(self._articles[art_id].get("title", art_id))
            if out_deg < 2:
                low_outbound.append(self._articles[art_id].get("title", art_id))

        # Calculate health score
        issues: list[str] = []
        score = 100

        if orphans:
            score -= len(orphans) * 10
            issues.append(f"{len(orphans)} artigo(s) órfão(s): {', '.join(orphans[:5])}")

        if low_inbound:
            score -= len(low_inbound) * 3
            issues.append(f"{len(low_inbound)} artigo(s) com poucos links de entrada")

        if low_outbound:
            score -= len(low_outbound) * 2
            issues.append(f"{len(low_outbound)} artigo(s) com poucos links de saída")

        avg_links = total_edges / max(total_articles, 1)
        if avg_links < 2:
            score -= 15
            issues.append(f"Média de links por artigo baixa: {avg_links:.1f}")

        report = {
            "total_articles": total_articles,
            "total_links": total_edges,
            "avg_links_per_article": round(avg_links, 1),
            "orphan_articles": orphans,
            "low_inbound_articles": low_inbound[:10],
            "low_outbound_articles": low_outbound[:10],
            "health_score": max(0, score),
            "issues": issues,
        }

        # Try to calculate PageRank distribution
        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph) and self._graph.number_of_nodes() > 0:
                pagerank = nx.pagerank(self._graph)
                sorted_pr = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
                report["top_pagerank"] = [
                    {
                        "article": self._articles.get(aid, {}).get("title", aid),
                        "pagerank": round(pr, 4),
                    }
                    for aid, pr in sorted_pr[:10]
                ]
        except Exception:
            pass

        self._save_graph()
        return report

    def rebuild_graph(self, articles: list[Article]) -> dict[str, Any]:
        """
        Reconstrói todo o grafo de links a partir da lista de artigos.

        Args:
            articles: Lista completa de artigos.

        Returns:
            Relatório de saúde pós-reconstrução.
        """
        logger.info("rebuilding_link_graph", article_count=len(articles))

        # Clear existing graph
        try:
            import networkx as nx
            self._graph = nx.DiGraph()
        except ImportError:
            self._graph = _SimpleGraph()

        self._articles.clear()

        # Add all articles
        for article in articles:
            self.add_article(article)

        # Extract existing links from HTML
        for article in articles:
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', article.content_html)
            for url, anchor in links:
                if url.startswith("/blog/"):
                    # Find target article by slug
                    slug = url.replace("/blog/", "").strip("/")
                    for art_id, art_data in self._articles.items():
                        if art_data.get("slug") == slug:
                            self.add_link(article.id, art_id, anchor)
                            break

        self._save_graph()
        return self.generate_health_report()


class _SimpleGraph:
    """Grafo simples para quando NetworkX não está disponível."""

    def __init__(self) -> None:
        self._edges: list[tuple[str, str, dict[str, Any]]] = []
        self._nodes: set[str] = set()

    def add_node(self, node: str) -> None:
        self._nodes.add(node)

    def add_edge(self, u: str, v: str, **data: Any) -> None:
        self._nodes.add(u)
        self._nodes.add(v)
        self._edges.append((u, v, data))

    def number_of_nodes(self) -> int:
        return len(self._nodes)

    def number_of_edges(self) -> int:
        return len(self._edges)

    def edges(self, data: bool = False) -> list[Any]:
        if data:
            return self._edges
        return [(u, v) for u, v, _ in self._edges]

    def in_degree(self, node: str) -> int:
        return sum(1 for _, v, _ in self._edges if v == node)

    def out_degree(self, node: str) -> int:
        return sum(1 for u, _, _ in self._edges if u == node)

    def __contains__(self, node: str) -> bool:
        return node in self._nodes
