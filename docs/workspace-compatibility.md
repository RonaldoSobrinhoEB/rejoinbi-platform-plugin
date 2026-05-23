# Rejoin BI Workspace Compatibility Guide

These rules come from the platform Workspace and Gerenciar Paginas behavior. Use them before creating or publishing dashboards.

## Dashboard Pages

- Build one standalone HTML file per Rejoin BI page.
- Do not add an internal menu, sidebar, tab router, or SPA route switcher to change dashboard pages.
- Let Gerenciar Paginas own page hierarchy, menu placement, icon, permissions, parent page, active status, route, and file binding.
- In the manifest, each page should have its own `id`, `name`, `route`, and `file`.
- Keep `name` clean because it is what appears in the Rejoin BI menu. Use `id` for technical prefixes such as the workspace/client slug.
- For static dashboards, prefer `route` equal to the HTML file path without `.html` so the platform route resolver, file binding, and smoke test all agree.
- Use accents in visible `name` values according to the dashboard language. For pt-BR, write `Visão Geral`, `Operações`, `Configuração`, `Métricas`, etc. Keep accents out of `id`, `route`, and filenames.
- Save manifests as UTF-8 and run `validate-app` before deploy. A visible label containing `?` inside words (`Vis?o`, `Opera??es`) or mojibake byte sequences such as `Vis\u00c3\u00a3o` is a blocking error because it means the label was corrupted before reaching Gerenciar Paginas.
- Save BI Studio/Data Engine payloads as UTF-8 as well. The plugin now applies the same text-integrity check to Data Engine JSON/code payloads and selected Excel sheet names before creating datasets, notebook cells, materialized tables, filters, or canvas labels.
- Direct BI Studio publish is blocked when technical tab slugs contain accents/non-ASCII characters. Export and normalize first so production workspace files, page `arquivo`, and page `rota` stay ASCII while the visible menu names keep accents.
- When a clean `name` would generate a different technical ID, `deploy-manifest` creates the page with the technical ID and immediately updates the display name back to the clean menu label.
- Shared CSS, JavaScript, images, and fonts can live in `assets/`.
- BI Studio tab names can contain accents for display, but published technical slugs cannot. Normalize exported BI Studio folders so `templates/`, `layouts/`, `router/`, `static/css`, `static/js`, page `arquivo`, and page `rota` use ASCII paths such as `visao-geral` and `rls-usuario`.

Good:

```text
overview.html
sales.html
operations.html
forms.html
assets/app.css
assets/app.js
rejoinbi-app.json
```

Good manifest page shape:

```json
{
  "id": "rpvs-visao-geral",
  "name": "Visão Geral",
  "route": "visao-geral",
  "file": "visao-geral.html"
}
```

Avoid visible names like `RPVS - Visão Geral`; the prefix belongs in `id`, and the visible name should be localized as `Visão Geral`.

Avoid:

```text
index.html with internal links/buttons that switch pages
client-side router for multiple platform pages
dashboard sidebar duplicating the platform menu
```

## Static HTML/ECharts Dashboards

- Use `startup_mode: "static"`.
- Include at least one `.html` file.
- Prefer relative asset links such as `./assets/app.css` and `./assets/app.js`.
- Register each dashboard file in Gerenciar Paginas or in the manifest.
- After upload, run `smoke-pages` and check screenshots in the browser.

## Flask Apps

- Use `app.py` or `main.py`, or provide `selected_file` in file startup mode.
- Put HTML templates in `templates/` and assets in `static/` when building a Flask app.
- `requirements.txt` is optional. Without it, the platform uses the fast path with available/default libraries.
- Add `requirements.txt` only when the app needs extra Python packages.
- If the app includes Data Engine parquet files under `dados/df`, add `pyarrow>=16.0.0` or `fastparquet` to `requirements.txt`. Without a parquet engine, the workspace can start but load zero materialized DataFrames.
- Run `validate-app` before upload; in file startup mode it compiles `app.py` and `main.py` so syntax errors are caught before the workspace starts.
- Use `startup_mode: "command"` only when there is a real custom command. The platform limits this command to 500 characters.

## BI Studio Export Normalization

When publishing BI Studio output through a workspace folder, normalize the extracted export before upload:

```powershell
python .\scripts\rejoinbi.py bi-export --project-id "Projeto BI" --output C:\tmp\bi.zip
Expand-Archive C:\tmp\bi.zip C:\tmp\bi-export
python .\scripts\rejoinbi.py bi-normalize-export --path C:\tmp\bi-export --remove-old
python .\scripts\rejoinbi.py validate-app --manifest C:\tmp\bi-export\rejoinbi-app.json --strict
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-folder-select --workspace workspace-name --path C:\tmp\bi-export --selected-file app.py --startup-mode file --auto-start
```

After normalization and upload, update Gerenciar Paginas so visible names keep accents, but `arquivo` and `rota` are ASCII. Example: name `Visão 360`, file `visao-geral`, route `visao-geral`.

`bi-normalize-export` also fixes known BI Studio export runtime hazards, including adding a parquet engine when needed and repairing malformed Python backslash literals such as `replace('\', '/')`.

## BI Studio Canvas Quality

BI Studio canvas dashboards should be built like production BI products, not quick visual drafts. Use `examples/codex-bi-studio-canvas` as the reference before saving layouts.

- Start with the decision model: audience, questions, dimensions, metric formulas, and required filters.
- Complete and finalize Data Engine datasets before layout work; do not bind components to missing or guessed fields.
- Treat the dashboard like a data product: define fact grain, joins, dimensions, denominators, period comparison, segment rules, outlier handling, and the business action each metric should drive.
- Build a desktop canvas around a stable grid such as `1600x1080`, then build a mobile canvas around `430x940`.
- Use Rejoin BI visual identity: dark base, blue/teal brand accents, semantic green/amber/red, 8px radius, consistent spacing, and restrained borders.
- Enforce accessible contrast. Primary text on dark surfaces should read as near-white; secondary text must remain legible; chart labels cannot sit on busy gradients; colored KPI strips/badges must keep text readable. Do not use low-contrast gray-on-dark, teal-on-blue, or red/green text without enough background separation.
- Use professional typography hierarchy: one page title, concise subtitles, KPI labels smaller than KPI values, table text dense but readable, no oversized type inside compact cards, and no text clipped by cards/buttons.
- Make every tab answer one clear question. Avoid generic tabs, duplicate KPI cards, decorative charts, and internal navigation.
- Prefer visual forms by analytical purpose: scorecards for headline state, line/bar for trend, stacked/bar list for composition, scatter/table for risk triage, heatmap only when it improves scanning. Avoid pies with many categories, 3D effects, decorative gauges, and charts that repeat the same number already shown in a KPI.
- After export, use a Flask manifest shape when files live in `templates/`: page `route` should be the ASCII app route, page `file` can point to `templates/<slug>.html`, and `allow_custom_route` should be true.
- Use an ASCII smoke marker such as `canvas-root` for BI Studio templates when dynamic or encoded titles make text comparison unreliable.
- After production upload, capture desktop and mobile screenshots in an authenticated browser. The dashboard fails QA if screenshots show raw BI Studio placeholders (`Indicador`, `Sem dados`, `Coluna A`, `Item 1`, generic `123`), blank charts, broken theme CSS, console errors, horizontal mobile overflow, or a light/default export instead of the Rejoin BI professional theme.

## API Routes

- Use `/api/` for backend data endpoints.
- Examples: `/api/search`, `/api/users`, `/api/status`.
- Avoid frontend calls to non-API data routes such as `/search`; they can conflict with the platform proxy or page resolver.
- Keep visual page routes separate from data endpoints.

## Upload Rules

- Upload the project root folder, not a nested wrapper folder.
- The upload replaces the current workspace content.
- Exclude `.git`, `venv`, `.venv`, `__pycache__`, `node_modules`, `.pytest_cache`, build folders, temporary files, and secrets.
- For protected workspaces, validate the workspace password before uploading or creating pages.
- After upload, check workspace status and logs if the container is not running.

## Validation Commands

Before publishing:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
```

After publishing:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py pages --workspace <workspace-name>
python .\scripts\rejoinbi.py page-maintenance verify-hierarchy
python .\scripts\rejoinbi.py page-maintenance audit-encoding
python .\scripts\rejoinbi.py page-files --workspace <workspace-name>
```

Use `--strict` with `validate-app` when warnings should block the publish.
Use `page-maintenance audit-encoding --strict` when existing page labels and descriptions must be free of mojibake or `?` replacement before considering a platform production-ready.
