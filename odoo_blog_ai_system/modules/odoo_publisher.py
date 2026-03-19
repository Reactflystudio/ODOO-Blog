"""
Módulo de Publicação no Odoo.

Integração via XML-RPC com Odoo 17+ para CRUD completo no modelo
blog.post, upload de imagens e gerenciamento de tags.
"""

from __future__ import annotations

import base64
import json
import re
import xmlrpc.client
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import get_settings
from models.article import Article, ArticleStatus
from utils.logger import get_logger

logger = get_logger("odoo_publisher")


class OdooPublisher:
    """Publicador de artigos no Odoo via XML-RPC."""

    def __init__(
        self,
        url: str = "",
        db: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        """
        Args:
            url: URL do Odoo (override).
            db: Nome do banco (override).
            username: Usuário (override).
            password: Senha (override).
        """
        settings = get_settings()
        self.url = (url or settings.odoo_url).rstrip("/")
        self.db = db or settings.odoo_db
        self.username = username or settings.odoo_username
        self.password = password or settings.odoo_password
        self._uid: Optional[int] = None
        self._common: Optional[xmlrpc.client.ServerProxy] = None
        self._models: Optional[xmlrpc.client.ServerProxy] = None

    def _get_common(self) -> xmlrpc.client.ServerProxy:
        """Retorna proxy XML-RPC para endpoint common."""
        if self._common is None:
            self._common = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/common",
                allow_none=True,
            )
        return self._common

    def _get_models(self) -> xmlrpc.client.ServerProxy:
        """Retorna proxy XML-RPC para endpoint object."""
        if self._models is None:
            self._models = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/object",
                allow_none=True,
            )
        return self._models

    def authenticate(self) -> int:
        """
        Autentica no Odoo e retorna o UID.

        Returns:
            UID do usuário autenticado.

        Raises:
            ConnectionError: Se a autenticação falhar.
        """
        if self._uid is not None:
            return self._uid

        logger.info("odoo_authenticating", url=self.url, db=self.db, user=self.username)

        try:
            common = self._get_common()
            uid = common.authenticate(self.db, self.username, self.password, {})

            if not uid:
                raise ConnectionError(
                    f"Falha na autenticação Odoo: URL={self.url}, DB={self.db}, User={self.username}"
                )

            self._uid = uid
            logger.info("odoo_authenticated", uid=uid)
            return uid

        except xmlrpc.client.Fault as exc:
            raise ConnectionError(f"Erro XML-RPC na autenticação: {exc.faultString}") from exc
        except Exception as exc:
            raise ConnectionError(f"Erro de conexão com Odoo: {exc}") from exc

    def _execute(
        self,
        model: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Executa um método no modelo Odoo.

        Args:
            model: Nome do modelo (e.g., 'blog.post').
            method: Método a executar (e.g., 'create', 'write').
            *args: Argumentos posicionais.
            **kwargs: Keyword arguments como opções.

        Returns:
            Resultado da chamada XML-RPC.
        """
        uid = self.authenticate()
        models = self._get_models()

        try:
            result = models.execute_kw(
                self.db, uid, self.password,
                model, method,
                list(args),
                kwargs if kwargs else {},
            )
            return result
        except xmlrpc.client.Fault as exc:
            logger.error(
                "odoo_execute_error",
                model=model,
                method=method,
                error=exc.faultString,
            )
            raise
        except Exception as exc:
            logger.error("odoo_connection_error", error=str(exc))
            raise

    def check_connectivity(self) -> bool:
        """
        Verifica conectividade com o Odoo.

        Returns:
            True se o Odoo está acessível e autenticação funciona.
        """
        try:
            common = self._get_common()
            version = common.version()
            logger.info("odoo_version", version=version.get("server_version", "unknown"))
            self.authenticate()
            return True
        except Exception as exc:
            logger.error("odoo_connectivity_check_failed", error=str(exc))
            return False

    def publish_article(
        self,
        article: Article,
        publish: bool = True,
        dry_run: bool = False,
    ) -> int:
        """
        Publica um artigo no Odoo.

        Args:
            article: Artigo a publicar.
            publish: Se True, marca como publicado imediatamente.
            dry_run: Se True, simula sem efetuar.

        Returns:
            ID do post criado no Odoo.

        Raises:
            RuntimeError: Se a publicação falhar.
        """
        logger.info(
            "publishing_article",
            article_id=article.id,
            title=article.title,
            dry_run=dry_run,
        )

        # Check for duplicates
        existing = self._find_existing_article(article)
        if existing:
            logger.warning(
                "article_already_exists",
                odoo_id=existing,
                title=article.title,
            )
            if not dry_run:
                self._update_article(existing, article)
                article.mark_as_published(existing)
            return existing

        # Prepare data
        data = article.to_odoo_dict()
        data["website_published"] = publish

        if dry_run:
            logger.info("dry_run_publish", data_keys=list(data.keys()))
            return 0

        try:
            # Create blog post
            post_id = self._execute("blog.post", "create", [data])

            if not post_id:
                raise RuntimeError(f"Falha ao criar post no Odoo para: {article.title}")

            # Handle cover image upload
            if article.cover_image and article.cover_image.local_path:
                attachment_id = self._upload_image(
                    article.cover_image.local_path,
                    article.cover_image.filename or f"cover-{article.slug}.webp",
                    post_id,
                )
                if attachment_id:
                    article.cover_image.odoo_attachment_id = attachment_id
                    # Update cover_properties
                    cover_props = json.dumps({
                        "background-image": f"url('/web/image/{attachment_id}')",
                        "background_type": "image",
                        "resize_class": "o_record_has_cover o_half_screen_height",
                        "opacity": "0",
                    })
                    self._execute(
                        "blog.post", "write",
                        [post_id],
                        {"cover_properties": cover_props},
                    )

            # Handle content images
            content_updated = False
            for img in article.content_images:
                if img.local_path:
                    att_id = self._upload_image(
                        img.local_path,
                        img.filename or f"{article.slug}-img-{uuid.uuid4().hex[:6]}.webp",
                        post_id,
                    )
                    if att_id:
                        img.odoo_attachment_id = att_id
                        # Replace the placeholder or empty src in content_html if it exists
                        # Sometimes we inject placeholder URLs like [IMAGE_0] or we need to replace based on alt text.
                        # Wait, the AI generated content_html probably has placeholder text or missing images.
                        # Let's just append the images sequentially if they aren't in the HTML, or try to replace standard tags.
                        # For now, let's inject them at appropriate headings if no placeholder exists.
                        content_updated = True
            
            # Since content images injection is tricky if LLM didn't put img tags, 
            # let's just do a simple replacement if we find `[IMAGE_{i}]` or `<img src="" alt="{img.alt_text}"`
            # For robustness, we will let the SEOOptimizer or ImageGenerator inject placeholders, 
            # and here we replace them.
            if content_updated:
                # Basic injection logic: if [IMAGE_xyz] exists, replace it
                html = article.content_html
                remaining_tags: list[str] = []
                for i, img in enumerate(article.content_images):
                    if img.odoo_attachment_id:
                        img_tag = f'<img src="/web/image/{img.odoo_attachment_id}" alt="{img.alt_text}" class="img-fluid rounded my-4 shadow-sm" loading="lazy" />'
                        placeholder = f"[IMAGE_{i+1}]"
                        if placeholder in html:
                            html = html.replace(placeholder, img_tag)
                        else:
                            remaining_tags.append(img_tag)

                if remaining_tags:
                    # Fallback: inject images after H2s, then append any leftovers
                    h2_pattern = re.compile(r"</h2>", re.IGNORECASE)
                    matches = list(h2_pattern.finditer(html))
                    if matches:
                        out: list[str] = []
                        last = 0
                        idx = 0
                        for m in matches:
                            out.append(html[last:m.end()])
                            if idx < len(remaining_tags):
                                out.append(remaining_tags[idx])
                                idx += 1
                            last = m.end()
                        out.append(html[last:])
                        if idx < len(remaining_tags):
                            out.append("".join(remaining_tags[idx:]))
                        html = "".join(out)
                    else:
                        p_match = re.search(r"</p>", html, flags=re.IGNORECASE)
                        if p_match:
                            pos = p_match.end()
                            html = html[:pos] + "".join(remaining_tags) + html[pos:]
                        else:
                            html = html + "".join(remaining_tags)
                
                if html != article.content_html:
                    article.content_html = html
                    self._execute(
                        "blog.post", "write",
                        [post_id],
                        {"content": html},
                    )

            article.mark_as_published(post_id)

            logger.info(
                "article_published",
                odoo_id=post_id,
                title=article.title,
            )

            return post_id

        except Exception as exc:
            article.mark_as_failed()
            logger.error("publish_failed", error=str(exc), title=article.title)
            raise RuntimeError(f"Erro ao publicar artigo: {exc}") from exc

    def _update_article(self, post_id: int, article: Article) -> None:
        """Atualiza um artigo existente no Odoo."""
        data = article.to_odoo_dict()
        # Don't overwrite publish status on update
        data.pop("website_published", None)

        try:
            self._execute("blog.post", "write", [post_id], data)
            logger.info("article_updated", odoo_id=post_id, title=article.title)
        except Exception as exc:
            logger.error("article_update_failed", odoo_id=post_id, error=str(exc))
            raise

    def _find_existing_article(self, article: Article) -> Optional[int]:
        """Verifica se o artigo já existe no Odoo (por título ou slug)."""
        try:
            domain = ["|", ("name", "=", article.title), ("name", "ilike", article.slug)]
            results = self._execute(
                "blog.post", "search",
                [domain],
                limit=1,
            )
            if results:
                return results[0]
        except Exception as exc:
            logger.warning("duplicate_check_error", error=str(exc))

        return None

    def _upload_image(
        self,
        image_path: str,
        filename: str,
        post_id: int,
    ) -> Optional[int]:
        """
        Faz upload de imagem como ir.attachment no Odoo.

        Args:
            image_path: Caminho local da imagem.
            filename: Nome do arquivo.
            post_id: ID do post associado.

        Returns:
            ID do attachment criado ou None.
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning("image_not_found", path=image_path)
                return None

            image_data = path.read_bytes()
            b64_data = base64.b64encode(image_data).decode("utf-8")

            # Detect MIME type
            suffix = path.suffix.lower()
            mime_map = {
                ".webp": "image/webp",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
            }
            mimetype = mime_map.get(suffix, "image/png")

            attachment_data = {
                "name": filename,
                "type": "binary",
                "datas": b64_data,
                "res_model": "blog.post",
                "res_id": post_id,
                "mimetype": mimetype,
            }

            attachment_id = self._execute("ir.attachment", "create", [attachment_data])

            logger.info(
                "image_uploaded",
                attachment_id=attachment_id,
                filename=filename,
            )

            return attachment_id

        except Exception as exc:
            logger.error("image_upload_failed", error=str(exc), path=image_path)
            return None

    def get_existing_tags(self) -> dict[str, int]:
        """
        Obtém todas as tags de blog existentes no Odoo.

        Returns:
            Dict de {nome_da_tag: tag_id}.
        """
        try:
            tag_ids = self._execute("blog.tag", "search", [[]])
            if not tag_ids:
                return {}

            tags_data = self._execute(
                "blog.tag", "read",
                [tag_ids],
                {"fields": ["id", "name"]},
            )

            return {t["name"]: t["id"] for t in tags_data}

        except Exception as exc:
            logger.error("get_tags_error", error=str(exc))
            return {}

    def create_or_get_tag(self, tag_name: str) -> int:
        """
        Cria uma tag no Odoo ou retorna ID de existente.

        Args:
            tag_name: Nome da tag.

        Returns:
            ID da tag.
        """
        # Search for existing
        try:
            existing = self._execute(
                "blog.tag", "search",
                [[("name", "=ilike", tag_name)]],
                limit=1,
            )
            if existing:
                return existing[0]

            # Create new
            tag_id = self._execute("blog.tag", "create", [{"name": tag_name}])
            logger.info("tag_created", name=tag_name, id=tag_id)
            return tag_id

        except Exception as exc:
            logger.error("tag_create_error", name=tag_name, error=str(exc))
            raise

    def resolve_tags(self, tag_names: list[str]) -> list[int]:
        """
        Converte lista de nomes de tags em IDs do Odoo.

        Args:
            tag_names: Lista de nomes de tags.

        Returns:
            Lista de IDs de tags no Odoo.
        """
        tag_ids: list[int] = []
        for name in tag_names:
            try:
                tag_id = self.create_or_get_tag(name)
                tag_ids.append(tag_id)
            except Exception as exc:
                logger.warning("tag_resolve_failed", name=name, error=str(exc))
        return tag_ids

    def unpublish_article(self, post_id: int) -> bool:
        """
        Despublica um artigo no Odoo.

        Args:
            post_id: ID do post no Odoo.

        Returns:
            True se despublicado com sucesso.
        """
        try:
            self._execute(
                "blog.post", "write",
                [post_id],
                {"website_published": False},
            )
            logger.info("article_unpublished", odoo_id=post_id)
            return True
        except Exception as exc:
            logger.error("unpublish_failed", odoo_id=post_id, error=str(exc))
            return False

    def get_all_posts(
        self,
        limit: int = 100,
        offset: int = 0,
        published_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Obtém todos os posts do blog.

        Args:
            limit: Máximo de resultados.
            offset: Offset para paginação.
            published_only: Se True, retorna apenas publicados.

        Returns:
            Lista de posts como dicts.
        """
        domain: list[Any] = []
        if published_only:
            domain.append(("website_published", "=", True))

        try:
            post_ids = self._execute(
                "blog.post", "search",
                [domain],
                limit=limit,
                offset=offset,
                order="id desc",
            )

            if not post_ids:
                return []

            fields = [
                "id", "name", "subtitle", "content", "blog_id",
                "website_meta_title", "website_meta_description",
                "website_meta_keywords", "website_published",
                "tag_ids", "author_id", "create_date", "write_date",
            ]

            posts = self._execute(
                "blog.post", "read",
                [post_ids],
                {"fields": fields},
            )

            return posts

        except Exception as exc:
            logger.error("get_posts_error", error=str(exc))
            return []

    def batch_publish(
        self,
        articles: list[Article],
        dry_run: bool = False,
        delay_seconds: float = 2.0,
    ) -> dict[str, Any]:
        """
        Publica múltiplos artigos em batch com rate limiting.

        Args:
            articles: Lista de artigos a publicar.
            dry_run: Simular sem efetuar.
            delay_seconds: Delay entre publicações.

        Returns:
            Relatório de publicação.
        """
        import time

        results = {
            "total": len(articles),
            "published": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        for i, article in enumerate(articles):
            logger.info(
                "batch_publish_progress",
                current=i + 1,
                total=len(articles),
                title=article.title,
            )

            try:
                if not article.is_ready_to_publish and article.status != ArticleStatus.GENERATED:
                    results["skipped"] += 1
                    continue

                post_id = self.publish_article(article, dry_run=dry_run)
                if post_id > 0 or dry_run:
                    results["published"] += 1
                else:
                    results["failed"] += 1

            except Exception as exc:
                results["failed"] += 1
                results["errors"].append({"title": article.title, "error": str(exc)})
                logger.error("batch_publish_error", title=article.title, error=str(exc))

            # Rate limiting
            if not dry_run and i < len(articles) - 1:
                time.sleep(delay_seconds)

        logger.info("batch_publish_complete", **{k: v for k, v in results.items() if k != "errors"})
        return results
