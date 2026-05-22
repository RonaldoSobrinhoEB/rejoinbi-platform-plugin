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
python .\scripts\rejoinbi.py page-files --workspace <workspace-name>
```

Use `--strict` with `validate-app` when warnings should block the publish.
