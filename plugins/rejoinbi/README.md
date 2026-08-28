# Rejoin BI Plugin

Codex plugin for Rejoin BI platform environments under `rejoinbi.com.br`.

The plugin also manages persistent SQLite databases outside project workspaces through `managed-databases`. It can create visual-schema payloads for tables, views and indexes, inspect schema, query, read audit/diagnostics timelines, inspect a project's current SQLite database, reproduce tables/data/indexes/views/triggers in a new managed database, and validate counts and integrity. Remote clients use the platform HTTPS API with a scoped, rate-limited and revocable database token; they must never open the SQLite file through a network share. For high-volume RPA/agent loads, use the atomic `bulk_insert` and transactional `statements` write modes with a keep-alive session and the real limits from `/limits` — see `docs/managed-database-external-api.md`; never one request per row. Multiple subdomains (projects) can be stored and switched without losing sessions: `tenants list`, `tenants current`, `tenants use <subdomain>`, `tenants rm <subdomain> --yes` — see `docs/multi-subdomain-conversations.md`.

## Scope Isolation

Normal workspace, upload, page, dashboard, BI Studio, Data Engine, messaging, branding, RLS, and diagnostic work cannot inspect or alter users, direct permissions, or permission groups. Those identity-governance commands are disabled by default, even for an authenticated administrator.

Every remote command also has a mandatory immutable `--operation-scope`: `workspace`, `upload`, `deployment`, `pages`, `rls`, `bi`, `data`, `platform`, `messaging`, `ai`, `diagnostics`, `system`, or `identity`. The CLI rejects a missing or wrong scope before it opens an authenticated client. The agent must first identify one area, declare that exact scope, and split requests that span areas.

Only use identity commands when the requester explicitly names users, permissions, or groups and the exact purpose is clear. Identity reads require both `--operation-scope identity --identity-scope`; identity writes also require `--yes` and an exact resolved `--confirm-user` or `--confirm-group` target. `smoke-admin` is permanently limited to core diagnostics and cannot re-enable identity, messaging, AI, Data Engine, or RLS checks. Raw `api-get` and `api-send` derive the scope from known paths and require the exact `--confirm-api-path`, so they cannot bypass the separation.

See [docs/command-scope-map.md](docs/command-scope-map.md) for the complete command-by-command boundary and confirmations.

## Codex Marketplace Compatibility

This repository is a root plugin artifact, matching the structure used by Codex plugin ingestion:

- `.codex-plugin/plugin.json`
- `skills/`
- `scripts/`
- `docs/`
- `examples/`
- `assets/app-icon.svg`

Submit it as artifact type `PLUGIN`, branch `main`, with sparse path empty or `.`. Do not submit it as a marketplace wrapper. See `docs/MARKETPLACE_SUBMISSION.md` for the local validation checklist.

## Core Rule For Dashboards

Build dashboards as standalone platform pages. Do not create an internal menu, sidebar, SPA router, or page switcher inside the dashboard app. Rejoin BI already manages page hierarchy, icon, permission, route, and menu placement in Gerenciar Paginas.

Correct pattern:

- `overview.html` registered as one page.
- `sales.html` registered as another page.
- `operations.html` registered as another page.
- Shared assets can live in `assets/`.
- The manifest maps each page to its own `file` and `route`.
- Visible page names may be localized with accents. Technical values (`id`, `route`, filenames) stay ASCII; for static dashboards, `route` should usually be the HTML filename without `.html`.

See `examples/codex-advanced-suite/rejoinbi-app.json`. The advanced suite now includes executive, sales, operations, and scenario-form pages with a shared professional dashboard design system, responsive ECharts layouts, validation states, and export-ready local form records. For BI Studio canvas work, use `examples/codex-bi-studio-canvas`; it documents the professional canvas standard, Data Engine binding, Rejoin BI theme, export normalization, and Flask manifest shape for BI Studio exports. For row-level-security checks, use `examples/codex-rls-suite/rejoinbi-app.json`; it publishes a single accented menu page (`Visão RLS por Email`) with ASCII route/file values and client-side filtering from the platform config endpoint over fictitious data. Do not copy that static JSON pattern for sensitive production data; real sensitive rows must come from a server/API path that enforces RLS before returning data.

Read the full Workspace compatibility guide in `docs/workspace-compatibility.md`. It captures the platform Workspace tips for static dashboards, Flask apps, `/api/` routes, startup modes, upload replacement behavior, and the explicit upload-safety boundaries.

Read `docs/page-routing-map.md` for the platform route/menu contract. It maps `accessible-pages`, `container_name`, `arquivo`, `rota`, and the `/plataforma/<container_name>/client/<route>` tunnel so generated pages do not fall back to `container_<id>`.

Read `docs/admin-configuration-map.md` for the administrative configuration map. It follows the Rejoin BI manual permission levels and maps sidebar tools such as users, permissions, groups, announcements, platform branding, AI configuration, workspace, pages, RLS, audit, system management, and BI Studio to plugin commands or authenticated API fallbacks.

Read `docs/agent-operating-playbook.md` when another Codex agent, teammate, or new user needs to understand the platform from zero. It includes the full natural-language router, command families, safety rules, response patterns, and completion checklist.

Read `docs/command-scope-map.md` before any identity-governance work. It distinguishes ordinary platform operation from protected user, permission, and group administration.

## Common Commands

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\scripts\rejoinbi.py workspaceall --operation-scope workspace
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --create-workspace --replace-pages --operation-scope deployment
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --operation-scope pages
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin --operation-scope diagnostics
python .\scripts\rejoinbi.py announcements --operation-scope messaging
python .\scripts\rejoinbi.py platform-config --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --title "Minha BI" --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br backup-platform-branding --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-platform-branding --browser-title "Minha BI" --logo-image-file .\logo.png --logo-menu-image-file .\logo-menu.png --favicon-image-file .\favicon.png --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br restore-platform-branding --backup .\platform-config.json --yes --operation-scope platform
python .\scripts\rejoinbi.py export-platform-config --output .\platform-config.json --operation-scope platform
python .\scripts\rejoinbi.py audit dashboard --operation-scope diagnostics
python .\scripts\rejoinbi.py page-maintenance verify-hierarchy --operation-scope pages
python .\scripts\rejoinbi.py rls pages --operation-scope rls
python .\scripts\rejoinbi.py codex-keys stats --operation-scope ai
python .\scripts\rejoinbi.py studio-inventory --output .\bi-data-inventory.json --operation-scope bi
python .\scripts\rejoinbi.py data-engine status --operation-scope data
```

## Mandatory deployment choice

Before any deploy or project update, the agent must ask whether the requester wants to upload the complete project again or only reviewed changed files. It must never infer that choice from a generic deployment request.

The deploy-manifest command enforces this choice locally before it opens an authenticated client:

~~~powershell
# Complete project, only after the requester explicitly chose a full upload.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest C:\path\rejoinbi-app.json --upload-mode full --operation-scope deployment

# Incremental deployment: only these reviewed files are uploaded at their project-relative paths.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest C:\path\rejoinbi-app.json --upload-mode changed-files --changed-file static\app.js --changed-file templates\index.html --operation-scope deployment
~~~

Incremental mode preserves all unselected workspace files and page configuration, applies only the reviewed paths after finalization, does not automatically restart or reselect the app, and blocks database/data artifacts unless the requester explicitly approves the exact files through `--allow-database-files` and/or `--allow-data-files`.

## Upload resilience

`upload-folder-select` uploads a complete project in resumable bounded chunks. Its final publication is full-project mode: the platform versions/replaces the current `app/` tree with the uploaded folder, so use it only when the requester chose to resend the complete project. It accepts all selected file names and extensions, including hidden files, `.env`, `.pyc`, `__pycache__`, and archives. If a file is in use locally or still fails after retries, the default behavior is to show the diagnosis and require a decision: retry, skip only that file, or cancel the temporary session.

`upload-files` uses the same resumable flow for selected files. Use `--source-root` to preserve the project's relative folders and `--target-path source=target/path.ext` for an exact destination. This lets same-named files go to distinct workspace folders without an accidental overwrite.

```powershell
# Complete project; ZIP uploads are not supported.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-folder-select --workspace 12 --path C:\path\project --selected-file app.py --startup-mode file --operation-scope upload

# Only selected files, preserving static/ and templates/ beneath the project root.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-files --workspace 12 --files C:\path\project\static\app.js C:\path\project\templates\index.html --source-root C:\path\project --operation-scope upload
```

`ensure` first checks whether the Rejoin BI platform address already has a valid saved session with an allowed profile. If not, it opens a local browser login wizard. The user enters email, password, and PIN there; secrets do not need to go into chat, environment variables, or copied PowerShell snippets. The plugin saves only the resulting session cookies.

The enforced hierarchy is `Administrador Principal` (4) > `Master` (3) > `Administrador` (2) > `Usuário` (1). Only the first three levels may use privileged platform/upload/deployment commands; a wildcard permission cannot elevate a recognized `Usuário`. The public manual defines Administrador Principal as the top level and the only login that does not request PIN. The plugin preserves that no-PIN login as `Administrador Principal` so the profile is not downgraded to `Master` by later session checks.

## Assistant Intent Shortcuts

These are the expected interpretations for Codex agents using this plugin:

- "mudar o titulo", "qual titulo atual", "trocar nome da aba": use `platform-title`; this is Configuracao Plataforma, not a workspace/dashboard title unless the user explicitly says so.
- "mudar logo", "favicon", "cores", "identidade visual": use `backup-platform-branding` and `set-platform-branding`.
- "subir arquivo em uma pasta": use `upload-files --folder`; add `--source-root` when selected files must keep their project folders.
- "criar dashboard com paginas": create one standalone HTML file per platform page, then `validate-app`, `deploy-manifest`, and `smoke-pages`.
- "criar dashboard no BI Studio", "canvas profissional", "Data Engine + canvas": use `examples/codex-bi-studio-canvas` as the quality bar. Build the dataset first, save a professional desktop/mobile layout, export, normalize, deploy, and smoke test.
- "o que tem no BI Studio/Data Engine": run `studio-inventory` first. For BI exports with accents/parquet, run `bi-normalize-export` before uploading.
- "remover workspace": run `delete-workspace` dry-run first; password-protected workspaces require validated workspace password before deletion.
- For everything else, use `docs/agent-operating-playbook.md` as the routing source before asking questions.

For automation-only cases, the older terminal/API flow is still available:

```powershell
$env:REJOINBI_PASSWORD = "..."
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br connect --email user@example.com --terminal
```

The `examples/codex-echarts-dashboard` folder is a polished single-page ECharts signal dashboard for quick upload and rendering checks. The `examples/codex-bi-studio-canvas` folder is the BI Studio/Data Engine reference for professional canvas dashboards.

## Scoped Platform Administration

The plugin maps the slow manual configuration areas into first-class commands. Every remote command must declare its exact `--operation-scope`; actions that change configuration or send messages additionally require `--yes`. User, permission, and permission-group administration is the exception: it is unavailable without an explicit identity request, `--operation-scope identity`, and `--identity-scope`; every write also requires `--yes` plus the resolved target confirmation described in the scope map.

```powershell
# These reads are available only after an explicit identity-governance request.
python .\scripts\rejoinbi.py users --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py sectors --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py permission-pages --permissive --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py user-presence --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py download-users --output .\usuarios.xlsx --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py download-permissions --output .\permissoes.xlsx --operation-scope identity --identity-scope

python .\scripts\rejoinbi.py menu --operation-scope platform
python .\scripts\rejoinbi.py menu-maintenance check-duplicates --operation-scope platform
python .\scripts\rejoinbi.py menu-maintenance reload --operation-scope platform

python .\scripts\rejoinbi.py page-files --workspace codex-suite --operation-scope pages
python .\scripts\rejoinbi.py page-maintenance verify-orphan-permissions --operation-scope pages
python .\scripts\rejoinbi.py page-maintenance fix-hierarchy --yes --operation-scope pages
python .\scripts\rejoinbi.py set-page-order --page-id pagina-id --parent pagina-pai --position 20 --operation-scope pages

python .\scripts\rejoinbi.py rls pages --operation-scope rls
python .\scripts\rejoinbi.py rls page-config --page-id pagina-id --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py rls test-config --page-id pagina-id --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py rls set-config --data-file .\rls-config.json --yes --operation-scope rls
python .\scripts\rejoinbi.py rls set-page-mapping --data-file .\rls-page-mapping.json --yes --operation-scope rls
python .\scripts\rejoinbi.py rls-export --output .\rls.xlsx --operation-scope rls

python .\scripts\rejoinbi.py audit logs --per-page 50 --operation-scope diagnostics
python .\scripts\rejoinbi.py audit-export --output .\auditoria.xlsx --operation-scope diagnostics
python .\scripts\rejoinbi.py sleep-manager status

python .\scripts\rejoinbi.py email sessions --operation-scope messaging
python .\scripts\rejoinbi.py email create-group --data-file .\email-group.json --yes --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp sessions --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp create-group --data-file .\whatsapp-group.json --yes --operation-scope messaging

python .\scripts\rejoinbi.py codex-keys list --operation-scope ai
python .\scripts\rejoinbi.py codex-keys create --data-file .\codex-key.json --yes --operation-scope ai
python .\scripts\rejoinbi.py codex-keys usage --days 30 --limit 50 --operation-scope ai

python .\scripts\rejoinbi.py upload-admin capabilities --operation-scope system
python .\scripts\rejoinbi.py upload-admin gateway-pairings --operation-scope system
python .\scripts\rejoinbi.py route-map routes --operation-scope system
python .\scripts\rejoinbi.py system-admin database-status --operation-scope system

python .\scripts\rejoinbi.py studio-inventory --output .\bi-data-inventory.json
python .\scripts\rejoinbi.py studio-inventory --project-id 1 --include-raw
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin --operation-scope diagnostics
python .\scripts\rejoinbi.py data-engine db-connections --project-id 1
python .\scripts\rejoinbi.py data-engine repository-inspect-sheets --file .\dados.xlsx
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine repository-upload --project-id 1 --file .\dados.xlsx --folder codex --selected-sheet "Visão Geral" --yes
python .\scripts\rejoinbi.py data-engine repository-list --project-id 1
python .\scripts\rejoinbi.py data-engine datasets-list --project-id 1
python .\scripts\rejoinbi.py bi-normalize-export --path .\bi-export --remove-old
```

`smoke-admin` runs a read-only API check across the main configuration areas and writes a reusable JSON report. `studio-inventory` links BI Studio projects to Data Engine status, SQL Server driver support, sessions, database connections, repository tree, datasets, and files. It is read-only and redacts passwords, tokens, API keys, secrets, and connection strings. Data Engine repository/session/dataset commands are project-scoped; pass `--project-id`, `--project-uid`, or include `project_id/project_uid` in the JSON payload.

`bi-normalize-export` is a local safety helper for BI Studio exports. It keeps display names localized, converts technical slugs/files/static folders/routes to ASCII, and adds `pyarrow>=16.0.0` when parquet Data Engine artifacts are present. After using it, upload the normalized folder, update page `arquivo`/`rota` to the ASCII values, then run `page-files`, `page-maintenance verify-hierarchy`, and `smoke-pages`.

Professional BI Studio dashboards must not be treated as generic KPI dumps. Build a metric model first, bind Data Engine outputs, design each tab around a business question, and save both desktop and mobile canvas layouts. A finished BI Studio publication must pass `validate-app --strict`, have a running workspace, and show `html_ok`, `browser_route_ok`, and `menu_safe` for every platform page.

For e-mail, WhatsApp, RLS, sleep manager, workspace notification, Codex keys, Data Engine, and other high-variation configuration payloads, prefer `--data-file` with the same JSON shape used by the platform API. JSON files saved by Windows tools with UTF-8 BOM are accepted. That keeps the plugin compatible with new fields while still enforcing authentication, profile checks, and `--yes` on risky actions.

### RLS Smoke Workflow

Use this when changing RLS logic, page routing, permissions, or user/PIN handling:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-rls-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\examples\codex-rls-suite\rejoinbi-app.json --create-workspace --replace-pages --operation-scope deployment
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls set-config --page-id codex-rls-suite-visao --container-id 12 --data-file .\rls-config.json --yes --operation-scope rls
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls set-page-mapping --page-id codex-rls-suite-visao --container-id 12 --page-rls-id codex-rls-suite-visao --data-file .\rls-page-mapping.json --yes --operation-scope rls
# Only if the user explicitly requested this permission test.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions --user usuario@example.com --confirm-user usuario@example.com --permissions codex-rls-suite-visao --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls create-data --data-file .\rls-data.json --yes --operation-scope rls
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls create-dimension --data-file .\rls-dimension.json --yes --operation-scope rls
```

For a real standard-user test, perform the user and direct-permission steps only when the requester explicitly asks for an identity/RLS access validation. Use `--operation-scope identity --identity-scope --yes` and the resolved `--confirm-user` on each identity write. Connect only with `--allow-standard` for this negative/validation test. A correct result shows `plugin_profile_allowed: false` for the standard user, `accessible-pages` containing only the granted page, and `rls test-config` returning `allowed_values` only for that user's configured dimension values.

The RLS smoke dashboard intentionally uses fictitious local JSON so agents can verify menu, route, permission, PIN, and RLS configuration without touching real customer data. Do not use client-side filtering as the only protection for real datasets.

## Safe Destructive Commands

Workspace and page removal always starts as a dry-run plan. The plan includes the resolved workspace/page, parent-child-grandchild page tree, linked fictitious/hierarchy references, and verification guards. Destructive, upload, publish, and configuration commands require the explicit platform address with `--tenant subdomain.rejoinbi.com.br` unless you intentionally pass `--use-active-tenant`.

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12 --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12 --workspace-password "senha-do-workspace" --operation-scope workspace

python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview --yes --confirm-page-id codex-suite-overview --cascade --operation-scope pages
```

If the plan shows the workspace is password-protected, deletion is blocked until the workspace password is passed through `--workspace-password` or `REJOINBI_WORKSPACE_PASSWORD` and validated by the platform. If the password is missing or invalid, no deletion is attempted and manual removal is required. If the plan shows pages linked from another workspace, deletion is blocked until `--allow-linked-pages` is provided. Fictitious pages cannot be deleted directly; delete the original page or workspace instead.

Upload and export commands block common secret paths by default, including `.env`, private keys, token/password/credential files, local session folders, and unsafe ZIP entries. Use `--allow-sensitive-files` only after manually reviewing every file. Raw API access requires the endpoint-derived `--operation-scope` and exact `--confirm-api-path`; `api-send` also requires `--yes`, while mapped identity endpoints additionally require `--identity-scope`.

## User registration and PIN

`create-user` requires a login PIN by default. Use `--no-pin` only when the
request explicitly says that the user may log in with e-mail and password;
`--pin-required` makes the default explicit. To prepare a standard workbook,
run:

```powershell
python .\scripts\rejoinbi.py create-user-template --output .\usuarios-template.xlsx
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-users-file --file .\usuarios-preenchidos.xlsx --confirm-count 3 --operation-scope identity --identity-scope --yes
```

The XLSX columns are `email`, `nome`, `matricula`, `setor`, `contato`, `perfil`,
and `pin`. In `pin`, use `sim/obrigatório/com pin` or `não/sem pin/dispensado`;
an empty value means PIN required. Batch creation reports each row and never
changes groups or permissions as a side effect.

## Share Package

```powershell
python .\scripts\rejoinbi.py export-package
```

This creates:

- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform`
- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform.zip`
- `%USERPROFILE%\Downloads\plugin\INSTALL.md`

Secrets are not included. Passwords and PINs are entered in the local browser auth wizard by default, or read from local prompts/environment variables only when `--terminal` is used.
