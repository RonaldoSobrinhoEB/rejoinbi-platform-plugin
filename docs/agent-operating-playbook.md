# Rejoin BI Agent Operating Playbook

This playbook is written for Codex agents and users who do not know the Rejoin BI platform internals. It explains how to turn natural language into safe plugin actions.

## Core Mental Model

Rejoin BI has two sides that must not be confused:

- The Rejoin BI tenant/server is the source of truth. Workspaces, pages, users, permissions, branding, RLS, BI Studio projects, Data Engine assets, email/WhatsApp configuration, and uploaded files live on the server.
- The local computer only holds the Codex plugin, login cookies, local dashboard source files before upload, generated backups, and test reports.

If a command changes the tenant, it must use an explicit tenant host such as `--tenant subdomain.rejoinbi.com.br`. Do not rely on the active cached tenant for writes unless the user explicitly chooses `--use-active-tenant` after checking the session.

## Required First Step

Before any real action, confirm a connected and allowed session:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
```

If the user has not supplied a tenant, ask only for the full host:

```text
Envie o host completo no formato subdomain.rejoinbi.com.br.
```

Do not ask what they want to do, list features, or request email/password in chat before tenant authentication is confirmed. The browser auth wizard handles email, password, and PIN locally.

Allowed plugin profiles are `Administrador Principal`, `Master`, and `Administrador`. A login that succeeds without PIN is `Administrador Principal`, even if a later raw session payload says `Master`.

## Natural Language Router

Use this table before asking clarifying questions. Fetch current state whenever possible.

| User says | Meaning | First command | Write command | Required validation |
| --- | --- | --- | --- | --- |
| "o que faz", "entenda o plugin", "quais recursos tem" | Explain plugin capabilities | none after session check | none | Mention connection, workspaces, uploads, pages/routes, dashboard publishing, admin config, BI Studio/Data Engine, safe cleanup |
| "conectar", "usar tenant", host sent | Connect to tenant | `ensure` | none | Continue only after `connected/profile_allowed` |
| "qual titulo atual", "mudar titulo", "trocar nome da aba" | Platform browser title in Configuracao Plataforma | `platform-title` | `platform-title --title "..."` | Write needs explicit `--tenant`; automatic backup must be reported |
| "mudar logo", "favicon", "icone", "logo do menu" | Platform branding images | `backup-platform-branding`, `platform-config` | `set-platform-branding --logo-image-file ...` | Backup path and restore command |
| "mudar cores", "identidade visual", "tema" | Platform colors/visual identity | `colors-config`, `backup-platform-branding` | `set-platform-branding --colors-file ...` or `set-platform-config --data-file ...` | Backup path, then visual/smoke check if requested |
| "restaurar padrao" | Restore default platform colors/config | `backup-platform-branding` | `restore-platform-config-defaults --yes` | Only use platform defaults when the user clearly asks for defaults |
| "voltar como estava", "desfazer visual" | Restore previous backup | Identify backup path | `restore-platform-branding --backup ... --yes` | Always save pre-restore backup unless user says not to |
| "listar workspaces", "quais workspaces tem" | Workspace inventory | `workspaceall` | none | Summarize id, name, status, password flag, last upload |
| "o que tem nesse workspace", "listar arquivos", "pastas" | Workspace file tree | `workspace-content --workspace ...` | none | If asking page files, use `page-files` |
| "subir arquivo X na pasta Y" | Direct file upload to workspace folder | `workspaceall`, maybe `workspace-content` | `upload-files --workspace ... --files ... --folder ...` | Explicit tenant; list folder after upload |
| "subir zip", "subir pasta", "igual usuario subindo" | UI-like upload flow | `workspaceall` | `upload-zip-select` or `upload-folder-select` | Select startup file/mode; poll upload status |
| "criar workspace" | Create workspace/container | `workspaceall` | `create-workspace --name ...` | Explicit tenant; if password requested, pass workspace password locally |
| "remover workspace", "excluir workspace" | Safe workspace deletion | `delete-workspace --workspace ...` dry-run | `delete-workspace --yes --confirm-name ... --confirm-id ...` | Block if password-protected until `--workspace-password` validates; check page tree |
| "senha do workspace" | Validate/unlock protected workspace | `workspaceall` | `validate-workspace --workspace ...` or deletion with `--workspace-password` | Never delete protected workspace without platform password validation |
| "criar pagina", "rota", "menu", "pai/filho/neto" | Gerenciar Paginas | `pages --all-containers`, `page-maintenance verify-hierarchy` | `create-page`, `update-page`, `set-page-order`, `delete-page` | Use clean names with accents; technical ids/routes/files ASCII |
| "dashboard", "painel", "ECharts", "criar 3 paginas" | Generate and publish dashboard package | Inspect local files/data; `validate-app` | `deploy-manifest` | One standalone HTML per Rejoin BI page; `smoke-pages` must pass |
| "publicar BI", "BI Studio" | BI Studio project work | `studio-inventory`, `bi-projects` | `publish-bi` or `bi-create-project` | Project id/uid and workspace target explicit |
| "Data Engine", "datasets", "repositorio", "conexao banco" | Data Engine work | `studio-inventory`, then project-scoped `data-engine` read | `data-engine create-*`, `terminal-command`, `execute-code` | Project id/uid required; do not run code without user intent |
| "usuarios", "cadastrar usuario", "editar usuario" | User admin | `users`, `sectors`, `user-presence` | `create-user`, `update-user`, `set-user-password`, `delete-user` | Profiles: Administrador Principal no PIN; others require PIN |
| "permissoes", "acesso pagina" | Permissions | `permission-pages --permissive`, `user-permissions` | `set-user-permissions`, `recalculate-permissions` | Confirm target user/group and page permissions |
| "grupos" | Permission groups | `groups`, `users-for-groups` | `create-group`, `update-group`, `assign-user-group`, `delete-group` | Confirm permissions and users before writes |
| "anuncios", "avisos" | Internal announcements | `announcements`, `announcement-groups` | `create-announcement`, `delete-announcement` | Confirm audience/all before creating |
| "RLS" | Row-level security | `rls pages`, `rls page-config`, `rls config` | `rls set-config`, `rls create-data`, `rls delete-data` | Use JSON payload; validate page/user ids |
| "configuracao IA", "IA da pagina" | Page AI context config | `ai-config --page-id ...` | `set-ai-config`, `delete-ai-config`, `cleanup-ai-config` | Requires page id and business context |
| "auditoria", "logs" | Audit tools | `audit dashboard`, `audit logs` | `audit cleanup --yes` | Exports use `audit-export` |
| "sleep manager", "desligamento", "usuarios online" | Sleep/session automation | `sleep-manager status`, `sleep-manager users-online` | `sleep-manager set-config --data-file ... --yes` | Avoid force actions unless explicit |
| "email", "agendar email", "fila email" | Email manager | `email sessions`, `email groups`, `email history`, `email queue-status` | `email create-*`, `email broadcast --yes` | Never broadcast without explicit recipients/payload |
| "whatsapp", "agendar whatsapp", "fila whatsapp" | WhatsApp manager | `whatsapp sessions`, `whatsapp groups`, `whatsapp diagnostics`, `whatsapp queue-status` | `whatsapp create-*`, `whatsapp broadcast --yes` | Session must be ready; never broadcast without explicit recipients/payload |
| "codex keys", "chaves IA" | AI provider keys | `codex-keys stats`, `codex-keys list`, `codex-keys usage` | `codex-keys create/update/delete --yes` | Do not print secrets |
| "sistema", "cache", "runtime", "status banco" | System diagnostics | `system-admin database-status`, `system-admin runtime-readiness`, `route-map routes` | cache/route writes with `--yes` | Tenant may return optional backend errors; report separately |
| "gateway", "upload capabilities", "python versions" | Upload gateway diagnostics | `upload-admin capabilities`, `python-versions`, `gateway-pairings` | gateway write actions with `--yes` | Confirm target pairing/action |
| "exportar pacote do plugin" | Share plugin | local validation | `export-package` | Never include sessions/passwords/PINs |

## Command Families

### Authentication

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\scripts\rejoinbi.py status
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br connect --email user@example.com --terminal
```

Use terminal auth only for automation. Prefer browser auth for humans.

### Workspaces

```powershell
python .\scripts\rejoinbi.py workspaceall
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-workspace --name workspace-name
python .\scripts\rejoinbi.py workspace-content --workspace workspace-name
python .\scripts\rejoinbi.py page-files --workspace workspace-name
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-workspace --workspace workspace-name --name new-name
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-workspace-password --workspace workspace-name --password "..."
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-start --workspace workspace-name
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-stop --workspace workspace-name
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-restart --workspace workspace-name
python .\scripts\rejoinbi.py workspace-status --workspace workspace-name
python .\scripts\rejoinbi.py workspace-logs --workspace workspace-name
python .\scripts\rejoinbi.py workspace-versions --workspace workspace-name
```

### Uploads

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-files --workspace workspace-name --files C:\path\file.html --folder relatorios
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-folder-select --workspace workspace-name --path C:\path\app --selected-file app.py --startup-mode file --auto-start
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-zip-select --workspace workspace-name --zip C:\path\app.zip --selected-file index.html --startup-mode static --auto-start
```

After upload, list files or smoke pages. Do not assume production is ready just because upload returned success.

### Pages And Routes

```powershell
python .\scripts\rejoinbi.py pages --all-containers
python .\scripts\rejoinbi.py accessible-pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-page --workspace workspace-name --name "Visão Geral" --file visao-geral.html --route visao-geral
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-page --page-id page-id --name "Operações" --route operacoes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-page-order --page-id child-id --parent parent-id --position 20
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br resolve-page --page-ref page-id
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-maintenance verify-hierarchy
```

Visible page names should match the user's language and may include accents. Technical page ids, routes, and filenames should stay ASCII and stable.

### Manifest Dashboard Deployment

Always follow this sequence:

```powershell
python .\scripts\rejoinbi.py validate-app --manifest C:\path\rejoinbi-app.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest C:\path\rejoinbi-app.json --create-workspace --replace-pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest C:\path\rejoinbi-app.json
```

The manifest should contain one HTML file per platform page. Do not create a dashboard SPA with internal page tabs or menus. The platform menu owns page navigation.

### Platform Branding

```powershell
python .\scripts\rejoinbi.py platform-config
python .\scripts\rejoinbi.py colors-config
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --title "Minha BI"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br backup-platform-branding
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-platform-branding --browser-title "Minha BI" --logo-image-file C:\logo.png --logo-menu-image-file C:\menu.png --favicon-image-file C:\favicon.png
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br restore-platform-branding --backup C:\backup.json --yes
```

Changing title/logos/favicon/colors affects the tenant server and persists after the local computer is formatted. Backups are local files and should be preserved if rollback matters.

### Users, Groups, Permissions

```powershell
python .\scripts\rejoinbi.py users
python .\scripts\rejoinbi.py sectors
python .\scripts\rejoinbi.py user-presence
python .\scripts\rejoinbi.py permission-pages --permissive
python .\scripts\rejoinbi.py user-permissions --user user@example.com
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-user --email user@example.com --name "Nome" --perfil Administrador --setor Comercial
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br update-user --user user@example.com --name "Novo Nome" --perfil Master
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-password --user user@example.com
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions --user user@example.com --permissions "workspace,paginas"
python .\scripts\rejoinbi.py groups
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-group --name Comercial --permissions "workspace,paginas"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br assign-user-group --user user@example.com --group Comercial
```

Standard `Usuario` should not be treated as an allowed plugin operator. Use standard users only for negative tests or dashboard access validation.

### Announcements

```powershell
python .\scripts\rejoinbi.py announcements
python .\scripts\rejoinbi.py announcement-groups
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br create-announcement --title "Aviso" --message "Mensagem" --all
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-announcement --announcement-id 1 --yes
```

Confirm audience before creating announcements.

### RLS

```powershell
python .\scripts\rejoinbi.py rls pages
python .\scripts\rejoinbi.py rls page-config --page-id page-id
python .\scripts\rejoinbi.py rls config --page-id page-id
python .\scripts\rejoinbi.py rls data --page-id page-id
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br rls set-config --data-file C:\rls-config.json --yes
python .\scripts\rejoinbi.py rls-export --output C:\rls.xlsx
```

Use JSON files for complex RLS payloads.

### Email And WhatsApp

```powershell
python .\scripts\rejoinbi.py email sessions
python .\scripts\rejoinbi.py email groups
python .\scripts\rejoinbi.py email history --limit 20
python .\scripts\rejoinbi.py email queue-status
python .\scripts\rejoinbi.py email external-contacts
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br email create-group --data-file C:\email-group.json --yes

python .\scripts\rejoinbi.py whatsapp sessions
python .\scripts\rejoinbi.py whatsapp groups
python .\scripts\rejoinbi.py whatsapp diagnostics
python .\scripts\rejoinbi.py whatsapp history --limit 20
python .\scripts\rejoinbi.py whatsapp queue-status
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br whatsapp create-group --data-file C:\whatsapp-group.json --yes
```

Broadcasts and schedules can affect real recipients. Do not send messages unless the user provides explicit target, payload, and confirmation.

### BI Studio And Data Engine

```powershell
python .\scripts\rejoinbi.py studio-inventory --output C:\bi-data-inventory.json
python .\scripts\rejoinbi.py bi-projects
python .\scripts\rejoinbi.py data-engine status
python .\scripts\rejoinbi.py data-engine db-connections --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine repository-list --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine datasets-list --project-id "Projeto"
python .\scripts\rejoinbi.py data-engine session-status --project-id "Projeto"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br publish-bi --project-id "Projeto" --workspace workspace-name
```

Project-scoped Data Engine endpoints require `--project-id`, `--project-uid`, or a JSON payload containing `project_id` or `project_uid`. The plugin can resolve known `project_uid` values through BI Studio inventory.

### System, Audit, Upload Gateway, Codex Keys

```powershell
python .\scripts\rejoinbi.py audit dashboard
python .\scripts\rejoinbi.py audit logs --per-page 50
python .\scripts\rejoinbi.py audit-export --output C:\auditoria.xlsx
python .\scripts\rejoinbi.py sleep-manager status
python .\scripts\rejoinbi.py route-map routes
python .\scripts\rejoinbi.py system-admin database-status
python .\scripts\rejoinbi.py system-admin runtime-readiness
python .\scripts\rejoinbi.py upload-admin capabilities
python .\scripts\rejoinbi.py upload-admin gateway-pairings
python .\scripts\rejoinbi.py codex-keys stats
python .\scripts\rejoinbi.py codex-keys list
python .\scripts\rejoinbi.py codex-keys usage --days 30 --limit 50
```

Treat system errors as tenant/backend diagnostics unless required checks fail.

## Safety Rules

- Never ask for tenant password or PIN in chat by default. Use browser auth.
- Never run mutating commands without explicit `--tenant`.
- Never delete password-protected workspaces without validating the workspace password through the platform.
- Never delete pages/workspaces before showing the dry-run plan.
- Never broadcast email or WhatsApp without explicit recipient/payload/confirmation.
- Never print secrets from Codex keys, DB connections, tokens, cookies, passwords, or connection strings.
- Never call a dashboard complete until `validate-app`, `deploy-manifest`, and `smoke-pages` pass.
- Never make a dashboard with its own internal page menu when Rejoin BI pages should manage navigation.
- Never use customer tenant names as generic examples. Use `subdomain.rejoinbi.com.br`.
- Never let one tenant's cached session drive writes to another tenant.

## Response Patterns

When answering a user, prefer concrete state over vague capabilities.

Good:

```text
Conectado ao tenant. O titulo atual da plataforma e "Grupo ADN BI". Para mudar, me diga o novo titulo; vou salvar backup antes.
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
- Tenant used for writes was explicit.
- Any backup path was reported.
- Any destructive dry-run plan was reviewed.
- Any upload/deploy was verified by listing content or smoke test.
- Any dashboard page was checked for `container_name`, `browser_route_ok`, and `menu_safe`.
- Any temporary users/workspaces/files created for tests were cleaned up.
- Any server-side limitation was separated from plugin failure.

