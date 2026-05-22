# Rejoin BI Platform Plugin

Codex personal plugin for Rejoin BI tenants under `rejoinbi.com.br`.

## Core Rule For Dashboards

Build dashboards as standalone platform pages. Do not create an internal menu, sidebar, SPA router, or page switcher inside the dashboard app. Rejoin BI already manages page hierarchy, icon, permission, route, and menu placement in Gerenciar Paginas.

Correct pattern:

- `overview.html` registered as one page.
- `sales.html` registered as another page.
- `operations.html` registered as another page.
- Shared assets can live in `assets/`.
- The manifest maps each page to its own `file` and `route`.

See `examples/codex-advanced-suite/rejoinbi-app.json`.

Read the full Workspace compatibility guide in `docs/workspace-compatibility.md`. It captures the platform Workspace tips for static dashboards, Flask apps, `/api/` routes, startup modes, upload replacement behavior, and folder exclusions.

## Common Commands

```powershell
python .\scripts\rejoinbi.py --subdomain cliente connect --email user@example.com
python .\scripts\rejoinbi.py workspaceall
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py deploy-manifest --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --create-workspace --replace-pages
python .\scripts\rejoinbi.py smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
```

## Safe Destructive Commands

Workspace and page removal always starts as a dry-run plan. The plan includes the resolved workspace/page, parent-child-grandchild page tree, linked fictitious/hierarchy references, and verification guards.

```powershell
python .\scripts\rejoinbi.py delete-workspace --workspace codex-suite
python .\scripts\rejoinbi.py delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12

python .\scripts\rejoinbi.py delete-page --page-id codex-suite-overview
python .\scripts\rejoinbi.py delete-page --page-id codex-suite-overview --yes --confirm-page-id codex-suite-overview --cascade
```

If the plan shows pages linked from another workspace, deletion is blocked until `--allow-linked-pages` is provided. Fictitious pages cannot be deleted directly; delete the original page or workspace instead.

## Share Package

```powershell
python .\scripts\rejoinbi.py export-package
```

This creates:

- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform`
- `%USERPROFILE%\Downloads\plugin\rejoinbi-platform.zip`
- `%USERPROFILE%\Downloads\plugin\INSTALL.md`

Secrets are not included. Passwords and PINs are only read from local prompts or environment variables.
