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
- Run `validate-app` before upload; in file startup mode it compiles `app.py` and `main.py` so syntax errors are caught before the workspace starts.
- Use `startup_mode: "command"` only when there is a real custom command. The platform limits this command to 500 characters.

## API Routes

- Use `/api/` for backend data endpoints.
- Examples: `/api/search`, `/api/users`, `/api/status`.
- Avoid frontend calls to non-API data routes such as `/search`; they can conflict with the platform proxy or page resolver.
- Keep visual page routes separate from data endpoints.

## Upload Rules

- Upload the project root folder, not a nested wrapper folder.
- Before a deploy, ask the requester to choose: resend the complete project or upload only reviewed changed files. Never infer this from “deploy”, “update”, or a local folder scan.
- The deploy-manifest command requires --upload-mode full or --upload-mode changed-files before it contacts the platform. Full mode can overwrite remote files that have the same paths; changed-files mode sends only explicit --changed-file paths and preserves every other workspace file.
- For changed-files mode, retain each file's path relative to the project root. The plugin applies only those selected paths after server finalization and never cleans the rest of the workspace. Do not include a local database or recognized data file unless the requester explicitly approves the exact file with `--allow-database-files` and/or `--allow-data-files`.
- Changed-files mode does not restart the workspace, reselect app.py, or alter pages unless the requester separately confirms --restart-after-upload or --sync-pages.
- Uploads include every selected project file, including dot-files, `.env`, `.pyc`, `__pycache__`, virtual environments, `node_modules`, archives, build output, and temporary files. The platform only reserves its own resumable-session metadata and rejects unsafe paths; database/data artifacts still require the explicit confirmation described above.
- For protected workspaces, validate the workspace password before uploading or creating pages.
- After upload, check workspace status and logs if the container is not running.

## Validation Commands

Before publishing:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
```

After publishing:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --operation-scope pages
python .\scripts\rejoinbi.py pages --workspace <workspace-name>
python .\scripts\rejoinbi.py page-maintenance verify-hierarchy --operation-scope pages
python .\scripts\rejoinbi.py page-maintenance audit-encoding --operation-scope pages
python .\scripts\rejoinbi.py page-files --workspace <workspace-name> --operation-scope pages
```

Use `--strict` with `validate-app` when warnings should block the publish.
Use `page-maintenance audit-encoding --strict` when existing page labels and descriptions must be free of mojibake or `?` replacement before considering a platform production-ready.
