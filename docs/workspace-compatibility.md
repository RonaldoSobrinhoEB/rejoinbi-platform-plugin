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
- Save manifests as UTF-8 and run `validate-app` before deploy. A visible label containing `?` inside words (`Vis?o`, `Opera??es`) or mojibake (`VisÃ£o`) is a blocking error because it means the label was corrupted before reaching Gerenciar Paginas.
- When a clean `name` would generate a different technical ID, `deploy-manifest` creates the page with the technical ID and immediately updates the display name back to the clean menu label.
- Shared CSS, JavaScript, images, and fonts can live in `assets/`.

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
- Use `startup_mode: "command"` only when there is a real custom command. The platform limits this command to 500 characters.

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
```

Use `--strict` with `validate-app` when warnings should block the publish.
