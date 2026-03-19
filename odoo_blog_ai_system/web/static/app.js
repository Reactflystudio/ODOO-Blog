/**
 * BlogAI Dashboard — Frontend Application
 * SPA with Odoo sync, article management, and content generation.
 */

// ──────────────────────────────────────────────
// API Layer
// ──────────────────────────────────────────────

const API = {
    async get(path) {
        try {
            const res = await fetch(`/api${path}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            return await res.json();
        } catch (e) {
            console.error(`GET /api${path}:`, e);
            throw e;
        }
    },
    async post(path, body = {}) {
        try {
            const res = await fetch(`/api${path}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            return await res.json();
        } catch (e) {
            console.error(`POST /api${path}:`, e);
            throw e;
        }
    },
    async del(path) {
        const res = await fetch(`/api${path}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        return await res.json();
    },
};


// ──────────────────────────────────────────────
// Router
// ──────────────────────────────────────────────

let currentPage = 'dashboard';

function navigate(page) {
    currentPage = page;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const active = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (active) active.classList.add('active');

    // Update title
    const titles = {
        'dashboard': 'Dashboard',
        'odoo-posts': 'Artigos Odoo',
        'generate': 'Gerar Artigo',
        'articles': 'Artigos Gerados',
        'bulk': 'Geracao em Massa',
        'keywords': 'Keywords',
        'trends': 'Tendencias',
        'seo': 'SEO',
        'publish': 'Publicar no Odoo',
        'templates': 'Templates HTML',
        'config': 'Configuracoes',
    };
    document.getElementById('pageTitle').textContent = titles[page] || page;

    renderPage(page);
}


// ──────────────────────────────────────────────
// Page Renderer
// ──────────────────────────────────────────────

async function renderPage(page) {
    const container = document.getElementById('pageContainer');
    container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div> Carregando...</div>';

    try {
        switch (page) {
            case 'dashboard': await renderDashboard(container); break;
            case 'odoo-posts': await renderOdooPosts(container); break;
            case 'generate': renderGenerate(container); break;
            case 'articles': await renderArticles(container); break;
            case 'bulk': renderBulk(container); break;
            case 'keywords': renderKeywords(container); break;
            case 'trends': renderTrends(container); break;
            case 'seo': renderSEO(container); break;
            case 'publish': renderPublish(container); break;
            case 'examples': await renderExamples(container); break;
            case 'templates': await renderTemplates(container); break;
            case 'config': await renderConfig(container); break;
            default: container.innerHTML = '<p>Pagina nao encontrada.</p>';
        }
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><h3>Erro ao carregar</h3><p>${e.message}</p></div>`;
    }
}


// ──────────────────────────────────────────────
// Dashboard Page
// ──────────────────────────────────────────────

async function renderDashboard(el) {
    const [status, odoo] = await Promise.all([
        API.get('/status'),
        API.get('/odoo/status'),
    ]);

    const lastSync = odoo.last_sync ? new Date(odoo.last_sync).toLocaleString('pt-BR') : 'Nunca';

    el.innerHTML = `
        <!-- Stats Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #7c3aed, #a855f7)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                </div>
                <div class="stat-value">${odoo.total_posts || 0}</div>
                <div class="stat-label">Artigos no Odoo</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #059669, #34d399)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22,4 12,14.01 9,11.01"/></svg>
                </div>
                <div class="stat-value">${odoo.published || 0}</div>
                <div class="stat-label">Publicados</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #d97706, #fbbf24)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </div>
                <div class="stat-value">${odoo.drafts || 0}</div>
                <div class="stat-label">Rascunhos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #2563eb, #60a5fa)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </div>
                <div class="stat-value">${(odoo.total_posts > 0 ? status.odoo_visits : 0).toLocaleString('pt-BR')}</div>
                <div class="stat-label">Visitas Total</div>
            </div>
        </div>

        <!-- Secondary Stats -->
        <div class="stats-grid stats-secondary">
            <div class="stat-card stat-sm">
                <div class="stat-value-sm">${odoo.total_tags || 0}</div>
                <div class="stat-label">Tags</div>
            </div>
            <div class="stat-card stat-sm">
                <div class="stat-value-sm">${odoo.total_blogs || 0}</div>
                <div class="stat-label">Blogs</div>
            </div>
            <div class="stat-card stat-sm">
                <div class="stat-value-sm">${status.total_words ? (status.total_words / 1000).toFixed(0) + 'k' : '0'}</div>
                <div class="stat-label">Palavras</div>
            </div>
            <div class="stat-card stat-sm">
                <div class="stat-value-sm">${status.articles_generated || 0}</div>
                <div class="stat-label">Gerados AI</div>
            </div>
        </div>

        <!-- Odoo Connection -->
        <div class="card">
            <div class="card-header">
                <h2>Conexao Odoo</h2>
                <button class="btn btn-primary btn-sm" onclick="syncOdoo()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23,4 23,10 17,10"/><polyline points="1,20 1,14 7,14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
                    Sincronizar Agora
                </button>
            </div>
            <div class="card-body">
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Status</span>
                        <span class="info-value">${odoo.connected ? '<span class="badge badge-success">Conectado</span>' : '<span class="badge badge-danger">Desconectado</span>'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">URL</span>
                        <span class="info-value"><a href="${odoo.odoo_url}" target="_blank">${odoo.odoo_url || '-'}</a></span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Banco de Dados</span>
                        <span class="info-value">${odoo.database || '-'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Ultima Sinc.</span>
                        <span class="info-value">${lastSync}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="section-title">Acoes Rapidas</div>
        <div class="actions-grid">
            <div class="action-card" onclick="navigate('generate')">
                <div class="action-icon" style="background: linear-gradient(135deg, #7c3aed, #a855f7)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
                </div>
                <div class="action-info">
                    <strong>Novo Artigo</strong>
                    <small>Gerar artigo otimizado</small>
                </div>
            </div>
            <div class="action-card" onclick="navigate('odoo-posts')">
                <div class="action-icon" style="background: linear-gradient(135deg, #059669, #34d399)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                </div>
                <div class="action-info">
                    <strong>Ver Artigos Odoo</strong>
                    <small>${odoo.total_posts || 0} artigos sincronizados</small>
                </div>
            </div>
            <div class="action-card" onclick="navigate('keywords')">
                <div class="action-icon" style="background: linear-gradient(135deg, #2563eb, #60a5fa)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/></svg>
                </div>
                <div class="action-info">
                    <strong>Keywords</strong>
                    <small>Pesquisar & clusterizar</small>
                </div>
            </div>
            <div class="action-card" onclick="navigate('trends')">
                <div class="action-icon" style="background: linear-gradient(135deg, #dc2626, #f87171)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>
                </div>
                <div class="action-info">
                    <strong>Tendencias</strong>
                    <small>Topicos em alta</small>
                </div>
            </div>
        </div>

        <!-- Recent Odoo Posts -->
        <div class="card">
            <div class="card-header">
                <h2>Ultimos Artigos no Odoo</h2>
                <button class="btn btn-outline btn-sm" onclick="navigate('odoo-posts')">Ver Todos</button>
            </div>
            <div class="card-body" id="recentPostsList">
                <div class="loading-spinner"><div class="spinner"></div></div>
            </div>
        </div>
    `;

    // Load recent posts
    loadRecentOdooPosts();
}

async function loadRecentOdooPosts() {
    const el = document.getElementById('recentPostsList');
    if (!el) return;

    try {
        const data = await API.get('/odoo/posts?limit=10');
        if (!data.posts || data.posts.length === 0) {
            el.innerHTML = `<div class="empty-state"><p>Nenhum artigo sincronizado. Clique em "Sincronizar Agora".</p></div>`;
            return;
        }

        el.innerHTML = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Titulo</th>
                            <th>Status</th>
                            <th>Palavras</th>
                            <th>Visitas</th>
                            <th>Data</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.posts.map(p => `
                            <tr>
                                <td><span class="text-muted">#${p.id}</span></td>
                                <td><strong>${escapeHtml(truncate(p.title, 55))}</strong></td>
                                <td>${p.published
                                    ? '<span class="badge badge-success">Publicado</span>'
                                    : '<span class="badge badge-warning">Rascunho</span>'}</td>
                                <td>${(p.word_count || 0).toLocaleString('pt-BR')}</td>
                                <td>${p.visits || 0}</td>
                                <td><span class="text-muted">${formatDate(p.created_at)}</span></td>
                                <td>
                                    <button class="btn btn-xs btn-outline" onclick="viewOdooPost(${p.id})">Ver</button>
                                    ${p.url ? `<a href="https://www.empurraodigital.com.br${p.url}" target="_blank" class="btn btn-xs btn-outline">Abrir</a>` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="empty-state"><p>Erro ao carregar: ${e.message}</p></div>`;
    }
}


// ──────────────────────────────────────────────
// Odoo Posts Page
// ──────────────────────────────────────────────

async function renderOdooPosts(el) {
    const [postsData, tagsData, blogsData] = await Promise.all([
        API.get('/odoo/posts?limit=200'),
        API.get('/odoo/tags'),
        API.get('/odoo/blogs'),
    ]);

    const posts = postsData.posts || [];
    const tags = tagsData.tags || [];
    const blogs = blogsData.blogs || [];

    const published = posts.filter(p => p.published).length;
    const drafts = posts.filter(p => !p.published).length;
    const totalWords = posts.reduce((a, p) => a + (p.word_count || 0), 0);
    const totalVisits = posts.reduce((a, p) => a + (p.visits || 0), 0);

    el.innerHTML = `
        <!-- Overview -->
        <div class="stats-grid stats-secondary">
            <div class="stat-card stat-sm"><div class="stat-value-sm">${posts.length}</div><div class="stat-label">Total Posts</div></div>
            <div class="stat-card stat-sm"><div class="stat-value-sm" style="color: var(--success)">${published}</div><div class="stat-label">Publicados</div></div>
            <div class="stat-card stat-sm"><div class="stat-value-sm" style="color: var(--warning)">${drafts}</div><div class="stat-label">Rascunhos</div></div>
            <div class="stat-card stat-sm"><div class="stat-value-sm">${totalVisits.toLocaleString('pt-BR')}</div><div class="stat-label">Visitas</div></div>
            <div class="stat-card stat-sm"><div class="stat-value-sm">${(totalWords / 1000).toFixed(0)}k</div><div class="stat-label">Palavras</div></div>
            <div class="stat-card stat-sm"><div class="stat-value-sm">${tags.length}</div><div class="stat-label">Tags</div></div>
        </div>

        <!-- Blogs -->
        ${blogs.length > 0 ? `
        <div class="card">
            <div class="card-header"><h2>Blogs</h2></div>
            <div class="card-body">
                <div class="blogs-grid">
                    ${blogs.map(b => `
                        <div class="blog-card">
                            <strong>[${b.id}] ${escapeHtml(b.name)}</strong>
                            <small>${escapeHtml(b.subtitle || '')}</small>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
        ` : ''}

        <!-- Filters -->
        <div class="card">
            <div class="card-header">
                <h2>Artigos (${posts.length})</h2>
                <div class="filter-group">
                    <button class="btn btn-xs btn-outline filter-active" onclick="filterPosts('all', this)">Todos</button>
                    <button class="btn btn-xs btn-outline" onclick="filterPosts('published', this)">Publicados</button>
                    <button class="btn btn-xs btn-outline" onclick="filterPosts('draft', this)">Rascunhos</button>
                    <input type="text" id="postSearch" class="input input-sm" placeholder="Buscar..." oninput="searchPosts()">
                </div>
            </div>
            <div class="card-body">
                <div class="table-wrapper">
                    <table class="table" id="postsTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Titulo</th>
                                <th>Blog</th>
                                <th>Status</th>
                                <th>Palavras</th>
                                <th>Visitas</th>
                                <th>Tags</th>
                                <th>Data</th>
                                <th>Acoes</th>
                            </tr>
                        </thead>
                        <tbody id="postsBody">
                            ${posts.map(p => postRow(p)).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    // Store posts for filtering
    window._odooPosts = posts;
}

function postRow(p) {
    const tagCount = (p.tag_ids || []).length;
    return `
        <tr data-published="${p.published}" data-title="${(p.title || '').toLowerCase()}">
            <td><span class="text-muted">#${p.id}</span></td>
            <td><strong class="post-title-cell">${escapeHtml(truncate(p.title, 50))}</strong></td>
            <td><span class="text-muted">${escapeHtml(truncate(p.blog_name || '', 20))}</span></td>
            <td>${p.published
                ? '<span class="badge badge-success">PUB</span>'
                : '<span class="badge badge-warning">DRF</span>'}</td>
            <td>${(p.word_count || 0).toLocaleString('pt-BR')}</td>
            <td>${p.visits || 0}</td>
            <td>${tagCount > 0 ? `<span class="badge badge-info">${tagCount}</span>` : '-'}</td>
            <td><span class="text-muted">${formatDate(p.created_at)}</span></td>
            <td>
                <button class="btn btn-xs btn-outline" onclick="viewOdooPost(${p.id})">Ver</button>
                ${p.url ? `<a href="https://www.empurraodigital.com.br${p.url}" target="_blank" class="btn btn-xs btn-outline">Abrir</a>` : ''}
            </td>
        </tr>
    `;
}

function filterPosts(filter, btnEl) {
    document.querySelectorAll('.filter-group .btn').forEach(b => b.classList.remove('filter-active'));
    if (btnEl) btnEl.classList.add('filter-active');

    const rows = document.querySelectorAll('#postsBody tr');
    rows.forEach(row => {
        const pub = row.dataset.published === 'true';
        if (filter === 'all') row.style.display = '';
        else if (filter === 'published') row.style.display = pub ? '' : 'none';
        else if (filter === 'draft') row.style.display = !pub ? '' : 'none';
    });
}

function searchPosts() {
    const q = document.getElementById('postSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#postsBody tr');
    rows.forEach(row => {
        row.style.display = row.dataset.title.includes(q) ? '' : 'none';
    });
}

async function viewOdooPost(postId) {
    try {
        const data = await API.get(`/odoo/posts/${postId}`);
        openModal(escapeHtml(data.title), `
            <div class="post-detail">
                <div class="info-grid" style="margin-bottom: 1.5rem;">
                    <div class="info-item"><span class="info-label">ID</span><span class="info-value">#${data.id}</span></div>
                    <div class="info-item"><span class="info-label">Status</span><span class="info-value">${data.published ? '<span class="badge badge-success">Publicado</span>' : '<span class="badge badge-warning">Rascunho</span>'}</span></div>
                    <div class="info-item"><span class="info-label">Blog</span><span class="info-value">${escapeHtml(data.blog_name || '-')}</span></div>
                    <div class="info-item"><span class="info-label">Autor</span><span class="info-value">${escapeHtml(data.author || '-')}</span></div>
                    <div class="info-item"><span class="info-label">Palavras</span><span class="info-value">${(data.word_count || 0).toLocaleString('pt-BR')}</span></div>
                    <div class="info-item"><span class="info-label">Visitas</span><span class="info-value">${data.visits || 0}</span></div>
                    <div class="info-item"><span class="info-label">Criado em</span><span class="info-value">${formatDate(data.created_at)}</span></div>
                    <div class="info-item"><span class="info-label">Atualizado</span><span class="info-value">${formatDate(data.updated_at)}</span></div>
                </div>
                ${data.subtitle ? `<p class="text-muted"><em>${escapeHtml(data.subtitle)}</em></p>` : ''}
                ${data.meta_title ? `<p><strong>Meta Title:</strong> ${escapeHtml(data.meta_title)}</p>` : ''}
                ${data.meta_description ? `<p><strong>Meta Desc:</strong> ${escapeHtml(data.meta_description)}</p>` : ''}
                ${data.meta_keywords ? `<p><strong>Keywords:</strong> ${escapeHtml(data.meta_keywords)}</p>` : ''}
                ${data.url ? `<p><a href="https://www.empurraodigital.com.br${data.url}" target="_blank" class="btn btn-sm btn-primary">Abrir no Site</a></p>` : ''}
                ${data.content_html ? `<div class="post-content-preview">${data.content_html}</div>` : ''}
            </div>
        `);
    } catch (e) {
        showToast('Erro ao carregar post: ' + e.message, 'error');
    }
}


// ──────────────────────────────────────────────
// Generate Article Page
// ──────────────────────────────────────────────

function renderGenerate(el) {
    el.innerHTML = `
        <!-- Header -->
        <div class="card" style="border-left: 4px solid var(--primary);">
            <div class="card-body" style="padding: 1.2rem 1.5rem;">
                <h2 style="margin:0 0 0.3rem 0; font-size: 1.3rem;">Gerador de Artigos - Empurrao Digital</h2>
                <p class="text-muted" style="margin:0; font-size: 0.85rem;">Artigos otimizados para SEO sobre marketing digital politico no Brasil.</p>
            </div>
        </div>

        <form id="generateForm" onsubmit="handleGenerate(event)">

            <!-- Configuracao dos Posts -->
            <div class="card">
                <div class="card-header"><h2>Configuracao dos Posts</h2></div>
                <div class="card-body">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Quantidade de Posts *</label>
                            <input type="number" class="input" id="genCount" value="1" min="1" max="50" required>
                            <small class="form-help">1 para artigo unico, 2-50 para lote</small>
                        </div>
                        <div class="form-group">
                            <label>Tipo de Artigo</label>
                            <select class="input" id="genType">
                                <option value="guia">Guia Completo</option>
                                <option value="lista">Listicle</option>
                                <option value="tutorial">Tutorial</option>
                                <option value="case_study">Case Study</option>
                                <option value="pillar">Pillar Page</option>
                                <option value="comparacao">Comparacao</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>API Geradora</label>
                            <select class="input" id="genProvider">
                                <option value="ollama" selected>Ollama Llama 3 (Local/Grátis)</option>
                                <option value="">Automático (Fallback)</option>
                                <option value="gemini">Google Gemini (Grátis)</option>
                                <option value="openai">OpenAI ChatGPT</option>
                                <option value="anthropic">Anthropic Claude</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Gemini API Key (Opcional)</label>
                            <input type="text" class="input" id="genGeminiKey" placeholder="Se vazio, usa a do .env">
                        </div>
                        <div class="form-group">
                            <label>OpenAI API Key (Opcional)</label>
                            <input type="text" class="input" id="genOpenaiKey" placeholder="Se vazio, usa a do .env">
                        </div>
                        <div class="form-group">
                            <label>Anthropic API Key (Opcional)</label>
                            <input type="text" class="input" id="genAnthropicKey" placeholder="Se vazio, usa a do .env">
                        </div>
                        <div class="form-group form-full">
                            <label>Temas dos Posts *</label>
                            <textarea class="input" id="genTopics" rows="4" placeholder="Descreva os temas dos artigos, um por linha.&#10;Ex:&#10;Marketing politico para eleicoes 2026&#10;Como engajar jovens eleitores na internet&#10;Estrategias de trafego pago para candidatos" required></textarea>
                            <small class="form-help">Um tema por linha. Se a quantidade for maior que os temas, temas serao gerados automaticamente.</small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Publico-Alvo / Tom / Profundidade -->
            <div class="form-grid" style="grid-template-columns: 1fr 1fr 1fr; gap: 1rem;">
                <div class="card">
                    <div class="card-header"><h2>Publico-Alvo</h2></div>
                    <div class="card-body">
                        <div class="checkbox-group">
                            <label class="checkbox-label"><input type="checkbox" class="checkbox" value="Partidos politicos" checked> Partidos politicos</label>
                            <label class="checkbox-label"><input type="checkbox" class="checkbox" value="Vereadores" checked> Vereadores</label>
                            <label class="checkbox-label"><input type="checkbox" class="checkbox" value="Deputados" checked> Deputados</label>
                            <label class="checkbox-label"><input type="checkbox" class="checkbox" value="Pre-candidatos" checked> Pre-candidatos</label>
                            <label class="checkbox-label"><input type="checkbox" class="checkbox" value="Politicos em geral" checked> Politicos em geral</label>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h2>Tom de Voz</h2></div>
                    <div class="card-body">
                        <div class="checkbox-group">
                            <label class="checkbox-label"><input type="checkbox" class="tone-check" value="Profissional" checked> Profissional</label>
                            <label class="checkbox-label"><input type="checkbox" class="tone-check" value="Didatico" checked> Didatico</label>
                            <label class="checkbox-label"><input type="checkbox" class="tone-check" value="Tecnico" checked> Tecnico</label>
                            <label class="checkbox-label"><input type="checkbox" class="tone-check" value="Inspirador" checked> Inspirador</label>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h2>Nivel de Profundidade</h2></div>
                    <div class="card-body">
                        <select class="input" id="genDepth" style="margin-bottom: 0.8rem;">
                            <option value="intermediate_advanced" selected>Intermediario a Avancado</option>
                            <option value="beginner">Iniciante</option>
                            <option value="intermediate">Intermediario</option>
                            <option value="advanced">Avancado</option>
                            <option value="expert">Expert</option>
                        </select>
                        <div class="form-group">
                            <label>Tamanho dos Artigos (caracteres)</label>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <input type="number" class="input" id="genMinChars" value="3000" min="1000" style="flex:1;">
                                <span class="text-muted">a</span>
                                <input type="number" class="input" id="genMaxChars" value="30000" min="3000" style="flex:1;">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Keywords -->
            <div class="card">
                <div class="card-header"><h2>Palavras-Chave</h2></div>
                <div class="card-body">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Palavra-Chave Principal</label>
                            <input type="text" class="input" id="genKeyword" value="marketing digital politico">
                        </div>
                        <div class="form-group">
                            <label>Palavras-Chave Secundarias</label>
                            <input type="text" class="input" id="genSecondaryKw" value="eleicoes 2026, campanhas eleitorais, otimizacao de campanhas eleitorais online, engajar jovens eleitores na internet">
                            <small class="form-help">Separadas por virgula</small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Imagens -->
            <div class="card">
                <div class="card-header"><h2>Imagens do Artigo</h2></div>
                <div class="card-body">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Quantidade de Imagens</label>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <input type="number" class="input" id="genMinImages" value="1" min="0" max="5" style="flex:1;">
                                <span class="text-muted">a</span>
                                <input type="number" class="input" id="genMaxImages" value="2" min="0" max="10" style="flex:1;">
                            </div>
                            <small class="form-help">Total inclui a capa. Use 0 para desativar imagens.</small>
                        </div>
                        <div class="form-group">
                            <label>Proporcao da Imagem</label>
                            <select class="input" id="genImageRatio">
                                <option value="16:9" selected>16:9 (Cover/Background)</option>
                                <option value="4:3">4:3</option>
                                <option value="1:1">1:1 (Quadrada)</option>
                            </select>
                        </div>
                        <div class="form-group form-full">
                            <label>Google API Key (Imagens)</label>
                            <input type="text" class="input" id="genGoogleApiKey" value="AIzaSyC5rz4mmdYSSu0cZGXbzm87J7eIi88aR44">
                        </div>
                        <div class="form-group form-full">
                            <label>Instrucoes de Imagem</label>
                            <textarea class="input" id="genImageInstructions" rows="2">Imagens realistas no cenario Brasileiro. Tema visual: Marketing politico no Brasil - eleicoes 2026. Visual moderno e profissional. Cover Image - Background Image.</textarea>
                        </div>
                    </div>
                    <div class="alert-info" style="margin-top: 0.8rem; padding: 0.7rem 1rem; background: rgba(37,99,235,0.1); border-radius: 8px; border-left: 3px solid var(--primary); font-size: 0.82rem;">
                        Todas as imagens serao geradas novas automaticamente. Nunca reutilizadas entre posts. Cada imagem reflete o tema do artigo.
                    </div>
                </div>
            </div>

            <!-- Estrutura e Estilo -->
            <div class="form-grid" style="grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="card">
                    <div class="card-header"><h2>Estrutura Obrigatoria</h2></div>
                    <div class="card-body" style="font-size: 0.85rem;">
                        <ul class="structure-list">
                            <li>Titulo principal otimizado para SEO</li>
                            <li>Meta Title</li>
                            <li>Meta Description (ate 155 caracteres)</li>
                            <li>Slug otimizado para SEO</li>
                            <li>Tags do artigo</li>
                            <li>Introducao</li>
                            <li>Secoes com H2</li>
                            <li>Subtopicos com H3 quando necessario</li>
                            <li>Conclusao</li>
                            <li>FAQ com acordeoes (3 a 7 perguntas)</li>
                            <li>Botoes de compartilhamento social</li>
                        </ul>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h2>Estilo de Escrita</h2></div>
                    <div class="card-body" style="font-size: 0.85rem;">
                        <ul class="structure-list">
                            <li>Linguagem clara, humana e natural</li>
                            <li>Paragrafos curtos e escanaveis</li>
                            <li>Uso de listas quando necessario</li>
                            <li>Exemplos praticos</li>
                            <li>Uso natural das palavras-chave</li>
                            <li>Texto justificado</li>
                            <li>Alternar negrito em trechos importantes</li>
                            <li>Tom de publicitario experiente</li>
                            <li>Sem textos roboticos ou formais demais</li>
                            <li>Mencionando a Empurrao Digital</li>
                        </ul>
                    </div>
                </div>
            </div>

            <!-- Template HTML -->
            <div class="card">
                <div class="card-header"><h2>Template HTML (Opcional)</h2></div>
                <div class="card-body">
                    <textarea class="input" id="genHtmlTemplate" rows="8" placeholder="<div class=&quot;ed-blog-post-body&quot;>\n  <h1>{{TITLE}}</h1>\n  {{INTRO}}\n  {{CONTENT}}\n  {{FAQ}}\n  {{SHARE}}\n</div>"></textarea>
                    <small class="form-help">
                        Use {{TITLE}}, {{INTRO}}, {{BODY}}, {{CONTENT}}, {{CONCLUSION}}, {{FAQ}}, {{SHARE}}, {{IMAGES}}, {{TAGS}}.
                        Se usar {{CONTENT}} sem outros slots, ele inclui todas as partes (intro, corpo, conclusao, FAQ, share).
                    </small>
                </div>
            </div>

            <!-- Contexto Institucional -->
            <div class="card">
                <div class="card-header"><h2>Contexto Institucional (Aprendizado Mestre)</h2></div>
                <div class="card-body">
                    <textarea class="input" id="genContext" rows="5">Somos a Empurrao Digital, uma agencia de marketing localizada em Goiania, que atende clientes em todo o Brasil. Atuamos desde 2018, com experiencia no atendimento a diversos candidatos e campanhas politicas. Desenvolvemos desde o planejamento estrategico digital ate a gestao de trafego pago, ajudando campanhas a crescerem e se posicionarem melhor no ambiente digital. Sempre que possivel, valorize a experiencia, autoridade e posicionamento da agencia, mantendo a comunicacao clara, estrategica e com linguagem proxima do publico.</textarea>
                    <small class="form-help">Este contexto sera utilizado para enriquecer todos os artigos gerados.</small>
                </div>
            </div>

            <!-- Final do Artigo -->
            <div class="card">
                <div class="card-header"><h2>Final do Artigo</h2></div>
                <div class="card-body">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>FAQ (perguntas)</label>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <input type="number" class="input" id="genFaqMin" value="3" min="0" max="10" style="flex:1;">
                                <span class="text-muted">a</span>
                                <input type="number" class="input" id="genFaqMax" value="7" min="1" max="15" style="flex:1;">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Botoes de Compartilhamento</label>
                            <div class="checkbox-group" style="flex-direction: row; flex-wrap: wrap; gap: 0.5rem;">
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="facebook" checked> Facebook</label>
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="instagram" checked> Instagram</label>
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="x" checked> X (Twitter)</label>
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="linkedin" checked> LinkedIn</label>
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="whatsapp" checked> WhatsApp</label>
                                <label class="checkbox-label"><input type="checkbox" class="share-check" value="telegram" checked> Telegram</label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Submit -->
            <div style="text-align: center; padding: 1.5rem 0;">
                <button type="submit" class="btn btn-primary btn-lg" id="genSubmit" style="padding: 1rem 3rem; font-size: 1.1rem;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                    Gerar Artigo(s)
                </button>
                <p class="text-muted" style="margin-top: 0.5rem; font-size: 0.8rem;">A geracao pode levar alguns minutos dependendo da quantidade e tamanho dos artigos.</p>
            </div>

        </form>
    `;
}

function collectGenerateConfig() {
    const audiences = [];
    document.querySelectorAll('.checkbox:checked').forEach(cb => audiences.push(cb.value));
    const tones = [];
    document.querySelectorAll('.tone-check:checked').forEach(cb => tones.push(cb.value));
    const shares = [];
    document.querySelectorAll('.share-check:checked').forEach(cb => shares.push(cb.value));
    const topics = document.getElementById('genTopics').value.split('\n').map(t => t.trim()).filter(t => t);

    return {
        count: parseInt(document.getElementById('genCount').value) || 1,
        topics: topics,
        article_type: document.getElementById('genType').value,
        primary_keyword: document.getElementById('genKeyword').value,
        secondary_keywords: document.getElementById('genSecondaryKw').value.split(',').map(k => k.trim()).filter(k => k),
        tone: tones.join(', '),
        depth: document.getElementById('genDepth').value,
        min_chars: parseInt(document.getElementById('genMinChars').value) || 3000,
        max_chars: parseInt(document.getElementById('genMaxChars').value) || 30000,
        audiences: audiences,
        google_api_key: document.getElementById('genGoogleApiKey').value,
        image_instructions: document.getElementById('genImageInstructions').value,
        min_images: parseInt(document.getElementById('genMinImages').value) || 1,
        max_images: parseInt(document.getElementById('genMaxImages').value) || 2,
        image_ratio: document.getElementById('genImageRatio').value,
        html_template: document.getElementById('genHtmlTemplate') ? document.getElementById('genHtmlTemplate').value : '',
        context: document.getElementById('genContext').value,
        faq_min: parseInt(document.getElementById('genFaqMin').value) || 3,
        faq_max: parseInt(document.getElementById('genFaqMax').value) || 7,
        share_buttons: shares,
        language: 'pt-br',
        provider: document.getElementById('genProvider') ? document.getElementById('genProvider').value : '',
        gemini_api_key: document.getElementById('genGeminiKey') ? document.getElementById('genGeminiKey').value : '',
        openai_api_key: document.getElementById('genOpenaiKey') ? document.getElementById('genOpenaiKey').value : '',
        anthropic_api_key: document.getElementById('genAnthropicKey') ? document.getElementById('genAnthropicKey').value : '',
    };
}

async function handleGenerate(e) {
    e.preventDefault();
    const btn = document.getElementById('genSubmit');
    const config = collectGenerateConfig();

    if (config.topics.length === 0) {
        showToast('Informe pelo menos um tema para os artigos.', 'error');
        return;
    }

    btn.disabled = true;
    const total = config.count;
    btn.innerHTML = `<div class="spinner spinner-sm"></div> Gerando ${total} artigo(s)...`;

    try {
        const result = await API.post('/generate/empurrao', config);
        if (result.success) {
            const generated = result.articles_generated || total;
            showToast(`${generated} artigo(s) gerado(s) com sucesso!`, 'success');
            navigate('articles');
        } else {
            showToast('Erro na geracao: ' + (result.detail || 'desconhecido'), 'error');
        }
    } catch (err) {
        showToast('Erro: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Gerar Artigo(s)`;
    }
}


// ──────────────────────────────────────────────
// Generated Articles Page
// ──────────────────────────────────────────────

async function renderArticles(el) {
    const data = await API.get('/articles?limit=100');
    const articles = data.articles || [];

    if (articles.length === 0) {
        el.innerHTML = `<div class="empty-state">
            <h3>Nenhum artigo gerado</h3>
            <p>Use o gerador para criar artigos com IA.</p>
            <button class="btn btn-primary" onclick="navigate('generate')">Gerar Primeiro Artigo</button>
        </div>`;
        return;
    }

    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Artigos Gerados por IA (${articles.length})</h2></div>
            <div class="card-body">
                <div class="table-wrapper">
                    <table class="table">
                        <thead><tr><th>Titulo</th><th>Tipo</th><th>Palavras</th><th>SEO</th><th>Provider</th><th>Custo</th><th>Acoes</th></tr></thead>
                        <tbody>
                            ${articles.map(a => `
                                <tr>
                                    <td><strong>${escapeHtml(truncate(a.title, 45))}</strong></td>
                                    <td><span class="badge">${a.article_type || '-'}</span></td>
                                    <td>${a.word_count || 0}</td>
                                    <td><span class="seo-score seo-${getSeoClass(a.seo_score)}">${a.seo_score || '-'}</span></td>
                                    <td>${a.provider || '-'}</td>
                                    <td>$${(a.cost || 0).toFixed(4)}</td>
                                    <td>
                                        <button class="btn btn-xs btn-outline" onclick="viewArticle('${a.id}')">Ver</button>
                                        <button class="btn btn-xs btn-primary" onclick="publishArticle('${a.id}')">Publicar</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}


// ──────────────────────────────────────────────
// Other Pages (Bulk, Keywords, Trends, SEO, Publish, Config)
// ──────────────────────────────────────────────

function renderBulk(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Geracao em Massa</h2></div>
            <div class="card-body">
                <form onsubmit="handleBulk(event)">
                    <div class="form-grid">
                        <div class="form-group form-full">
                            <label>Topico Base *</label>
                            <input type="text" class="input" id="bulkTopic" placeholder="Ex: Marketing Politico" required>
                        </div>
                        <div class="form-group">
                            <label>Quantidade</label>
                            <input type="number" class="input" id="bulkCount" value="10" min="2" max="500">
                        </div>
                        <div class="form-group">
                            <label>Concorrencia</label>
                            <input type="number" class="input" id="bulkConcurrent" value="5" min="1" max="20">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary btn-lg" id="bulkSubmit">Iniciar Geracao em Massa</button>
                </form>
            </div>
        </div>
    `;
}

function renderKeywords(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Pesquisa de Keywords</h2></div>
            <div class="card-body">
                <form onsubmit="handleCluster(event)">
                    <div class="form-grid">
                        <div class="form-group form-full">
                            <label>Keyword Semente *</label>
                            <input type="text" class="input" id="kwSeed" placeholder="Ex: marketing politico" required>
                        </div>
                        <div class="form-group"><label>Profundidade</label><input type="number" class="input" id="kwDepth" value="2" min="1" max="5"></div>
                        <div class="form-group"><label>Max Keywords</label><input type="number" class="input" id="kwMax" value="50" min="10" max="200"></div>
                    </div>
                    <button type="submit" class="btn btn-primary" id="kwSubmit">Gerar Cluster</button>
                </form>
                <div id="kwResults"></div>
            </div>
        </div>
    `;
}

function renderTrends(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Descoberta de Tendencias</h2></div>
            <div class="card-body">
                <form onsubmit="handleTrends(event)">
                    <div class="form-grid">
                        <div class="form-group"><label>Nicho</label><input type="text" class="input" id="trendNiche" value="marketing politico"></div>
                        <div class="form-group"><label>Regiao</label><input type="text" class="input" id="trendRegion" value="BR"></div>
                        <div class="form-group"><label>Limite</label><input type="number" class="input" id="trendLimit" value="20" min="5" max="100"></div>
                    </div>
                    <button type="submit" class="btn btn-primary" id="trendSubmit">Descobrir Tendencias</button>
                </form>
                <div id="trendResults"></div>
            </div>
        </div>
    `;
}

function renderSEO(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Analise SEO</h2></div>
            <div class="card-body">
                <p>Selecione um artigo gerado para otimizar.</p>
                <div id="seoArticleList"><div class="loading-spinner"><div class="spinner"></div></div></div>
            </div>
        </div>
    `;
    loadSEOArticles();
}

async function loadSEOArticles() {
    try {
        const data = await API.get('/articles?limit=50');
        const el = document.getElementById('seoArticleList');
        if (!data.articles.length) { el.innerHTML = '<p class="text-muted">Nenhum artigo gerado encontrado.</p>'; return; }
        el.innerHTML = data.articles.map(a => `
            <div class="list-item">
                <div><strong>${escapeHtml(truncate(a.title, 50))}</strong> <span class="badge">${a.seo_score || '?'}</span></div>
                <button class="btn btn-xs btn-primary" onclick="optimizeArticle('${a.id}')">Otimizar</button>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('seoArticleList').innerHTML = `<p>Erro: ${e.message}</p>`;
    }
}

function renderPublish(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Publicar no Odoo</h2></div>
            <div class="card-body">
                <p>Selecione um artigo gerado para publicar no blog do Odoo.</p>
                <div id="publishArticleList"><div class="loading-spinner"><div class="spinner"></div></div></div>
            </div>
        </div>
    `;
    loadPublishArticles();
}

async function loadPublishArticles() {
    try {
        const data = await API.get('/articles?limit=50');
        const el = document.getElementById('publishArticleList');
        if (!data.articles.length) { el.innerHTML = '<p class="text-muted">Nenhum artigo gerado encontrado.</p>'; return; }
        el.innerHTML = data.articles.map(a => `
            <div class="list-item">
                <div><strong>${escapeHtml(truncate(a.title, 50))}</strong> <span class="text-muted">${a.word_count} palavras</span></div>
                <div>
                    <button class="btn btn-xs btn-outline" onclick="publishArticle('${a.id}', true)">Dry Run</button>
                    <button class="btn btn-xs btn-primary" onclick="publishArticle('${a.id}', false)">Publicar</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('publishArticleList').innerHTML = `<p>Erro: ${e.message}</p>`;
    }
}

async function renderConfig(el) {
    const config = await API.get('/config');
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h2>Configuracoes do Sistema</h2></div>
            <div class="card-body">
                <div class="info-grid">
                    <div class="info-item"><span class="info-label">Odoo URL</span><span class="info-value">${config.odoo_url || 'Nao configurado'}</span></div>
                    <div class="info-item"><span class="info-label">Odoo DB</span><span class="info-value">${config.odoo_db || '-'}</span></div>
                    <div class="info-item"><span class="info-label">Odoo Status</span><span class="info-value">${config.odoo_configured ? '<span class="badge badge-success">Configurado</span>' : '<span class="badge badge-danger">Nao Configurado</span>'}</span></div>
                    <div class="info-item"><span class="info-label">Provider LLM</span><span class="info-value">${config.default_provider}</span></div>
                    <div class="info-item"><span class="info-label">OpenAI</span><span class="info-value">${config.openai_configured ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-warning">Sem API Key</span>'}</span></div>
                    <div class="info-item"><span class="info-label">Gemini</span><span class="info-value">${config.gemini_configured ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-warning">Sem API Key</span>'}</span></div>
                    <div class="info-item"><span class="info-label">Idioma</span><span class="info-value">${config.default_language}</span></div>
                    <div class="info-item"><span class="info-label">Tom</span><span class="info-value">${config.default_tone}</span></div>
                    <div class="info-item"><span class="info-label">Profundidade</span><span class="info-value">${config.default_depth}</span></div>
                    <div class="info-item"><span class="info-label">Min Palavras</span><span class="info-value">${config.min_words}</span></div>
                    <div class="info-item"><span class="info-label">Max Palavras</span><span class="info-value">${config.max_words}</span></div>
                    <div class="info-item"><span class="info-label">Artigos/Dia</span><span class="info-value">${config.articles_per_day}</span></div>
                    <div class="info-item"><span class="info-label">Imagens</span><span class="info-value">${config.image_provider}</span></div>
                </div>
            </div>
        </div>
    `;
}


// ──────────────────────────────────────────────
// Action Handlers
// ──────────────────────────────────────────────

async function syncOdoo() {
    const btn = document.getElementById('syncBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner spinner-sm"></div> Sincronizando...';

    try {
        const result = await API.post('/odoo/sync');
        showToast(`Sincronizado! ${result.total_posts} posts, ${result.total_tags} tags`, 'success');
        navigate(currentPage);  // Refresh
    } catch (e) {
        showToast('Erro na sincronizacao: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23,4 23,10 17,10"/><polyline points="1,20 1,14 7,14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Sync Odoo';
    }
}

async function viewArticle(id) {
    try {
        const data = await API.get(`/articles/${id}`);
        openModal(escapeHtml(data.title || 'Artigo'), `
            <div class="info-grid" style="margin-bottom: 1rem">
                <div class="info-item"><span class="info-label">Palavras</span><span class="info-value">${data.metadata?.word_count || 0}</span></div>
                <div class="info-item"><span class="info-label">SEO</span><span class="info-value">${data.metadata?.seo_score || '-'}</span></div>
                <div class="info-item"><span class="info-label">Provider</span><span class="info-value">${data.metadata?.llm_provider || '-'}</span></div>
            </div>
            ${data.content_html_full ? `<iframe srcdoc="${escapeHtml(data.content_html_full)}" style="width: 100%; height: 60vh; border: 1px solid var(--border); border-radius: 8px; background: white;"></iframe>` : '<p>Sem conteudo HTML.</p>'}
        `, 'modal-lg');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    }
}

async function publishArticle(id, dryRun = false) {
    try {
        showToast('Publicando...', 'info');
        const result = await API.post('/publish', { article_id: id, dry_run: dryRun });
        showToast(dryRun ? `Dry run OK (ID: ${result.odoo_post_id})` : `Publicado no Odoo! ID: ${result.odoo_post_id}`, 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    }
}

async function optimizeArticle(id) {
    try {
        showToast('Otimizando SEO...', 'info');
        const result = await API.post(`/optimize/${id}`);
        showToast(`SEO Score: ${result.seo_score} (${result.grade})`, 'success');
        navigate('seo');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    }
}

async function handleBulk(e) {
    e.preventDefault();
    const btn = document.getElementById('bulkSubmit');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner spinner-sm"></div> Gerando...';
    try {
        const result = await API.post('/generate/bulk', {
            topic: document.getElementById('bulkTopic').value,
            count: parseInt(document.getElementById('bulkCount').value),
            concurrent: parseInt(document.getElementById('bulkConcurrent').value),
        });
        showToast('Geracao em massa concluida!', 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Iniciar Geracao em Massa';
    }
}

async function handleCluster(e) {
    e.preventDefault();
    const btn = document.getElementById('kwSubmit');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner spinner-sm"></div> Gerando...';
    try {
        const result = await API.post('/keywords/cluster', {
            seed: document.getElementById('kwSeed').value,
            depth: parseInt(document.getElementById('kwDepth').value),
            max_keywords: parseInt(document.getElementById('kwMax').value),
        });
        document.getElementById('kwResults').innerHTML = `
            <div class="section-title" style="margin-top: 1.5rem">Resultados: ${result.total_keywords} keywords</div>
            ${result.clusters.map(c => `
                <div class="card" style="margin-bottom: 0.5rem">
                    <div class="card-header"><h3>${c.intent} (${c.keyword_count})</h3></div>
                    <div class="card-body"><div class="tags-list">${c.keywords.map(k => `<span class="badge">${escapeHtml(k.keyword)}</span>`).join(' ')}</div></div>
                </div>
            `).join('')}
        `;
        showToast(`${result.total_keywords} keywords encontradas!`, 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Gerar Cluster';
    }
}

// ──────────────────────────────────────────────
// HTML Examples Page
// ──────────────────────────────────────────────

async function renderExamples(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2>Exemplos de Conteudo (HTML)</h2>
                <div class="topbar-actions">
                    <input type="file" id="exampleFile" accept=".html" style="display: none" onchange="uploadExample(this)">
                    <button class="btn btn-primary btn-sm" onclick="document.getElementById('exampleFile').click()">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        Upload HTML
                    </button>
                </div>
            </div>
            <div class="card-body">
                <p class="text-muted" style="margin-bottom: 1.5rem;">
                    Faca upload de artigos em HTML para que a IA aprenda o seu estilo de escrita e formatacao. 
                    Note: Serão usados os 3 exemplos mais recentes no prompt.
                </p>
                <div id="examplesList">
                    <div class="loading-spinner"><div class="spinner"></div> Carregando...</div>
                </div>
            </div>
        </div>
    `;

    loadExamplesList();
}

async function loadExamplesList() {
    const el = document.getElementById('examplesList');
    if (!el) return;

    try {
        const data = await API.get('/examples');
        if (!data.examples || data.examples.length === 0) {
            el.innerHTML = `<div class="empty-state">
                <p>Nenhum exemplo carregado ainda.</p>
            </div>`;
            return;
        }

        el.innerHTML = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Nome do Arquivo</th>
                            <th>Tamanho</th>
                            <th>Carregado em</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.examples.map(ex => `
                            <tr>
                                <td><strong>${ex.name}</strong></td>
                                <td>${(ex.size / 1024).toFixed(1)} KB</td>
                                <td><span class="text-muted">${formatDate(ex.created_at)}</span></td>
                                <td>
                                    <button class="btn btn-xs btn-outline btn-danger" onclick="deleteExample('${ex.name}')">Excluir</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="empty-state"><p>Erro ao carregar: ${e.message}</p></div>`;
    }
}

async function uploadExample(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    
    const formData = new FormData();
    formData.append('file', file);

    showToast('Enviando arquivo...', 'info');

    try {
        const res = await fetch('/api/examples/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error('Falha no upload');
        
        showToast('Arquivo carregado com sucesso!', 'success');
        loadExamplesList();
    } catch (e) {
        showToast('Erro no upload: ' + e.message, 'error');
    } finally {
        input.value = '';
    }
}

async function deleteExample(filename) {
    if (!confirm(`Deseja excluir o exemplo "${filename}"?`)) return;

    try {
        await API.del(`/examples/${filename}`);
        showToast('Exemplo excluido.', 'success');
        loadExamplesList();
    } catch (e) {
        showToast('Erro ao excluir: ' + e.message, 'error');
    }
}

// ──────────────────────────────────────────────
// HTML Templates Page
// ──────────────────────────────────────────────

async function renderTemplates(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2>Gerenciador de Templates HTML</h2>
            </div>
            <div class="card-body">
                <p class="text-muted" style="margin-bottom: 1.5rem;">
                    Faça o upload de um arquivo HTML como template estrutural principal. Você pode selecionar de forma opcional as imagens que acompanham este HTML.
                </p>
                <div class="form-group" style="display: flex; gap: 1rem; align-items: flex-end; flex-wrap: wrap; background: rgba(0,0,0,0.02); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">
                    <div>
                        <label>Arquivo HTML (Obrigatório)</label>
                        <input type="file" id="templateFile" accept=".html,.htm" class="form-control" style="max-width: 250px;">
                    </div>
                    <div>
                        <label>Imagens (Opcional)</label>
                        <input type="file" id="templateImageFiles" accept="image/*" multiple class="form-control" style="max-width: 250px;">
                    </div>
                    <button class="btn btn-primary" onclick="uploadTemplate()">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 5px;"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        Efetuar Upload
                    </button>
                </div>
                <hr style="margin: 2rem 0;">
                <div id="templatesList">
                    <div class="loading-spinner"><div class="spinner"></div> Carregando...</div>
                </div>
            </div>
        </div>
        
        <!-- Active Template Preview -->
        <div class="card" style="margin-top: 2rem;">
            <div class="card-header">
                <h2>Template Atualmente Ativo</h2>
            </div>
            <div class="card-body" id="activeTemplatePreview">
                <div class="loading-spinner"><div class="spinner"></div> Carregando preview...</div>
            </div>
        </div>
    `;

    loadTemplatesList();
    loadActiveTemplatePreview();
}

async function loadTemplatesList() {
    const el = document.getElementById('templatesList');
    if (!el) return;

    try {
        const data = await API.get('/templates');
        if (!data.templates || data.templates.length === 0) {
            el.innerHTML = `<div class="empty-state">
                <p>Nenhum template cadastrado.</p>
            </div>`;
            return;
        }

        const activeName = data.active_template;

        el.innerHTML = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Nome do Template</th>
                            <th>Status Ativo</th>
                            <th>Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.templates.map(t => {
                            const isActive = (t.name === activeName);
                            return `
                                <tr style="${isActive ? 'background-color: rgba(16, 185, 129, 0.05);' : ''}">
                                    <td><strong>${escapeHtml(t.name)}</strong></td>
                                    <td>
                                        ${isActive 
                                            ? '<span class="badge badge-success">Ativo</span>'
                                            : '<span class="badge badge-warning">Inativo</span>'}
                                    </td>
                                    <td>
                                        ${!isActive ? `<button class="btn btn-xs btn-outline btn-success" onclick="activateTemplate('${t.name}')">Definir como Ativo</button>` : ''}
                                        <button class="btn btn-xs btn-outline btn-danger" onclick="deleteTemplate('${t.name}')">Excluir</button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="empty-state"><p>Erro ao carregar: ${e.message}</p></div>`;
    }
}

async function loadActiveTemplatePreview() {
    const previewEl = document.getElementById('activeTemplatePreview');
    if (!previewEl) return;
    
    try {
        const activeData = await API.get('/template/active');
        if (!activeData.active_template) {
            previewEl.innerHTML = `<div class="empty-state"><p>Nenhum template ativo no momento.</p></div>`;
            return;
        }
        
        let htmlPreview = escapeHtml(activeData.template_content);
        // Truncate preview if it's too large
        if (htmlPreview.length > 500) {
            htmlPreview = htmlPreview.substring(0, 500) + '...';
        }

        previewEl.innerHTML = `
            <div class="info-grid" style="margin-bottom: 1rem;">
                <div class="info-item"><span class="info-label">Template</span><span class="info-value"><strong>${escapeHtml(activeData.active_template)}</strong></span></div>
                <div class="info-item"><span class="info-label">Imagens Locais</span><span class="info-value">${activeData.images_count || 0}</span></div>
            </div>
            <div>
                <strong>Preview do HTML:</strong>
                <pre style="background: var(--bg); padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85em; margin-top: 0.5rem; max-height: 200px; overflow-y: auto;"><code>${htmlPreview}</code></pre>
            </div>
        `;
    } catch(e) {
        if(e.message.includes('Nenhum template ativo') || e.message.includes('404')) {
            previewEl.innerHTML = `<div class="empty-state"><p>Nenhum template ativo no momento.</p></div>`;
        } else {
            previewEl.innerHTML = `<div class="empty-state"><p>Status indefinido.</p></div>`;
        }
    }
}

async function uploadTemplate() {
    const htmlInput = document.getElementById('templateFile');
    const imgInput = document.getElementById('templateImageFiles');
    
    if (!htmlInput.files || htmlInput.files.length === 0) {
        showToast('Por favor, selecione um arquivo HTML primeiro.', 'error');
        htmlInput.value = '';
        imgInput.value = '';
        return;
    }
    
    const htmlFile = htmlInput.files[0];
    const formData = new FormData();
    
    // The python backend expects: html_file, images, name, set_active
    formData.append('html_file', htmlFile);
    formData.append('name', htmlFile.name.replace('.html', '').replace('.htm', ''));
    formData.append('set_active', 'true');
    
    // Check for images
    if (imgInput.files && imgInput.files.length > 0) {
        for(let i=0; i < imgInput.files.length; i++){
            formData.append('images', imgInput.files[i]);
        }
    } else {
        // Send a dummy empty blob as images to bypass FastAPI 422 "Field required" if images list is completely absent
        formData.append('images', new Blob([]), '');
    }

    showToast('Enviando template e imagens...', 'info');

    try {
        const res = await fetch('/api/template/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Falha no upload');
        }
        
        showToast('Template carregado e ativado com sucesso!', 'success');
        loadTemplatesList();
        loadActiveTemplatePreview();
    } catch (e) {
        showToast('Erro no upload: ' + e.message, 'error');
    } finally {
        htmlInput.value = '';
        imgInput.value = '';
    }
}

async function activateTemplate(name) {
    try {
        await API.post(`/template/activate/${name}`);
        showToast('Template ativado com sucesso!', 'success');
        loadTemplatesList();
        loadActiveTemplatePreview();
    } catch (e) {
        showToast('Erro ao ativar: ' + e.message, 'error');
    }
}

async function deleteTemplate(name) {
    if (!confirm(`Deseja excluir o template "${name}"? Todo o diretório HTML e imagens associadas será apagado.`)) return;

    try {
        await API.del(`/template/${name}`);
        showToast('Template excluido.', 'success');
        loadTemplatesList();
        loadActiveTemplatePreview();
    } catch (e) {
        showToast('Erro ao excluir: ' + e.message, 'error');
    }
}

async function handleTrends(e) {
    e.preventDefault();
    const btn = document.getElementById('trendSubmit');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner spinner-sm"></div> Buscando...';
    try {
        const result = await API.post('/trends', {
            niche: document.getElementById('trendNiche').value,
            region: document.getElementById('trendRegion').value,
            limit: parseInt(document.getElementById('trendLimit').value),
        });
        const trends = result.trends || [];
        document.getElementById('trendResults').innerHTML = `
            <div class="section-title" style="margin-top: 1.5rem">${trends.length} Tendencias</div>
            ${trends.map(t => `
                <div class="list-item">
                    <div>
                        <strong>${escapeHtml(t.title || t.topic)}</strong>
                        <small class="text-muted">${t.source || ''} | Score: ${t.score || '-'}</small>
                    </div>
                </div>
            `).join('')}
        `;
        showToast(`${trends.length} tendencias encontradas!`, 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Descobrir Tendencias';
    }
}


// ──────────────────────────────────────────────
// UI Utilities
// ──────────────────────────────────────────────

function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${msg}</span><button onclick="this.parentElement.remove()">&times;</button>`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 5000);
}

function openModal(title, body) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = body;
    document.getElementById('modalOverlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modalOverlay').classList.remove('active');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.slice(0, len) + '...' : str;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
        return dateStr;
    }
}

function getSeoClass(score) {
    if (!score) return 'na';
    if (score >= 80) return 'high';
    if (score >= 60) return 'medium';
    return 'low';
}


// ──────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            if (page) navigate(page);
        });
    });

    // Check status
    API.get('/odoo/status').then(data => {
        const badge = document.getElementById('statusBadge');
        const text = document.getElementById('statusText');
        if (data.connected && data.synced) {
            badge.classList.add('status-online');
            text.textContent = `Odoo Conectado (${data.total_posts} posts)`;
        } else if (data.connected) {
            badge.classList.add('status-online');
            text.textContent = 'Conectado - Sync Pendente';
        } else {
            badge.classList.add('status-offline');
            text.textContent = 'Nao Conectado';
        }
    }).catch(() => {
        document.getElementById('statusText').textContent = 'Offline';
    });

    // Modal close on backdrop
    document.getElementById('modalOverlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });

    // Render initial page
    navigate('dashboard');
});
