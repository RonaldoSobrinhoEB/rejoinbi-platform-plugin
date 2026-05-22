# Rejoin BI Platform Plugin

Codex plugin for Rejoin BI tenants under `rejoinbi.com.br`.

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

See `examples/codex-advanced-suite/rejoinbi-app.json`. The advanced suite now includes executive, sales, operations, and scenario-form pages with a shared professional dashboard design system, responsive ECharts layouts, validation states, and export-ready local form records.

Read the full Workspace compatibility guide in `docs/workspace-compatibility.md`. It captures the platform Workspace tips for static dashboards, Flask apps, `/api/` routes, startup modes, upload replacement behavior, and folder exclusions.

Read `docs/page-routing-map.md` for the platform route/menu contract. It maps `accessible-pages`, `container_name`, `arquivo`, `rota`, and the `/plataforma/<container_name>/client/<route>` tunnel so generated pages do not fall back to `container_<id>`.

Read `docs/admin-configuration-map.md` for the administrative configuration map. It follows the Rejoin BI manual permission levels and maps sidebar tools such as users, permissions, groups, announcements, platform branding, AI configuration, workspace, pages, RLS, audit, system management, and BI Studio to plugin commands or authenticated API fallbacks.

Read `docs/agent-operating-playbook.md` when another Codex agent, teammate, or new user needs to understand the platform from zero. It includes the full natural-language router, command families, safety rules, response patterns, and completion checklist.

## Common Commands

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\scripts\rejoinbi.py workspaceall
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --create-workspace --replace-pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin
python .\scripts\rejoinbi.py users
python .\scripts\rejoinbi.py groups
python .\scripts\rejoinbi.py announcements
python .\scripts\rejoinbi.py platform-config
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --title "Minha BI"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br backup-platform-branding
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-platform-branding --browser-title "Minha BI" --logo-image-file .\logo.png --logo-menu-image-file .\logo-menu.png --favicon-image-file .\favicon.png
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br restore-platform-branding --backup .\platform-config.json --yes
python .\scripts\rejoinbi.py export-platform-config --output .\platform-config.json
python .\scripts\rejoinbi.py audit dashboard
python .\scripts\rejoinbi.py page-maintenance verify-hierarchy
python .\scripts\rejoinbi.py rls pages
python .\scripts\rejoinbi.py codex-keys stats
python .\scripts\rejoinbi.py studio-inventory --output .\bi-data-inventory.json
python .\scripts\rejoinbi.py data-engine status
```

`ensure` first checks whether the tenant already has a valid saved session with an allowed profile. If not, it opens a local browser login wizard. The user enters email, password, and PIN there; secrets do not need to go into chat, environment variables, or copied PowerShell snippets. The plugin saves only the resulting tenant session cookies.

The public manual defines Administrador Principal as the top level and the only login that does not request PIN. The plugin preserves that no-PIN login as `Administrador Principal` so the profile is not downgraded to `Master` by later session checks.

## Assistant Intent Shortcuts

These are the expected interpretations for Codex agents using this plugin:

- "mudar o titulo", "qual titulo atual", "trocar nome da aba": use `platform-title`; this is Configuracao Plataforma, not a workspace/dashboard title unless the user explicitly says so.
- "mudar logo", "favicon", "cores", "identidade visual": use `backup-platform-branding` and `set-platform-branding`.
- "subir arquivo em uma pasta": use `upload-files --folder`.
- "criar dashboard com paginas": create one standalone HTML file per platform page, then `validate-app`, `deploy-manifest`, and `smoke-pages`.
- "o que tem no BI Studio/Data Engine": run `studio-inventory` first.
- "remover workspace": run `delete-workspace` dry-run first; password-protected workspaces require validated workspace password before deletion.
- For everything else, use `docs/agent-operating-playbook.md` as the routing source before asking questions.

For automation-only cases, the older terminal/API flow is still available:

```powershell
$env:REJOINBI_PASSWORD = "..."
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br connect --email user@example.com --terminal
```

The `examples/codex-echarts-dashboard` folder is a polished single-page ECharts signal dashboard for quick upload and rendering checks.

## Administrative Automation

The plugin maps the slow manual configuration areas into first-class commands. Read actions run directly after `ensure`; actions that change configuration or send messages require `--yes`.

```powershell
python .\scripts\rejoinbi.py users
python .\scripts\rejoinbi.py sectors
python .\scripts\rejoinbi.py permission-pages --permissive
python .\scripts\rejoinbi.py user-presence
python .\scripts\rejoinbi.py download-users --output .\usuarios.xlsx
python .\scripts\rejoinbi.py download-permissions --output .\permissoes.xlsx

python .\scripts\rejoinbi.py menu
python .\scripts\rejoinbi.py menu-maintenance check-duplicates
python .\scripts\rejoinbi.py menu-maintenance reload

python .\scripts\rejoinbi.py page-files --workspace codex-suite
python .\scripts\rejoinbi.py page-maintenance verify-orphan-permissions
python .\scripts\rejoinbi.py page-maintenance fix-hierarchy --yes
python .\scripts\rejoinbi.py set-page-order --page-id pagina-id --parent pagina-pai --position 20

python .\scripts\rejoinbi.py rls pages
python .\scripts\rejoinbi.py rls page-config --page-id pagina-id
python .\scripts\rejoinbi.py rls set-config --data-file .\rls-config.json --yes
python .\scripts\rejoinbi.py rls-export --output .\rls.xlsx

python .\scripts\rejoinbi.py audit logs --per-page 50
python .\scripts\rejoinbi.py audit-export --output .\auditoria.xlsx
python .\scripts\rejoinbi.py sleep-manager status

python .\scripts\rejoinbi.py email sessions
python .\scripts\rejoinbi.py email create-group --data-file .\email-group.json --yes
python .\scripts\rejoinbi.py whatsapp sessions
python .\scripts\rejoinbi.py whatsapp create-group --data-file .\whatsapp-group.json --yes

python .\scripts\rejoinbi.py codex-keys list
python .\scripts\rejoinbi.py codex-keys create --data-file .\codex-key.json --yes
python .\scripts\rejoinbi.py codex-keys usage --days 30 --limit 50

python .\scripts\rejoinbi.py upload-admin capabilities
python .\scripts\rejoinbi.py upload-admin gateway-pairings
python .\scripts\rejoinbi.py route-map routes
python .\scripts\rejoinbi.py system-admin database-status

python .\scripts\rejoinbi.py studio-inventory --output .\bi-data-inventory.json
python .\scripts\rejoinbi.py studio-inventory --project-id 1 --include-raw
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin
python .\scripts\rejoinbi.py data-engine db-connections --project-id 1
python .\scripts\rejoinbi.py data-engine repository-list --project-id 1
python .\scripts\rejoinbi.py data-engine datasets-list --project-id 1
```

`smoke-admin` runs a read-only API check across the main configuration areas and writes a reusable JSON report. `studio-inventory` links BI Studio projects to Data Engine status, SQL Server driver support, sessions, database connections, repository tree, datasets, and files. It is read-only and redacts passwords, tokens, API keys, secrets, and connection strings. Data Engine repository/session/dataset commands are project-scoped; pass `--project-id`, `--project-uid`, or include `project_id/project_uid` in the JSON payload.

For e-mail, WhatsApp, RLS, sleep manager, workspace notification, Codex keys, Data Engine, and other high-variation configuration payloads, prefer `--data-file` with the same JSON shape used by the platform API. JSON files saved by Windows tools with UTF-8 BOM are accepted. That keeps the plugin compatible with new fields while still enforcing authentication, profile checks, and `--yes` on risky actions.

## Safe Destructive Commands

Workspace and page removal always starts as a dry-run plan. The plan includes the resolved workspace/page, parent-child-grandchild page tree, linked fictitious/hierarchy references, and verification guards. Destructive, upload, publish, and configuration commands require `--tenant subdomain.rejoinbi.com.br` unless you intentionally pass `--use-active-tenant`.

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12 --workspace-password "senha-do-workspace"

python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview --yes --confirm-page-id codex-suite-overview --cascade
```

If the plan shows the workspace is password-protected, deletion is blocked until the workspace password is passed through `--workspace-password` or `REJOINBI_WORKSPACE_PASSWORD` and validated by the platform. If the password is missing or invalid, no deletion is attempted and manual removal is required. If the plan shows pages linked from another workspace, deletion is blocked until `--allow-linked-pages` is provided. Fictitious pages cannot be deleted directly; delete the original page or workspace instead.

## Share Package

```powershell
python .\scripts\rejoinbi.py export-package
```

This creates:

- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform`
- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform.zip`
- `%USERPROFILE%\Downloads\plugin\INSTALL.md`

Secrets are not included. Passwords and PINs are entered in the local browser auth wizard by default, or read from local prompts/environment variables only when `--terminal` is used.
