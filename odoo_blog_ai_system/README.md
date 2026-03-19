# 🚀 Odoo Blog AI System

> Sistema completo de automação end-to-end para criação e publicação de artigos SEO no Odoo 17+.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Visão Geral

Sistema de automação que cobre **todo o pipeline** de conteúdo para blog:

1. **Pesquisa** → Descoberta de tendências e clusters de keywords
2. **Geração** → Artigos completos com IA (OpenAI, Gemini)
3. **Otimização** → Score SEO automático (0-100) com auto-fix
4. **Publicação** → Integração XML-RPC direta com Odoo
5. **Agendamento** → Distribuição inteligente de publicações

---

## 🏗 Arquitetura

```
odoo_blog_ai_system/
├── config.py                    # Configuração centralizada (Pydantic Settings)
├── main.py                      # CLI principal (Typer + Rich)
├── requirements.txt             # Dependências
├── .env.example                 # Template de variáveis de ambiente
│
├── models/                      # Modelos de dados (Pydantic)
│   ├── article.py               # Article, ArticleMetadata, FAQItem
│   ├── keyword.py               # Keyword, KeywordCluster, ContentMap
│   └── seo_report.py            # SEOReport, SEOCheck
│
├── providers/                   # Provedores de IA
│   ├── llm_provider.py          # Interface abstrata LLM
│   ├── openai_provider.py       # OpenAI (GPT-4o, GPT-4 Turbo)
│   ├── gemini_provider.py       # Google Gemini (2.0 Flash/Pro)
│   └── image_provider.py        # DALL-E 3 + Unsplash fallback
│
├── modules/                     # Módulos de negócio
│   ├── ai_content_generator.py  # Geração de artigos com LLM
│   ├── seo_optimizer.py         # Otimização SEO (20+ checks)
│   ├── keyword_cluster.py       # Clusters de keywords + content map
│   ├── image_generator.py       # Geração de imagens
│   ├── tag_generator.py         # Tags automáticas
│   ├── backlink_system.py       # Grafo de links internos
│   ├── odoo_publisher.py        # Publicação no Odoo (XML-RPC)
│   ├── trend_scraper.py         # Scraping de tendências
│   ├── bulk_generator.py        # Geração massiva (100-500+)
│   └── scheduler.py             # Agendamento inteligente
│
├── utils/                       # Utilitários
│   ├── logger.py                # Logging estruturado (structlog)
│   ├── http_client.py           # HTTP async + retry + rate limit
│   ├── cache.py                 # Cache em disco (diskcache)
│   ├── html_builder.py          # HTML semântico + schema markup
│   ├── text_processing.py       # NLP: slugify, readability, etc.
│   └── content_validator.py     # Validação de conteúdo
│
└── tests/                       # Testes automatizados
    ├── test_text_processing.py
    └── test_seo_optimizer.py
```

---

## ⚡ Início Rápido

### 1. Instalar dependências

```bash
cd odoo_blog_ai_system
pip install -r requirements.txt
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# Edite o .env com suas API keys e credenciais do Odoo
```

### 3. Gerar um artigo

```bash
python main.py generate "marketing digital"
```

### 4. Gerar em massa

```bash
python main.py generate-bulk "marketing digital" --count 50 --concurrent 5
```

---

## 🖥 Comandos CLI

| Comando | Descrição |
|---------|-----------|
| `generate <topic>` | Gera um artigo único otimizado para SEO |
| `generate-bulk <topic>` | Gera múltiplos artigos em batch |
| `generate-from-cluster <seed>` | Gera artigos a partir de cluster de keywords |
| `trends` | Descobre tópicos em alta |
| `cluster <seed>` | Gera cluster de keywords |
| `publish` | Publica artigos no Odoo |
| `schedule` | Gerencia agendamento de publicações |
| `optimize` | Analisa e otimiza SEO |
| `backlinks` | Gerencia links internos |
| `status` | Status do sistema |

### Exemplos

```bash
# Artigo com configurações personalizadas
python main.py generate "automação com IA" --type how-to --tone formal --min-words 2000

# Descobrir tendências do nicho
python main.py trends --niche "inteligência artificial" --limit 30

# Cluster de keywords
python main.py cluster "python para iniciantes" --depth 3 --max-keywords 100

# Publicar todos os artigos pendentes
python main.py publish --all-pending

# Publicar em modo dry-run (simulação)
python main.py publish --all-pending --dry-run

# Agendamento como daemon
python main.py schedule --daemon --articles-per-day 5

# Otimizar com auto-fix
python main.py optimize --all --fix-auto

# Relatório de links internos
python main.py backlinks --report
```

---

## 🔑 Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|-----------|:-----------:|
| `OPENAI_API_KEY` | Chave API OpenAI | ✅* |
| `GOOGLE_AI_API_KEY` | Chave API Google AI | ✅* |
| `ODOO_URL` | URL do Odoo | ✅ |
| `ODOO_DB` | Banco de dados Odoo | ✅ |
| `ODOO_USERNAME` | Usuário Odoo | ✅ |
| `ODOO_PASSWORD` | Senha Odoo | ✅ |
| `DEFAULT_LLM_PROVIDER` | Provider padrão (openai/gemini) | ❌ |
| `UNSPLASH_API_KEY` | Chave Unsplash (fallback imagens) | ❌ |
| `NEWS_API_KEY` | Chave NewsAPI (tendências) | ❌ |

*\*Pelo menos uma chave de LLM é obrigatória*

---

## 🔄 Pipeline Completo

```
[Trends] → [Keywords] → [Content Gen] → [SEO Optimize] → [Tags] → [Images] → [Links] → [Publish] → [Schedule]
```

1. **Trend Scraper**: Google Trends, NewsAPI, HackerNews, Reddit
2. **Keyword Cluster**: Expansão + classificação por intenção de busca
3. **AI Content Generator**: Multi-provider com fallback automático
4. **SEO Optimizer**: 20+ checks, score 0-100, auto-fix
5. **Tag Generator**: LLM + entidades nomeadas + deduplicação fuzzy
6. **Image Generator**: DALL-E 3 + WebP + Unsplash fallback
7. **Backlink System**: Grafo dirigido + PageRank
8. **Odoo Publisher**: XML-RPC + upload imagens + batch
9. **Scheduler**: Horários otimizados + daemon mode

---

## 🧪 Testes

```bash
# Executar todos os testes
python -m pytest tests/ -v

# Com coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## 📄 Licença

MIT License — Empurrão Digital
