# RELATORIO: MAPEAMENTO COMPLETO DO DIRETORIO plugin-codex/examples/

**Data da analise:** 2026-05-22
**Objetivo:** Inventario, arquitetura, diagnostico de desatualizacoes e recomendacoes
**Escopo:** plugin-codex/examples/ vs plataforma v24-v28
**Modo:** Somente leitura - nenhum arquivo foi modificado

---

## 1. INVENTARIO COMPLETO (16 arquivos, 3 suites)

### codex-advanced-suite (8 arquivos)
| Arquivo | Linhas | Observacao |
|---|---|---|
| index.html | 28 | DUPLICATA de overview.html - nao no manifesto |
| overview.html | 28 | Dashboard executivo |
| sales.html | 28 | Vendas: funil, dispersao, calor |
| operations.html | 28 | Operacoes: Workfront, capacidade, risco |
| forms.html | 28 | Planner cenario + localStorage |
| assets/app.css | 677 | ~11KB - Design tokens oklch, responsive |
| assets/app.js | 710 | ~29KB - ECharts, forms, localStorage |
| rejoinbi-app.json | 54 | Manifesto: 4 paginas, static, replace_pages=true |

### codex-echarts-dashboard (2 arquivos)
| Arquivo | Linhas | Observacao |
|---|---|---|
| index.html | 451 | ~13.6KB - Inline CSS+JS, ECharts dashboard |
| README.md | 8 | SEM manifesto, path obsoleto |

### codex-rls-suite (6 arquivos)
| Arquivo | Linhas | Observacao |
|---|---|---|
| visao-rls.html | 82 | Dashboard telecom com status RLS |
| assets/rls-suite.js | 146 | Fetch config, filtragem client-side |
| assets/rls-suite.css | 194 | Dark theme oklch |
| rejoinbi-app.json | 25 | Manifesto: 1 pagina rls=true |
| data/atendimentos.json | 9 | 8 registros de dados |
| plataformarj/rls.json | 10 | Config RLS: pagina->usuario/rls |

---

## 2. ARQUITETURA E FLUXOS

### 2.1 Plataforma v28 (Flask)
app.py + modules/rls.py (Blueprint, url_prefix=/plataforma/api) + paginas_admin.py
Plugin: plugin-codex/scripts/rejoinbi.py | MCP: plugin-codex/mcp/src/mcp_rejoinbi/
Templates: rls.html(v7.0/v9.6), rls_tutorial_completo.html, rls_example_page.html
Static: vendor/echarts.min.js, js/rls_client_code.js, js/rls_client_filter.js, js/rls_injector.js

### 2.2 Deployment via manifesto (rejoinbi.py:6508)
load_manifest -> integrity check -> require upload-mode -> chunked upload (resumable)
-> select_app_file (static=None, file=uses selected_file) -> POST /plataforma/api/paginas
-> wait_manifest_pages_ready (verifica expect_text, injeta pagina_id via URL)

### 2.3 Fluxo RLS
ADMIN: POST /plataforma/api/rls-config -> le plataformarj/rls.json -> valida -> salva no DB
CLIENT: platform injeta rls_injector.js(v4.9) + rls_client_filter.js(v1.0) automaticamente
  -> window.RLSClient.init(pageId) -> GET /plataforma/api/rls/config?pagina_id=X
  -> Response: {active, coluna_1, coluna_n, user_email, allowed_values, rls_colunas, valores_por_coluna}
  rls_injector.js tambem intercepta fetch() e reescreve URLs via rewriteUrl() (linha 261)

### 2.4 Upload resumivel (v28)
upload_entries_chunked: SHA-256 token -> state em rejoinbi-upload-sessions/temp dir
-> resume via completed_chunks -> retry 408/409/425/429/5xx -> on_file_error: retry/skip/cancel/fail
-> max_recovery_retries=1 -> upload-skip-file endpoint
NOTA: handler 413 generico existe (app.py:4698) mas NAO shrink adaptativo. Recupera por retry.

---

## 3. LISTA PRIORIZADA: DESATUALIZADO / ERRADO / QUEBRADO

### 3.1 CRITICO

[CRIT-1] rls-suite.js:48-49 nao valida payload.status
  Se API retornar {status:error} HTTP 200, retorna {} -> todos os dados expostos sem filtro.
  Plataforma: rls_client_code.js:56 verifica status===success. RISCO DE VAZAMENTO.

[CRIT-2] advanced-suite/index.html (28 linhas) duplicata byte-identica de overview.html
  data-page=overview, title idem. NAO registrada no manifesto -> upload waste + confusao.

[CRIT-3] codex-echarts-dashboard SEM rejoinbi-app.json
  upload-folder-select nao cria paginas. Deploy manual pos-upload necessario.

[CRIT-4] rls-suite.js:29-37 nao suporta multiclumn RLS
  API retorna rls_colunas + valores_por_coluna (rls.py:4400-4401) mas applyRls() so usa coluna_n/allowed_values.
  Plataforma: rls_client_filter.js:75-82 suporta multiclumn.

### 3.2 ALTO

[ALTO-1] README.md:8 path OBSOLETO: $HOME\plugins\rejoinbi-platform\scripts\rejoinbi.py
  Atual: plugin-codex\scripts\rejoinbi.py. Workspace codex-plugin-test-20260522 nao existe.

[ALTO-2] rls-suite manifesto: startup_mode=static + selected_file (linhas 8-11)
  choose_entry_file() (rejoinbi.py:3435) retorna None para static -> selected_file IGNORADO.

[ALTO-3] ECharts via CDN em todos os HTMLs (3 suites)
  Plataforma bundle: static/vendor/echarts.min.js. Problemas: offline fail, version mismatch, dup download.

[ALTO-4] rls-suite.js:53 fetch ./data/atentimentos.json (caminho relativo)
  rls_injector.js:261 reescreve URLs fetch. Tutorial (rls_tutorial:320) proibe fetch direto de JSON.
  Padrao: /plataforma/api/dados-rls

[ALTO-5] rls-suite.js reimplementa logica RLS duplicada
  Plataforma injeta rls_client_filter.js(window.RLSClient) + rls_client_code.js(applyRLSFilter).
  rls-suite.js duplica tudo -> 2x fetches a /rls/config no mesmo browser.

### 3.3 MEDIO

[MED-1] Duplicacao de dados entre echarts-dashboard e advanced-suite
  Dados: actual=[4.2,5.1,5.8,6.4,7.5,8.7] (index.html:362 vs app.js:31)
  Fator: factorByPeriod (index.html:359 vs app.js:20)
  Channels: Organic=34,Paid=28 (index.html:436 vs app.js:37)

[MED-2] forms.html promete 3 flows (app.js:582) mas so tem 1 form (scenarioForm)

[MED-3] Inconsistencia language nos manifestos
  Advanced: language=en-US (nomes em ingles, HTML em portugues)
  RLS: sem language, page name em portugues

[MED-4] app.js (710 linhas/29KB) carregado em todas as 5 paginas - 75% nao usado por pagina

[MED-5] echarts-dashboard usa inline CSS+JS (451 linhas) - nao reutiliza assets compartilhados

[MED-6] Versao ECharts inconsistente: @5 (advanced) vs @5.5.1 (echarts+rls) vs bundled (plataforma)

[MED-7] app.css (oklch/light) e rls-suite.css (hex/dark) - sem consistencia visual

### 3.4 BAIXO

[BAIXO-1] forms.html select prioridade sem value attributes (app.js:601)
[BAIXO-2] rls-suite.js boot() catch nao destroi charts - possivel duplicacao

---

## 4. VALIDACAO DO FORMATO rejoinbi-app.json

SIM: rejoinbi-app.json e o manifesto do Rejoin BI. Validado contra:
- mcp/src/mcp_rejoinbi/manifest.py:validate_manifest()

Campos validados pelo MCP:
| Campo | Obrigatorio | Validacao |
||---|---|---|
| workspace.name | SIM | ASCII |
| upload.startup_mode | nao | static/file/command |
| pages[].id | SIM | ASCII, unico, regex ^[a-z0-9][a-z0-9_-]*$ |
| pages[].name | SIM | |
| pages[].route | SIM | ASCII, unico, sem .html, sem .. |
| pages[].file | SIM | deve existir |

Campos EXTRA (CLI aceita, MCP ignora): language, replace_pages, auto_start, exclude, icon, expect_text, rls

advanced-suite: app_root=., workspace=codex-platform-pages-20260522, 4 pages validas, expect_text OK -> PASS
rls-suite: app_root=., workspace=codex-rls-smoke-20260522, 1 page valida, rls=true -> PASS (warning: selected_file ignorado)

---

## 5. ENDPOINTS/ARQUIVOS REFERENCIADOS - VALIDACAO

| Referencia | Plataforma | Status |
||---|---|---|
| /plataforma/api/rls/config?pagina_id= | modules/rls.py:1608 | MATCH EXATO |
| plataformarj/rls.json | paginas_admin.py:5046 | MATCH (aceita id/pagina/nome) |
| static/vendor/echarts.min.js | static/ | EXISTE mas NAO referenciado pelos exemplos |
| rls_client_filter.js | static/js/ | Plataforma injeta auto; exemplo duplica logica |
| rls_client_code.js | static/js/ | Referencia no tutorial; exemplo duplica |
| upload-folder-select | rejoinbi.py:3527 | COMANDO EXISTE; README path obsoleto | --operation-scope upload

---

## 6. RECOMENDACOES CONCRETAS

### Prioridade ALTA
1. [CRIT-1] rls-suite.js:47: adicionar check payload.status !== success -> throw
2. [CRIT-2] Remover index.html do advanced-suite ou tornar landing page real
3. [CRIT-3] Adicionar rejoinbi-app.json ao codex-echarts-dashboard com 1 pagina
4. [CRIT-4] rls-suite.js:29-37: adicionar support multiclumn via rls_colunas+valores_por_coluna
5. [ALTO-1] README.md: atualizar path para plugin-codex/scripts/rejoinbi.py
6. [ALTO-2] rls-suite manifesto: mudar startup_mode para file ou remover selected_file
7. [ALTO-3] Substituir CDN ECharts por /static/vendor/echarts.min.js em todos os HTMLs
8. [ALTO-4] rls-suite.js: usar /plataforma/api/dados-rls em vez de fetch relativo

### Prioridade MEDIA
9. [MED-1] Extrair dados compartilhados entre suites (data.js ou config.json)
10. [MED-2] Completar forms.html com lead/risk forms ou corrigir metric card
11. [MED-3] Adicionar language=pt-BR ao rls-suite manifesto
12. [MED-4] Code splitting do app.js por pagina (lazy load)
13. [MED-5] rls-suite.js: usar window.RLSClient quando disponivel (fallback own fetch)
14. [MED-7] Unificar paletas de cores entre app.css e rls-suite.css

### Prioridade BAIXA
15. [BAIXO-1] Adicionar value= explicito aos <option> do forms.html
16. [BAIXO-2] rls-suite.js: destruir charts no boot() catch
17. [MED-6] Padronizar versao ECharts (@5.5.1 ou bundled)
