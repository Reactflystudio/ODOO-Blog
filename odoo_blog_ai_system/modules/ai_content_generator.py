"""
Módulo de Geração de Conteúdo com LLM.

Gera artigos completos otimizados para SEO usando LLMs com fallback
automático entre providers (OpenAI, Gemini, Anthropic).

Cada artigo inclui: título, slug, meta description, HTML estruturado,
FAQ, schema markup e todos os metadados necessários para publicação.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from config import (
    ArticleType,
    ContentDepth,
    LLMProvider,
    SearchIntent,
    ToneOfVoice,
    get_settings,
)
from models.article import Article, ArticleMetadata, FAQItem, SchemaMarkup
from providers.gemini_provider import GeminiProvider
from providers.llm_provider import LLMProviderBase, LLMResponse
from providers.openai_provider import OpenAIProvider
from providers.ollama_provider import OllamaProvider
from utils.cache import get_cache
from utils.logger import get_logger
from utils.text_processing import (
    calculate_keyword_density,
    count_words,
    slugify,
    strip_html_tags,
    truncate_text,
)

logger = get_logger("ai_content_generator")

# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """Você é um redator de conteúdo SEO especialista, com 10+ anos de experiência em criação de conteúdo que ranqueia no Google.

REGRAS OBRIGATÓRIAS:
1. Escreva em {language} ({language_full})
2. Tom de voz: {tone}
3. Nível de profundidade: {depth}
4. Persona do autor: {author_name}
5. O conteúdo deve ser ORIGINAL, PROFUNDO e PRÁTICO
6. NUNCA use conteúdo genérico ou superficial
7. Parágrafos curtos (2-4 linhas máximo)
8. Use listas, tabelas e destaques para escaneabilidade
9. A keyword principal deve aparecer nos primeiros 100 caracteres
10. Inclua dados, estatísticas e exemplos práticos quando possível

ESTRUTURA DO ARTIGO:
- Introdução: Hook engajante + contexto + preview do conteúdo (150-200 palavras)
- Corpo: 4-8 seções H2, cada uma com suas sub-seções H3
- FAQ: 3-5 perguntas frequentes com respostas objetivas
- Conclusão: Recapitulação + CTA

FORMATAÇÃO:
- Output em HTML semântico válido
- Use tags: h2, h3, p, ul, ol, li, strong, em, blockquote, table
- NÃO inclua tags html, head, body — apenas o conteúdo interno
- NÃO inclua o H1 (será adicionado separadamente)

FORMATO DE SAÍDA OBRIGATÓRIO:
- Responda EXCLUSIVAMENTE com JSON válido puro
- NÃO envolva o JSON em blocos de código markdown (```json ou ```)
- NÃO adicione texto antes ou depois do JSON
- O JSON deve começar com {{ e terminar com }}
"""

ARTICLE_PROMPT_TEMPLATE = """Escreva um artigo completo e detalhado sobre o tema:

**KEYWORD PRINCIPAL:** {keyword}
**TIPO DE ARTIGO:** {article_type}
**KEYWORDS SECUNDÁRIAS:** {secondary_keywords}
**CONTAGEM DE PALAVRAS:** entre {min_words} e {max_words} palavras

REQUISITOS ESPECÍFICOS:
1. O artigo DEVE ter entre {min_words} e {max_words} palavras
2. Inclua a keyword "{keyword}" nos primeiros 100 caracteres do conteúdo
3. Use as keywords secundárias naturalmente nos headings H2 e no corpo
4. Inclua pelo menos 2 listas (ul ou ol)
5. Inclua pelo menos 1 tabela comparativa se aplicável
6. Inclua 1-2 blockquotes com insights relevantes
7. Cada seção H2 deve ter 200-400 palavras
8. Inclua exemplos práticos e dados reais quando possível

FORMATO DE RESPOSTA (JSON):
{{
    "title": "Título otimizado para SEO (max 60 chars, com keyword)",
    "meta_description": "Meta description (150-160 chars, com CTA implícito e keyword)",
    "introduction": "Texto da introdução (150-200 palavras, texto puro sem HTML)",
    "content_html": "Conteúdo HTML completo do corpo do artigo (H2, H3, parágrafos, listas, tabelas)",
    "conclusion": "Texto da conclusão (texto puro sem HTML)",
    "faq_items": [
        {{"question": "Pergunta 1?", "answer": "Resposta objetiva 1"}},
        {{"question": "Pergunta 2?", "answer": "Resposta objetiva 2"}},
        {{"question": "Pergunta 3?", "answer": "Resposta objetiva 3"}}
    ],
    "secondary_keywords_used": ["keyword1", "keyword2", "keyword3"],
    "lsi_keywords": ["termo1", "termo2", "termo3", "termo4", "termo5"]
}}

IMPORTANTE: Responda SOMENTE com o JSON acima. NÃO use blocos de código markdown (```). NÃO adicione explicações. Resposta deve iniciar com {{ e terminar com }}.
"""


class AIContentGenerator:
    """Gerador de conteúdo otimizado para SEO usando LLMs."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        custom_api_keys: Optional[dict] = None,
    ) -> None:
        """
        Args:
            provider: Provedor LLM específico (ou usa o padrão do .env).
            temperature: Temperatura de geração.
            max_tokens: Máximo de tokens na resposta.
            custom_api_keys: Chaves de API personalizadas por provider.
        """
        self.settings = get_settings()
        self.explicit_provider = provider
        self.default_provider = provider or self.settings.default_llm_provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.custom_api_keys = custom_api_keys or {}
        self._providers: dict[LLMProvider, LLMProviderBase] = {}
        self._cache = get_cache("content_generator")
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_llm_calls)

    def _get_provider(self, provider: LLMProvider) -> LLMProviderBase:
        """Retorna ou cria uma instância do provider."""
        if provider not in self._providers:
            api_key = self.custom_api_keys.get(provider)
            if not api_key:
                api_key = self.settings.get_llm_api_key(provider)
            model = self.settings.get_llm_model(provider)

            if provider == LLMProvider.OPENAI:
                self._providers[provider] = OpenAIProvider(
                    api_key=api_key,
                    model=model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif provider == LLMProvider.GEMINI:
                self._providers[provider] = GeminiProvider(
                    api_key=api_key,
                    model=model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif provider == LLMProvider.OLLAMA:
                self._providers[provider] = OllamaProvider(
                    model=model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            else:
                # Fallback to OpenAI for unsupported providers
                logger.warning(
                    "provider_not_implemented",
                    provider=provider.value,
                    fallback="openai",
                )
                self._providers[provider] = OpenAIProvider(
                    api_key=self.settings.get_llm_api_key(LLMProvider.OPENAI),
                    model=self.settings.get_llm_model(LLMProvider.OPENAI),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

        return self._providers[provider]

    async def generate_article(
        self,
        keyword: str,
        article_type: ArticleType = ArticleType.GUIDE,
        secondary_keywords: Optional[list[str]] = None,
        tone: Optional[ToneOfVoice] = None,
        depth: Optional[ContentDepth] = None,
        language: str = "",
        author_name: str = "",
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        provider: Optional[LLMProvider] = None,
        use_cache: bool = True,
        extra_context: str = "",
    ) -> Article:
        """
        Gera um artigo completo otimizado para SEO.

        Args:
            keyword: Keyword principal do artigo.
            article_type: Tipo de artigo.
            secondary_keywords: Keywords secundárias.
            tone: Tom de voz.
            depth: Nível de profundidade.
            language: Idioma.
            author_name: Nome do autor.
            min_words: Mínimo de palavras.
            max_words: Máximo de palavras.
            provider: Provider LLM específico.
            use_cache: Se deve usar cache.

        Returns:
            Artigo completo gerado.
        """
        settings = self.settings
        effective_tone = tone or settings.default_tone
        effective_depth = depth or settings.default_depth
        effective_lang = language or settings.default_language
        effective_min = min_words or settings.min_words
        effective_max = max_words or settings.max_words
        effective_author = author_name or settings.default_author_name
        secondary = secondary_keywords or []

        # Check cache
        cache_key = f"article:{keyword}:{article_type.value}:{effective_lang}:{effective_tone.value}"
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.info("article_from_cache", keyword=keyword)
                return Article.from_storage_dict(cached)

        logger.info(
            "generating_article",
            keyword=keyword,
            article_type=article_type.value,
            tone=effective_tone.value,
            depth=effective_depth.value,
            language=effective_lang,
        )

        start_time = time.monotonic()

        # Generate with fallback
        llm_response = await self._generate_with_fallback(
            keyword=keyword,
            article_type=article_type,
            secondary_keywords=secondary,
            tone=effective_tone,
            depth=effective_depth,
            language=effective_lang,
            author_name=effective_author,
            min_words=effective_min,
            max_words=effective_max,
            provider=provider,
            extra_context=extra_context,
        )

        # Parse response
        article = self._parse_llm_response(
            llm_response=llm_response,
            keyword=keyword,
            article_type=article_type,
            secondary_keywords=secondary,
            tone=effective_tone,
            depth=effective_depth,
            language=effective_lang,
            author_name=effective_author,
            generation_time=time.monotonic() - start_time,
        )

        # Cache result
        if use_cache:
            self._cache.set(cache_key, article.to_storage_dict(), ttl=86400)

        logger.info(
            "article_generated",
            keyword=keyword,
            title=article.title,
            word_count=article.metadata.word_count,
            generation_time_s=round(time.monotonic() - start_time, 2),
        )

        return article

    async def _generate_with_fallback(
        self,
        keyword: str,
        article_type: ArticleType,
        secondary_keywords: list[str],
        tone: ToneOfVoice,
        depth: ContentDepth,
        language: str,
        author_name: str,
        min_words: int,
        max_words: int,
        provider: Optional[LLMProvider] = None,
        extra_context: str = "",
    ) -> LLMResponse:
        """Gera conteúdo com fallback automático entre providers."""
        actual_provider = provider or self.explicit_provider
        providers_to_try = (
            [actual_provider] if actual_provider
            else self.settings.llm_provider_fallback_order
        )

        language_full_map = {
            "pt-br": "Português Brasileiro",
            "pt": "Português",
            "en": "English",
            "es": "Español",
        }

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            language=language,
            language_full=language_full_map.get(language, language),
            tone=tone.value,
            depth=depth.value,
            author_name=author_name,
        )

        # Append examples context
        examples_context = self._get_examples_context()
        if examples_context:
            system_prompt += "\n\nUSE OS SEGUINTES ARTIGOS COMO EXEMPLO DE ESTILO E QUALIDADE:\n"
            system_prompt += examples_context

        # Append extra context (e.g. Empurrao Digital master prompt)
        if extra_context:
            system_prompt += "\n\n" + extra_context

        article_prompt = ARTICLE_PROMPT_TEMPLATE.format(
            keyword=keyword,
            article_type=article_type.value,
            secondary_keywords=", ".join(secondary_keywords) if secondary_keywords else "gerar automaticamente",
            min_words=min_words,
            max_words=max_words,
        )

        last_error: Optional[Exception] = None
        all_errors: list[str] = []

        for prov in providers_to_try:
            try:
                async with self._semaphore:
                    llm_provider = self._get_provider(prov)
                    logger.info("trying_provider", provider=prov.value)

                    response = await llm_provider.generate_structured(
                        prompt=article_prompt,
                        system_prompt=system_prompt,
                    )

                    if response.success and response.content:
                        response.provider = prov.value
                        return response

            except Exception as exc:
                last_error = exc
                error_msg = f"{prov.value}: {str(exc)}"
                all_errors.append(error_msg)
                logger.warning(
                    "provider_failed",
                    provider=prov.value,
                    error=str(exc),
                    msg="Tentando próximo provider...",
                )
                continue

        errors_detail = " | ".join(all_errors)
        raise RuntimeError(
            f"Todos os providers falharam para keyword '{keyword}'. "
            f"Providers tentados: {[p.value for p in providers_to_try]}. "
            f"Erros: {errors_detail}"
        )

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences (```json ... ```) from LLM responses."""
        import re
        stripped = text.strip()
        # Remove leading ```json or ``` (with optional language tag)
        stripped = re.sub(r'^```(?:json|JSON)?\s*\n?', '', stripped)
        # Remove trailing ```
        stripped = re.sub(r'\n?```\s*$', '', stripped)
        return stripped.strip()

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[dict]:
        """Try to extract a JSON object from text using multiple strategies."""
        import re
        # Strategy 1: Find first { and last } and try to parse that
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # Strategy 2: Try to find JSON block in markdown fences
        json_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _extract_html_from_raw(raw_content: str) -> str:
        """Extract HTML content from a raw LLM response when JSON parsing totally fails."""
        import re
        # Try to find content_html value in the raw text
        # Pattern: "content_html": "..." or "content_html": '...'
        match = re.search(
            r'"content_html"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]',
            raw_content,
            re.DOTALL,
        )
        if match:
            html = match.group(1)
            # Unescape JSON string escapes
            html = html.replace('\\n', '\n').replace('\\"', '"').replace('\\/', '/')
            return html

        # Fallback: if the raw content contains HTML tags, extract just those parts
        if '<h2' in raw_content or '<p>' in raw_content or '<h3' in raw_content:
            # Remove any JSON-like wrapping, keep only HTML
            cleaned = re.sub(r'^[^<]*', '', raw_content, count=1)
            # Remove trailing non-HTML content
            last_tag = max(
                cleaned.rfind('</p>'),
                cleaned.rfind('</h2>'),
                cleaned.rfind('</h3>'),
                cleaned.rfind('</ul>'),
                cleaned.rfind('</ol>'),
                cleaned.rfind('</div>'),
                cleaned.rfind('</section>'),
                cleaned.rfind('</table>'),
            )
            if last_tag > 0:
                # Find the end of that closing tag
                end_of_tag = cleaned.find('>', last_tag)
                if end_of_tag > 0:
                    cleaned = cleaned[:end_of_tag + 1]
            return cleaned.strip()

        return ""

    def _parse_llm_response(
        self,
        llm_response: LLMResponse,
        keyword: str,
        article_type: ArticleType,
        secondary_keywords: list[str],
        tone: ToneOfVoice,
        depth: ContentDepth,
        language: str,
        author_name: str,
        generation_time: float,
    ) -> Article:
        """Parseia a resposta do LLM em um objeto Article."""
        raw_content = llm_response.content or ""
        data: Optional[dict] = None

        # Step 1: Strip markdown code fences (```json ... ```)
        cleaned_content = self._strip_markdown_fences(raw_content)

        # Step 2: Try direct JSON parse on cleaned content
        try:
            data = json.loads(cleaned_content)
        except json.JSONDecodeError:
            pass

        # Step 3: If direct parse failed, try extraction strategies
        if data is None:
            data = self._extract_json_from_text(raw_content)

        # Step 4: If still no valid JSON, create fallback
        if data is None:
            logger.error("json_parse_error", content_preview=raw_content[:500])
            # Try to extract just the HTML content from the raw response
            extracted_html = self._extract_html_from_raw(raw_content)
            if not extracted_html:
                # Absolute last resort: use raw content but warn
                logger.warning("using_raw_content_as_html", keyword=keyword)
                extracted_html = raw_content

            data = {
                "title": f"Guia sobre {keyword}",
                "meta_description": f"Descubra tudo sobre {keyword} neste guia completo.",
                "introduction": "",
                "content_html": extracted_html,
                "conclusion": "",
                "faq_items": [],
                "secondary_keywords_used": secondary_keywords,
                "lsi_keywords": [],
            }

        title = data.get("title", f"Guia sobre {keyword}")[:80]
        slug = slugify(title)

        # Parse FAQ items
        faq_items: list[FAQItem] = []
        for faq in data.get("faq_items", []):
            if isinstance(faq, dict) and faq.get("question") and faq.get("answer"):
                try:
                    faq_items.append(FAQItem(
                        question=faq["question"],
                        answer=faq["answer"],
                    ))
                except Exception:
                    pass

        content_html = data.get("content_html", "")
        introduction = data.get("introduction", "")
        conclusion = data.get("conclusion", "")

        # Calculate metrics
        full_text = f"{introduction} {strip_html_tags(content_html)} {conclusion}"
        word_count = count_words(full_text)
        reading_time = max(1, word_count // 200)
        kw_density = calculate_keyword_density(full_text, keyword)

        # Build metadata
        meta_description = data.get("meta_description", "")
        if not meta_description:
            meta_description = truncate_text(
                strip_html_tags(introduction or content_html), 160
            )

        metadata = ArticleMetadata(
            keyword_primary=keyword,
            keywords_secondary=data.get("secondary_keywords_used", secondary_keywords),
            keywords_lsi=data.get("lsi_keywords", []),
            search_intent=SearchIntent.INFORMATIONAL.value,
            article_type=article_type.value,
            tone=tone.value,
            depth=depth.value,
            language=language,
            word_count=word_count,
            reading_time_minutes=reading_time,
            keyword_density=kw_density,
            llm_provider=llm_response.provider,
            llm_model=llm_response.model,
            generation_cost_usd=llm_response.cost_usd,
            generation_time_seconds=round(generation_time, 2),
        )

        article = Article(
            title=title,
            slug=slug,
            meta_title=title[:60],
            meta_description=meta_description[:160],
            content_html=content_html,
            introduction=introduction,
            conclusion=conclusion,
            content_plain=full_text,
            faq_items=faq_items,
            metadata=metadata,
            author_name=author_name,
            blog_id=self.settings.odoo_blog_id,
        )

        article.mark_as_generated()
        return article

    async def regenerate_section(
        self,
        article: Article,
        section_heading: str,
        instructions: str = "",
    ) -> str:
        """
        Regenera uma seção específica do artigo.

        Args:
            article: Artigo existente.
            section_heading: Heading da seção a regenerar.
            instructions: Instruções adicionais.

        Returns:
            HTML da seção regenerada.
        """
        prompt = (
            f"Reescreva a seção '{section_heading}' do artigo sobre "
            f"'{article.metadata.keyword_primary}'.\n\n"
            f"Keyword principal: {article.metadata.keyword_primary}\n"
            f"Tom: {article.metadata.tone}\n"
            f"Idioma: {article.metadata.language}\n"
        )
        if instructions:
            prompt += f"\nInstruções adicionais: {instructions}\n"

        prompt += (
            "\nRetorne APENAS o HTML da seção (começando com <h2> e terminando "
            "antes do próximo <h2>). Sem explicações adicionais."
        )

        async with self._semaphore:
            provider = self._get_provider(self.default_provider)
            response = await provider.generate(prompt=prompt)
            return response.content.strip()

    async def generate_meta_description(self, title: str, keyword: str) -> str:
        """
        Gera uma meta description otimizada.

        Args:
            title: Título do artigo.
            keyword: Keyword principal.

        Returns:
            Meta description (150-160 chars).
        """
        prompt = (
            f"Gere uma meta description otimizada para SEO.\n\n"
            f"Título: {title}\n"
            f"Keyword: {keyword}\n\n"
            f"Requisitos:\n"
            f"- Exatamente 150-160 caracteres\n"
            f"- Inclua a keyword '{keyword}'\n"
            f"- Inclua um CTA implícito\n"
            f"- Seja descritivo e atraente\n\n"
            f"Responda APENAS com a meta description, sem aspas."
        )

        async with self._semaphore:
            provider = self._get_provider(self.default_provider)
            response = await provider.generate(prompt=prompt, max_tokens=200)
            return response.content.strip().strip('"')[:160]

    async def generate_image_prompts(self, article: Article, count: int = 3) -> list[str]:
        """
        Gera prompts para criação de imagens baseadas no conteúdo.

        Args:
            article: Artigo de referência.
            count: Número de prompts a gerar.

        Returns:
            Lista de prompts para geração de imagem.
        """
        prompt = (
            f"Gere {count} prompts em inglês para gerar imagens com IA "
            f"para um artigo de blog sobre: {article.title}\n\n"
            f"Keyword: {article.metadata.keyword_primary}\n"
            f"Tipo de artigo: {article.metadata.article_type}\n\n"
            f"Requisitos para cada prompt:\n"
            f"- Estilo moderno, profissional e minimalista\n"
            f"- Sem texto na imagem\n"
            f"- Ideal para blog corporativo\n"
            f"- Descrição detalhada da composição\n\n"
            f"Responda em JSON: {{\"prompts\": [\"prompt1\", \"prompt2\", ...]}}"
        )

        async with self._semaphore:
            provider = self._get_provider(self.default_provider)
            response = await provider.generate_structured(prompt=prompt)

            try:
                cleaned = self._strip_markdown_fences(response.content)
                data = json.loads(cleaned)
                return data.get("prompts", [])[:count]
            except json.JSONDecodeError:
                logger.warning("image_prompts_parse_error")
                return [
                    f"Modern minimalist illustration about {article.metadata.keyword_primary}, "
                    f"professional blog style, clean design, no text"
                ]

    def _get_examples_context(self) -> str:
        """
        Lê o template ativo e arquivos de exemplo para fornecer contexto ao LLM.
        
        Prioridade:
        1. Template ativo (data/templates/<name>/template.html) — instrui o LLM a seguir fielmente
        2. Exemplos HTML em data/examples/ — referência de estilo
        """
        from config import EXAMPLES_DIR
        from pathlib import Path
        import os
        
        context = ""
        
        # 1. Load active template (highest priority)
        try:
            templates_dir = Path(__file__).resolve().parent.parent / "data" / "templates"
            active_file = templates_dir / "_active.json"
            if active_file.exists():
                import json
                active_config = json.loads(active_file.read_text(encoding="utf-8"))
                template_name = active_config.get("active_template", "")
                if template_name:
                    template_html_file = templates_dir / template_name / "template.html"
                    if template_html_file.exists():
                        template_content = template_html_file.read_text(encoding="utf-8")
                        # Truncate very large templates but keep enough structure
                        if len(template_content) > 15000:
                            template_content = template_content[:15000] + "\n... [template truncado, mas siga a estrutura acima]"
                        
                        context += f"""
=== TEMPLATE DE REFERÊNCIA DE ESTILO CSS E HTML ===
Abaixo está o template mestre do usuário. 
**ATENÇÃO**: O seu papel NÃO é gerar a página HTML inteira (não gere <head>, <body>, scripts, metatags, etc.).
O seu papel é gerar apenas o miolo do artigo (o texto, os H2, H3, p, ul, ol), que será inserido na variável {{CONTENT}} do template real.

PORTANTO, observe o template abaixo APENAS para aprender QUAIS CLASSES CSS e QUAIS ESTRUTURAS o usuário gosta de usar no miolo do conteúdo.
Exemplo: Se o template usa <h2 class="title-section">, use essa mesma classe nos seus H2 gerados.
Se o template usa <ul class="ed-list">, adote isso.

TEMPLATE HTML REFERÊNCIA:
{template_content}
=== FIM DO TEMPLATE ===

REGRA CRÍTICA PARA 'content_html':
Retorne EXCLUSIVAMENTE o HTML do conteúdo interno (parágrafos, subtítulos, listas). NUNCA envolva sua resposta em tags <html> ou <body>, e certifique-se de que a resposta final seja um JSON válido.
"""
                        return context
        except Exception as exc:
            logger.warning("get_active_template_context_error", error=str(exc))
        
        # 2. Fallback: Load example files
        try:
            examples = sorted(
                EXAMPLES_DIR.glob("*.html"),
                key=os.path.getmtime,
                reverse=True
            )[:3]
            
            for i, f in enumerate(examples):
                content = f.read_text(encoding="utf-8")
                if len(content) > 5000:
                    content = content[:5000] + "... [conteúdo truncado]"
                context += f"\n--- EXEMPLO {i+1} ({f.name}) ---\n{content}\n"
                
            return context
        except Exception as exc:
            logger.warning("get_examples_context_error", error=str(exc))
            return ""
