# Rejoin BI Agent Operating Playbook

This playbook is written for Codex agents and users who do not know the Rejoin BI platform internals. It explains how to turn natural language into safe plugin actions.

## Core Mental Model

Rejoin BI has two sides that must not be confused:

- The Rejoin BI platform address/server is the source of truth. Workspaces, pages, users, permissions, branding, RLS, BI Studio projects, Data Engine assets, managed databases, email/WhatsApp configuration, and uploaded files live on the server.
- The local computer only holds the Codex plugin, login cookies, local dashboard source files before upload, generated backups, and test reports.

If a command changes the platform, it must use the explicit platform address such as `--tenant subdomain.rejoinbi.com.br`. Do not rely on the active cached address for writes unless the user explicitly chooses `--use-active-tenant` after checking the session.

Users, direct permissions, and permission groups are a separate identity-governance scope. A valid administrative session does not authorize this scope. Never list, inspect, create, modify, test, or delete identities because a user asked for an upload, deployment, workspace/page/BI/RLS task, generic diagnosis, inventory, smoke test, or “administração” in the broad sense. See [command-scope-map.md](command-scope-map.md) before acting in that scope.

Every remote command now has a required `--operation-scope`. The agent must identify one exact domain (`workspace`, `upload`, `deployment`, `pages`, `rls`, `bi`, `data`, `platform`, `messaging`, `ai`, `diagnostics`, `system`, or `identity`) before execution. A missing or different value is blocked before authentication/profile checks. Split multi-domain work into separately authorized steps; do not use a generic command or raw API to join domains.

## Required First Step

Before any real action, confirm a connected and allowed session:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
```

If the user has not supplied the platform address, ask only for the full address:

```text
Envie o endereço completo da plataforma no formato subdomain.rejoinbi.com.br.
```

Do not ask what they want to do, list features, or request email/password in chat before platform authentication is confirmed. The browser auth wizard handles email, password, and PIN locally.

The plugin enforces the four-level hierarchy `Administrador Principal` (tier 4) > `Master` (tier 3) > `Administrador` (tier 2) > `Usuário` (tier 1). Only the first three levels are accepted for privileged platform/upload/deployment commands; a recognized `Usuário` is never elevated by a wildcard permission. A login that succeeds without PIN is `Administrador Principal`, even if a later raw session payload says `Master`.

## Natural Language Router

Use this table before asking clarifying questions. Fetch current state whenever possible.

| User says | Meaning | First command | Write command | Required validation |
| --- | --- | --- | --- | --- |
| "o que faz", "entenda o plugin", "quais recursos tem" | Explain plugin capabilities | none after session check | none | Mention connection, workspaces, uploads, pages/routes, dashboard publishing, admin config, BI Studio/Data Engine, safe cleanup |
| "conectar", "usar plataforma", "usar endereço", host sent | Connect to the Rejoin BI platform address | `ensure` | none | Continue only after `connected/profile_allowed` |
| "qual titulo atual", "mudar titulo", "trocar nome da aba" | Platform browser title in Configuracao Plataforma | `platform-title` | `platform-title --title "..."` | Write needs explicit platform address in `--tenant`; automatic backup must be reported |
| "mudar logo", "favicon", "icone", "logo do menu" | Platform branding images | `backup-platform-branding`, `platform-config` | `set-platform-branding --logo-image-file ...` | Backup path and restore command |
| "mudar cores", "identidade visual", "tema" | Platform colors/visual identity | `colors-config`, `backup-platform-branding` | `set-platform-branding --colors-file ...` or `set-platform-config --data-file ...` | Backup path, then visual/smoke check if requested |
| "restaurar padrao" | Restore default platform colors/config | `backup-platform-branding` | `restore-platform-config-defaults --yes` | Only use platform defaults when the user clearly asks for defaults |
| "voltar como estava", "desfazer visual" | Restore previous backup | Identify backup path | `restore-platform-branding --backup ... --yes` | Always save pre-restore backup unless user says not to |
| "listar workspaces", "quais workspaces tem" | Workspace inventory | `workspaceall` | none | Summarize id, name, status, password flag, last upload |
| "o que tem nesse workspace", "listar arquivos", "pastas" | Workspace file tree | `workspace-content --workspace ...` | none | If asking page files, use `page-files` |
| "subir arquivo X na pasta Y" | Direct file upload to workspace folder | `workspaceall`, maybe `workspace-content` | `upload-files --workspace ... --files ... --folder ...` | Explicit platform address; list folder after upload |
| "subir pasta", "igual usuario subindo" | UI-like resumable folder upload | `workspaceall` | `upload-folder-select` | Send bounded chunks; select startup file/mode; poll upload status. ZIP project upload is disabled. |
| "criar workspace" | Create workspace/container | `workspaceall` | `create-workspace --name ...` | Explicit platform address; if password requested, pass workspace password locally |
| "remover workspace", "excluir workspace" | Safe workspace deletion | `delete-workspace --workspace ...` dry-run | `delete-workspace --yes --confirm-name ... --confirm-id ...` | Block if password-protected until `--workspace-password` validates; check page tree |
| "senha do workspace" | Validate/unlock protected workspace | `workspaceall` | `validate-workspace --workspace ...` or deletion with `--workspace-password` | Never delete protected workspace without platform password validation |
| "criar pagina", "rota", "menu", "pai/filho/neto" | Gerenciar Paginas | `pages --all-containers`, `page-maintenance verify-hierarchy`, `page-maintenance audit-encoding` | `create-page`, `update-page`, `set-page-order`, `delete-page` | Use clean names with accents; technical ids/routes/files ASCII |
| "dashboard", "painel", "ECharts", "criar 3 paginas" | Generate and publish dashboard package | Inspect local files/data; `validate-app` | `deploy-manifest` | One standalone HTML per Rejoin BI page; `smoke-pages` must pass |
| "publicar BI", "BI Studio" | BI Studio project work | `studio-inventory`, `bi-projects` | `publish-bi` or `bi-create-project` | Project id/uid and workspace target explicit |
| "dashboard BI Studio", "canvas profissional", "Data Engine + canvas" | Professional canvas dashboard | `studio-inventory`, inspect datasets | `bi-save-theme`, `bi-save-layout`, export/normalize/deploy | Use `examples/codex-bi-studio-canvas`; dataset completed, desktop/mobile layouts saved, smoke test passes |
| "Data Engine", "datasets", "repositorio", "conexao banco" | Data Engine work | `studio-inventory`, then project-scoped `data-engine` read | `data-engine create-*`, `terminal-command`, `execute-code` | Project id/uid required; do not run code without user intent |
| "criar/gerenciar banco", "SQLite gerenciado", "backup/token do banco" | Persistent managed database work | `managed-databases list`, then `get/schema/integrity/tokens` | `managed-databases create/update/query/download/create-token/revoke-token` | Master or Administrador Principal; use explicit tenant for writes |
| "migrar/copiar o banco deste projeto" | Move the live project SQLite into managed storage | Inspect project references; `managed-databases inspect-sqlite --source ...` | `managed-databases migrate-sqlite --source ... --name ... --yes` | Preserve source; require matching row counts, per-table content hashes, schema objects, and destination integrity |
| "carga em lote", "RPA alto volume", "envio em massa o banco", "55 mil linhas" | High-volume external writes | `managed-databases list`; create scoped token; read `/limits` | Generate client using `bulk_insert`/`statements` with keep-alive; atomic DROP→CREATE→INSERT→RENAME | Consult `docs/managed-database-external-api.md`; never one request per row; dedicated `database_id` per RPA |
| "trocar de subdominio", "qual subdominio esta ativo", "trabalhar em outro projeto", "varias plataformas" | Multi-subdomain session management | `tenants list` / `tenants current` | `tenants use <subdomain>`, `tenant <subdomain> ensure`, `tenants rm <subdomain> --yes` | Bind one subdomain per conversation; never deploy to a subdomain different from the bound one; see `docs/multi-subdomain-conversations.md` |
| "usuarios", "cadastrar usuario", "editar usuario" | Explicit user administration only | `users --operation-scope identity --identity-scope`, `sectors --operation-scope identity --identity-scope` | `create-user`, `create-user-template`, `create-users-file`, `update-user`, `set-user-password`, `delete-user` with both identity flags, `--yes`, and exact `--confirm-user` when a user already exists | Confirm that the request specifically concerns the named user area; PIN is required by default, and only an explicit `--no-pin` or a `não/sem pin` spreadsheet value disables it; registration never changes groups or permissions |
| "permissoes", "acesso pagina" | Explicit direct-permission work only | `permission-pages --permissive --operation-scope identity --identity-scope` | `set-user-permissions --operation-scope identity --identity-scope --yes --confirm-user ...`, `recalculate-permissions --operation-scope identity --identity-scope --yes --confirm-all-users RECALCULATE-ALL` | Confirm exact target/user and resulting page permissions; do not clear permissions without `--allow-empty-permissions` |
| "grupos" | Explicit permission-group work only | `groups --operation-scope identity --identity-scope` | `create-group --operation-scope identity --identity-scope --yes`; target changes also require exact `--confirm-group` and, for membership, `--confirm-user` | Confirm exact group, users, and intended access before writes |
| "anuncios", "avisos" | Internal announcements | `announcements`, `announcement-groups` | `create-announcement`, `delete-announcement` | Confirm audience/all before creating |
| "RLS" | Row-level security | `rls pages`, `rls page-config`, `rls config` | `rls set-config`, `rls create-data`, `rls delete-data` | Use JSON payload; validate page/user ids |
| "configuracao IA", "IA da pagina" | Page AI context config | `ai-config --page-id ...` | `set-ai-config`, `delete-ai-config`, `cleanup-ai-config` | Requires page id and business context |
| "auditoria", "logs" | Audit tools | `audit dashboard`, `audit logs` | `audit cleanup --yes` | Exports use `audit-export` |
| "sleep manager", "desligamento", "usuarios online" | Sleep/session automation | `sleep-manager status`, `sleep-manager users-online` | `sleep-manager set-config --data-file ... --yes` | Avoid force actions unless explicit |
| "email", "agendar email", "fila email" | Email manager | `email sessions`, `email groups`, `email history`, `email queue-status` | `email create-*`, `email broadcast --yes` | Never broadcast without explicit recipients/payload |
| "whatsapp", "agendar whatsapp", "fila whatsapp" | WhatsApp manager | `whatsapp sessions`, `whatsapp groups`, `whatsapp diagnostics`, `whatsapp queue-status` | `whatsapp create-*`, `whatsapp broadcast --yes` | Session must be ready; never broadcast without explicit recipients/payload |
| "codex keys", "chaves IA" | AI provider keys | `codex-keys stats`, `codex-keys list`, `codex-keys usage` | `codex-keys create/update/delete --yes` | Do not print secrets |
| "sistema", "cache", "runtime", "status banco" | System diagnostics | `system-admin database-status`, `system-admin runtime-readiness`, `route-map routes` | cache/route writes with `--yes` | Platform may return optional backend errors; report separately |
| "gateway", "upload capabilities", "python versions" | Upload gateway diagnostics | `upload-admin capabilities`, `python-versions`, `gateway-pairings` | gateway write actions with `--yes` | Confirm target pairing/action |
| "exportar pacote do plugin" | Share plugin | local validation | `export-package` | Never include sessions/passwords/PINs |

## Command Families

### Identity Governance (Protected)

Only enter this family when the user specifically asks about users, direct permissions, or permission groups. “Analyze everything”, “fix the platform”, “run smoke”, RLS configuration, uploads, and deployments do not enter it. Reads require `--operation-scope identity --identity-scope`; writes require those flags together with `--yes`. Resolve the target first, then repeat the server-resolved id, e-mail, or group name in the confirmation option.

```powershell
# Explicit read after an identity request.
python .\scripts\rejoinbi.py users --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py user-permissions --user pessoa@empresa.com --operation-scope identity --identity-scope

# Exact, requested direct-permission change.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions `
  --user pessoa@empresa.com --confirm-user pessoa@empresa.com `
  --permissions painel-operacional --operation-scope identity --identity-scope --yes

# Core diagnostics never include identity, messaging, IA, Data Engine, or RLS.
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin --operation-scope diagnostics
```

For an identity endpoint that has no dedicated command, `api-get` and `api-send` still require `--operation-scope identity --identity-scope` and the exact `--confirm-api-path`; `api-send` also requires `--yes`. Never use the raw command as a workaround for a confirmation rule.

### Authentication

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\scripts\rejoinbi.py status
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br connect --email user@example.com --terminal
```

Use terminal auth only for automation. Prefer browser auth for humans.

### Workspaces

```powershell
python .\scripts\rejoinbi.py workspaceall --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-workspace --name workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py workspace-content --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py page-files --workspace workspace-name --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-workspace --workspace workspace-name --name new-name --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-workspace-password --workspace workspace-name --password "..." --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-start --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-stop --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-restart --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py workspace-status --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py workspace-logs --workspace workspace-name --operation-scope workspace
python .\scripts\rejoinbi.py workspace-versions --workspace workspace-name --operation-scope workspace
```

### Uploads

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-files --workspace workspace-name --files C:\path\file.html --folder relatorios --operation-scope upload
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-folder-select --workspace workspace-name --path C:\path\app --selected-file app.py --startup-mode file --auto-start --operation-scope upload
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-folder-select --workspace workspace-name --path C:\path\app --selected-file index.html --startup-mode static --auto-start --operation-scope upload
```

After upload, list files or smoke pages. Do not assume production is ready just because upload returned success.

### Pages And Routes

```powershell
python .\scripts\rejoinbi.py pages --all-containers
python .\scripts\rejoinbi.py accessible-pages --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-page --workspace workspace-name --name "Visão Geral" --file visao-geral.html --route visao-geral --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-page --page-id page-id --name "Operações" --route operacoes --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-page-order --page-id child-id --parent parent-id --position 20 --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br resolve-page --page-ref page-id --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-maintenance verify-hierarchy --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-maintenance audit-encoding --operation-scope pages
```

Visible page names should match the user's language and may include accents. Technical page ids, routes, and filenames should stay ASCII and stable.

If a page update unexpectedly moves a child page out of its parent, immediately run `update-page --parent <parent-id>` or `set-page-order --parent <parent-id>` and re-run `page-maintenance verify-hierarchy`. Treat duplicate order or `pai null` warnings as not ready for production.
If page names or descriptions show `?` in place of accents, run `page-maintenance audit-encoding`, then fix the exact page ids with `update-page` using UTF-8 visible text and ASCII `route/file`.

### Manifest Dashboard Deployment

Always follow this sequence:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest C:\path\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest C:\path\rejoinbi-app.json --create-workspace --replace-pages --upload-mode full --operation-scope deployment
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest C:\path\rejoinbi-app.json --operation-scope pages
```

The manifest should contain one HTML file per platform page. Do not create a dashboard SPA with internal page tabs or menus. The platform menu owns page navigation.

For an existing workspace, do not silently resend the whole folder. Ask the requester whether to use full or changed-files. In changed-files mode, require the requester to confirm the exact list, then use deploy-manifest with --upload-mode changed-files and repeated --changed-file values. The plugin finalizes the resumable session and explicitly applies only those paths, replacing changed files and adding new files while leaving every other workspace file and page configuration untouched. Both modes block database/data artifacts by default because they may be older than the remote state. Do not add `--allow-database-files` or `--allow-data-files` unless the requester explicitly named the exact files and accepted that change.

### Platform Branding

```powershell
python .\scripts\rejoinbi.py platform-config --operation-scope platform
python .\scripts\rejoinbi.py colors-config --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --title "Minha BI" --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br backup-platform-branding --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-platform-branding --browser-title "Minha BI" --logo-image-file C:\logo.png --logo-menu-image-file C:\menu.png --favicon-image-file C:\favicon.png --operation-scope platform
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br restore-platform-branding --backup C:\backup.json --yes --operation-scope platform
```

Changing title/logos/favicon/colors affects the Rejoin BI server and persists after the local computer is formatted. Backups are local files and should be preserved if rollback matters.

### Users, Groups, Permissions

Run this section only after the requester explicitly asks for the named identity area. Do not use it as part of deploy, RLS, upload, page, messaging, or generic diagnostic work. Reads require `--operation-scope identity --identity-scope`; writes require those flags with `--yes` and the exact resolved target confirmation.

```powershell
python .\scripts\rejoinbi.py users --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py sectors --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py user-presence --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py permission-pages --permissive --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py user-permissions --user user@example.com --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-user --email user@example.com --name "Nome" --perfil Administrador --setor Comercial --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-user --user user@example.com --confirm-user user@example.com --name "Novo Nome" --perfil Master --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-password --user user@example.com --confirm-user user@example.com --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions --user user@example.com --confirm-user user@example.com --permissions "workspace,paginas" --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py groups --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-group --name Comercial --permissions "workspace,paginas" --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br assign-user-group --user user@example.com --confirm-user user@example.com --group Comercial --confirm-group Comercial --operation-scope identity --identity-scope --yes
```

Standard `Usuario` should not be treated as an allowed plugin operator. Use standard users only for negative tests or dashboard access validation.

### Announcements

```powershell
python .\scripts\rejoinbi.py announcements --operation-scope messaging
# This needs explicit group-scope authorization.
python .\scripts\rejoinbi.py announcement-groups --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-announcement --title "Aviso" --message "Mensagem" --all --operation-scope messaging
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-announcement --announcement-id 1 --yes --operation-scope messaging
```

Confirm audience before creating announcements.

### RLS

```powershell
python .\scripts\rejoinbi.py rls pages --operation-scope rls
python .\scripts\rejoinbi.py rls page-info --page-id page-id --operation-scope rls
python .\scripts\rejoinbi.py rls page-config --page-id page-id --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py rls config --page-id page-id --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py rls data --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls set-config --data-file C:\rls-config.json --yes --operation-scope rls
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls set-page-mapping --data-file C:\rls-page-mapping.json --yes --operation-scope rls
python .\scripts\rejoinbi.py rls test-config --page-id page-id --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py rls-export --output C:\rls.xlsx --operation-scope rls
```

Use JSON files for complex RLS payloads. RLS is page and workspace/container scoped; always pass `container_id` when a page lives in a workspace, because the same page id/route pattern can exist in different contexts during tests. For N-cardinality tests, configure `coluna_usuario_1` as the user column, `coluna_dim_n` as the dimension column, create the user row with `rls create-data`, then add explicit allowed values with `rls create-dimension`.

End-to-end RLS smoke sequence:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-rls-suite\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\examples\codex-rls-suite\rejoinbi-app.json --create-workspace --replace-pages --operation-scope deployment
# Only when the requester explicitly asks for the identity/permission part of the RLS test.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions --user usuario@example.com --confirm-user usuario@example.com --permissions codex-rls-suite-visao --operation-scope identity --identity-scope --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls test-config --page-id codex-rls-suite-visao --container-id 12 --operation-scope rls
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-rls-suite\rejoinbi-app.json --operation-scope pages
```

For realistic user/PIN validation, perform mailbox creation, user creation, and page-permission changes only after the requester explicitly requests this identity validation. Use the generated mailbox to create a standard `Usuario` with `--operation-scope identity --identity-scope --yes`, read the welcome e-mail for the provisional password, attempt the login to trigger a PIN e-mail, then complete the login with that PIN. Standard users are not valid plugin operators; `--allow-standard` is only for this test. After login, verify `accessible-pages` contains only the granted page and `rls test-config` contains only the allowed dimension values for that e-mail.

`examples/codex-rls-suite` uses fictitious bundled JSON for smoke tests only. Never treat client-side filtering of a static JSON file as production RLS for sensitive data; production dashboards must fetch data from an endpoint that applies RLS before returning rows.

### Email And WhatsApp

```powershell
python .\scripts\rejoinbi.py email sessions --operation-scope messaging
python .\scripts\rejoinbi.py email groups --operation-scope messaging
python .\scripts\rejoinbi.py email history --limit 20 --operation-scope messaging
python .\scripts\rejoinbi.py email queue-status --operation-scope messaging
python .\scripts\rejoinbi.py email external-contacts --operation-scope messaging
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br email create-group --data-file C:\email-group.json --yes --operation-scope messaging

python .\scripts\rejoinbi.py whatsapp sessions --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp groups --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp diagnostics --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp history --limit 20 --operation-scope messaging
python .\scripts\rejoinbi.py whatsapp queue-status --operation-scope messaging
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br whatsapp create-group --data-file C:\whatsapp-group.json --yes --operation-scope messaging
```

Broadcasts and schedules can affect real recipients. Do not send messages unless the user provides explicit target, payload, and confirmation.

### BI Studio And Data Engine

```powershell
python .\scripts\rejoinbi.py studio-inventory --output C:\bi-data-inventory.json
python .\scripts\rejoinbi.py bi-projects
python .\scripts\rejoinbi.py bi-tabs --project-id "Projeto"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-create-tab --project-id "Projeto" --name "Visão 360" --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-save-layout --project-id "Projeto" --tab "Visão 360" --data-file C:\layouts\visao-360.json --yes
python .\scripts\rejoinbi.py bi-load-layout --project-id "Projeto" --tab "Visão 360"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-save-theme --project-id "Projeto" --data-file C:\layouts\tema.json --yes
python .\scripts\rejoinbi.py data-engine status
python .\scripts\rejoinbi.py data-engine db-connections --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine repository-list --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine repository-inspect-sheets --file C:\dados\telecom.xlsx
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine repository-upload --project-id "Projeto" --file C:\dados\telecom.xlsx --folder codex --selected-sheet "Visão Geral" --yes
python .\scripts\rejoinbi.py data-engine datasets-list --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine session-status --project-id "Projeto"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br publish-bi --project-id "Projeto" --workspace workspace-name
python .\scripts\rejoinbi.py bi-normalize-export --path C:\path\extracted-bi-export --remove-old
```

Project-scoped Data Engine endpoints require `--project-id`, `--project-uid`, or a JSON payload containing `project_id` or `project_uid`. The plugin can resolve known `project_uid` values through BI Studio inventory.

Data Engine repository uploads support CSV, Excel, SQLite, and other files accepted by the platform. For Excel files, run `repository-inspect-sheets` first, then pass one or more `--selected-sheet` values. The upload command blocks sensitive-looking files such as `.env`, keys, certificates, tokens, and password-named files unless `--allow-sensitive-files` is explicitly provided after manual review.

### Managed Databases

For direct database requests, act with `managed-databases` instead of returning a capability explanation. Resolve existing targets with `list`; use `schema`, `query`, `integrity`, `download`, and token actions as requested. For project migrations, identify the SQLite file actually referenced by the application, run `inspect-sqlite`, then `migrate-sqlite`. Keep the source untouched until the destination passes schema-object, row-count, content-hash, and integrity validation. Rewire application code only when requested, using a non-committed HTTPS API token rather than a network SQLite path. For high-volume external loads, use the atomic `bulk_insert` and transactional `statements` modes with a keep-alive session and the real limits from `/limits`, per `docs/managed-database-external-api.md`; never have a client send one request per row.

### Multiple Subdomains (multi-project)

The plugin stores one session per subdomain and lets a developer switch projects without losing credentials: `tenants list`, `tenants current`, `tenants use <subdomain>`, `tenants rm <subdomain> --yes`, plus per-subdomain auth (`ensure`/`connect`/`tenant <subdomain>`). Bind exactly one subdomain per conversation and keep it fixed; before any mutating or deploy command confirm the target subdomain equals the bound one. Never use `--use-active-tenant` without `tenants current` confirming the active subdomain.

Save all BI Studio/Data Engine JSON/code payloads as UTF-8. The CLI rejects strings that look like replaced accents or mojibake (`Vis?o`, `Cr?tico`, byte sequence `Vis\u00c3\u00a3o`) before they can create wrong tabs, filters, materialized datasets, or canvas labels.

Notebook and finalize payloads are strict. `save-notebook-state` expects a list of cell objects, not an object wrapper. `finalize-dataset` with scoped output expects `dataframe_names` items shaped like `{"dataset_id":"Dataset","name":"df_name","cell_id":"cell-id"}`. Plain `"df_name"` can fail when `require_scoped_df` is true.

#### Professional Canvas Standard

Use `examples/codex-bi-studio-canvas` before creating any BI Studio dashboard. A professional canvas starts with a decision model, not with random widgets:

- Define audience, business questions, metric grain, dimensions, and derived metrics.
- Complete the Data Engine dataset first; every KPI, chart, table, and filter should bind to a known dataframe and field.
- Work like a data specialist: define grain, joins, denominators, source-of-truth fields, refresh assumptions, trend windows, benchmark/target rules, and segment definitions before creating visuals.
- Every metric needs a formula and interpretation. If a KPI cannot explain status, trend, variance, risk, or an action, remove or replace it.
- Use visible tab/page names in the user's language with accents, such as `Visão Executiva`, but keep technical slugs, filenames, routes, dataset ids, and component ids ASCII.
- Design desktop around a stable grid such as `1600x1080`, then create a separate mobile arrangement around `430x940`.
- Use the Rejoin BI identity: dark base, blue/teal brand accents, semantic green/amber/red, 8px radius, restrained borders, and enough whitespace for scanability.
- Enforce contrast and readability: near-white primary text on dark panels, legible muted text, clear chart labels, no gray-on-dark haze, no teal-on-blue text, no red/green meaning without separation, and no text clipped by cards, buttons, tables, or KPI panels.
- Use UI hierarchy deliberately: title and executive intent first, then KPIs, diagnostic charts, ranked tables, recommendations, and filters. Keep controls compact; reserve large type for page-level messages.
- Give each tab one job: executive health, financial performance, customer retention, operations/SLA, or another explicit business question.
- Avoid generic placeholder labels, repeated card shapes without hierarchy, excessive gradients, internal menus, vanity metrics, chart junk, and charts that do not answer a question.
- Choose charts by analytical job: trend, comparison, composition, distribution, ranking, exception/risk, or relationship. Do not use decorative gauges, 3D charts, overloaded pies, or duplicate KPI values as full charts.
- After export, run `bi-normalize-export --remove-old`, remove upload-noise folders such as `venv`, create `rejoinbi-app.json` with `startup_mode: "file"` and `selected_file: "app.py"`, then deploy with platform pages mapped to ASCII routes.
- After deploy, visual QA is mandatory. Capture authenticated desktop and mobile screenshots for every page, then reject any page with BI Studio placeholders (`Indicador`, `Sem dados`, `Coluna A`, `Item 1`, generic `123`), blank charts, broken styling, console errors, horizontal mobile overflow, or a default light export. If the export renderer ignored the intended canvas, fix the package with a production-safe template/static layer or regenerate the canvas before marking it done.

For BI Studio publication, `publish-bi` now performs a post-publish workspace runtime check. It fails the command when runtime logs contain `SyntaxError`, a Python traceback, missing parquet engines (`pyarrow`/`fastparquet`), or missing materialized DataFrames. If the BI export contains parquet files, make sure `requirements.txt` includes `pyarrow>=16.0.0` or `fastparquet`.

Direct `publish-bi` also blocks BI projects whose technical tab slugs contain accents/non-ASCII characters. This prevents the platform from creating workspace files/routes such as `visão-360` or `rls-usuário` that can later confuse Gerenciar Paginas. The correct production path is: export, extract, `bi-normalize-export --remove-old`, upload normalized folder, create platform pages with accented visible names but ASCII `file/route`, then `smoke-pages`. `bi-normalize-export` also fixes known malformed BI export Python literals such as `replace('\', '/')`, and `validate-app` compiles `app.py/main.py` before deploy.

BI Studio tab display names may be localized with accents, but the exported slug, template filename, static folder, router filename, platform `arquivo`, and platform `rota` must be ASCII. If the export produced slugs such as `visão-geral` or `rls-usuário`, run `bi-normalize-export --path <extracted-export> --remove-old`, upload the normalized folder, update platform pages to ASCII `file/route`, then run `page-files`, `page-maintenance verify-hierarchy`, and `smoke-pages`.

### System, Audit, Upload Gateway, Codex Keys

```powershell
python .\scripts\rejoinbi.py audit dashboard --operation-scope diagnostics
python .\scripts\rejoinbi.py audit logs --per-page 50 --operation-scope diagnostics
python .\scripts\rejoinbi.py audit-export --output C:\auditoria.xlsx --operation-scope diagnostics
python .\scripts\rejoinbi.py sleep-manager status
python .\scripts\rejoinbi.py route-map routes --operation-scope system
python .\scripts\rejoinbi.py system-admin database-status --operation-scope system
python .\scripts\rejoinbi.py system-admin runtime-readiness --operation-scope system
python .\scripts\rejoinbi.py upload-admin capabilities --operation-scope system
python .\scripts\rejoinbi.py upload-admin gateway-pairings --operation-scope system
python .\scripts\rejoinbi.py codex-keys stats --operation-scope ai
python .\scripts\rejoinbi.py codex-keys list --operation-scope ai
python .\scripts\rejoinbi.py codex-keys usage --days 30 --limit 50 --operation-scope ai
```

Treat system errors as platform/backend diagnostics unless required checks fail.

## Safety Rules

- Never ask for platform password or PIN in chat by default. Use browser auth.
- Never run mutating commands without explicit `--tenant`.
- Never delete password-protected workspaces without validating the workspace password through the platform.
- Never delete pages/workspaces before showing the dry-run plan.
- Never broadcast email or WhatsApp without explicit recipient/payload/confirmation.
- Never print secrets from Codex keys, DB connections, tokens, cookies, passwords, or connection strings.
- Never delete or modify a project's source SQLite file during migration; remove it only in a separate explicitly requested cleanup after the migrated application has been validated.
- Never upload or export `.env`, key, token, credential, session, or backup files unless the user explicitly accepts the security risk.
- Never call a dashboard complete until `validate-app`, `deploy-manifest`, and `smoke-pages` pass.
- Never call a BI Studio canvas complete until the workspace is running and every page has `html_ok`, `browser_route_ok`, and `menu_safe` true.
- Never call a BI Studio/Data Engine dashboard professional until screenshots prove the published pages are polished on desktop and mobile, with no placeholders, no blank visuals, no console errors, and no horizontal overflow.
- Never make a dashboard with its own internal page menu when Rejoin BI pages should manage navigation.
- Never use customer platform names as generic examples. Use `subdomain.rejoinbi.com.br`.
- Never let one platform address's cached session drive writes to another platform address.

## Response Patterns

When answering a user, prefer concrete state over vague capabilities.

Good:

```text
Conectado ao endereço da plataforma. O titulo atual da plataforma e "Grupo ADN BI". Para mudar, me diga o novo titulo; vou salvar backup antes.
```

Good:

```text
Encontrei 6 workspaces. O workspace 2 tem senha, entao o plugin nao pode remove-lo sem validar a senha do workspace.
```

Bad:

```text
Qual titulo voce quer mudar?
```

Bad when already connected:

```text
O plugin pode listar workspaces, publicar dashboards e gerenciar configuracoes.
```

## Completion Checklist

Before saying a task is finished:

- Auth/session is valid and allowed.
- Platform address used for writes was explicit.
- Any backup path was reported.
- Any destructive dry-run plan was reviewed.
- Any upload/deploy was verified by listing content or smoke test.
- Any dashboard page was checked for `container_name`, `browser_route_ok`, and `menu_safe`.
- Any temporary users/workspaces/files created for tests were cleaned up.
- Any server-side limitation was separated from plugin failure.
