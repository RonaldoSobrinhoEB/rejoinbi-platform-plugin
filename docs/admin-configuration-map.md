# Admin Configuration Map

This map follows the public Rejoin BI user manual and the analyzed Flask blueprints in the local platform codebase.

## Permission Levels

- Administrador Principal (tier 4): highest access level, full platform/user control, no PIN during login.
- Master (tier 3): global management and workspace visibility, requires PIN; the platform still decides which endpoints this account may use.
- Administrador (tier 2): operational management for users, groups, permissions, and granted tools, requires PIN; the platform still decides which endpoints this account may use.
- Usuario (tier 1): dashboard/report access and own account changes, requires PIN. The plugin never elevates this level to perform administrative, upload, or deployment actions.

The plugin preserves this hierarchy explicitly as `Administrador Principal > Master > Administrador > Usuário`. A wildcard permission cannot elevate a recognized lower-level profile, and identity-governance actions remain separately locked to the `identity` scope.

The plugin treats a successful login that does not request PIN as `Administrador Principal`. Saved sessions created through that no-PIN flow keep this profile hint so later `ensure` and administrative commands do not downgrade it to `Master`.

## Identity Governance Boundary

User records, departments, user-presence data, direct permissions, permission exports/pages, permission groups, and group membership are a protected identity-governance area. They are not part of a normal platform inventory, upload, deployment, workspace, page, RLS, messaging, BI, or diagnostic request.

- Every remote command requires an exact `--operation-scope`; the parser rejects a missing or mismatched domain before it connects to the platform.
- Identity reads require an explicit user/permission/group request, `--operation-scope identity`, and `--identity-scope`.
- Identity writes require both identity scope flags, `--yes`, and the resolved target repeated with `--confirm-user` or `--confirm-group`.
- An intentional empty direct-permission replacement additionally requires `--allow-empty-permissions`.
- Recalculating all user permissions additionally requires `--confirm-all-users RECALCULATE-ALL`.
- `smoke-admin` is permanently restricted to core diagnostics; it cannot inspect identity, messaging, IA, Data Engine, or RLS.
- `api-get` and `api-send` cannot bypass these rules: they derive known endpoint scopes and require exact `--confirm-api-path`.

The complete boundary, including command families and non-authorizing requests, is in [command-scope-map.md](command-scope-map.md).

## Sidebar Tools

| Manual tool | Primary API | Plugin command |
| --- | --- | --- |
| Cadastrar Usuario | `POST /plataforma/api/register` | `create-user`, `create-user-template`, `create-users-file` |
| Editar Usuarios | `GET /plataforma/api/users`, `GET /plataforma/api/setores`, `GET /plataforma/api/users-presence`, `GET /plataforma/api/download-users`, `POST /plataforma/api/update-user`, `POST /plataforma/api/change-user-password`, `POST /plataforma/api/delete-user` | `users`, `sectors`, `user-presence`, `download-users`, `update-user`, `set-user-password`, `delete-user` |
| Gerenciar Permissoes | `GET /plataforma/api/pages`, `GET /plataforma/api/permissive-pages`, `GET /plataforma/api/user-permissions/<id>`, `GET /plataforma/api/download-permissions`, `POST /plataforma/api/update-permissions`, `POST /plataforma/api/recalcular-permissoes` | `permission-pages`, `user-permissions`, `download-permissions`, `set-user-permissions`, `recalculate-permissions` |
| Gerenciar Grupos | `GET /plataforma/api/groups`, `POST /plataforma/api/create-group`, `POST /plataforma/api/update-group`, `POST /plataforma/api/delete-group`, `POST /plataforma/api/assign-user-to-group` | `groups`, `create-group`, `update-group`, `delete-group`, `assign-user-group` |
| Upload de Arquivos | `POST /plataforma/api/upload-init`, `POST /plataforma/api/upload-chunk`, `POST /plataforma/api/upload-finish`, `GET /plataforma/api/upload-finish-status`, `POST /plataforma/api/upload-apply-files`, `POST /plataforma/api/select-app-file`, `POST /plataforma/api/upload-multiple-files` | `upload-folder-select`, `upload-files` |
| Anuncios Internos | `GET /plataforma/api/anuncios/historico`, `GET /plataforma/api/anuncios/ativos`, `POST /plataforma/api/anuncios`, `DELETE /plataforma/api/anuncios/<id>` | `announcements`, `create-announcement`, `delete-announcement`, `announcement-groups` |
| Configuracao WhatsApp | `/plataforma/api/whatsapp/*` | `whatsapp sessions`, `whatsapp groups`, `whatsapp create-group`, `whatsapp broadcast`, `whatsapp schedules`, `whatsapp pause-schedule`, `whatsapp resume-schedule`, `whatsapp diagnostics`, `whatsapp restart-service` |
| Gestao de E-mails | `/plataforma/api/email/*` | `email sessions`, `email create-session`, `email groups`, `email create-group`, `email broadcast`, `email schedules`, `email pause-schedule`, `email resume-schedule`, `email external-contacts` |
| Configuracao Plataforma | `GET/POST /plataforma/api/platform-config`, `GET /plataforma/api/cores-config`, `POST /plataforma/api/platform-config/restore-defaults` | `platform-title`, `platform-config`, `colors-config`, `backup-platform-branding`, `set-platform-branding`, `restore-platform-branding`, `set-platform-config`, `export-platform-config`, `restore-platform-config-defaults` |
| Workspace | `GET/POST/PUT /plataforma/api/containers`, workspace actions, logs, schedules, notifications, versions, upload endpoints | `workspaceall`, `create-workspace`, `update-workspace`, `workspace-start`, `workspace-stop`, `workspace-restart`, `workspace-status`, `workspace-logs`, `workspace-versions`, `workspace-schedule`, `workspace-notification`, `workspace-build`, `deploy-manifest` |
| Gerenciar Paginas | `GET/POST/PUT/DELETE /plataforma/api/paginas*`, hierarchy/order/repair endpoints | `pages`, `page-files`, `create-page`, `update-page`, `delete-page`, `set-page-order`, `page-maintenance`, `resolve-page`, `smoke-pages` |
| Gerenciar RLS | `/plataforma/api/rls*` | `rls pages`, `rls page-info`, `rls page-config --container-id`, `rls config --container-id`, `rls set-config`, `rls set-page-mapping`, `rls data --container-id`, `rls create-data`, `rls create-dimension`, `rls test-config`, `rls-export` |
| Configuracao IA | `GET/POST/DELETE /plataforma/api/ai-config`, `POST /plataforma/api/ai-config/cleanup` | `ai-config`, `set-ai-config`, `delete-ai-config`, `cleanup-ai-config` |
| Chaves Codex/IA | `/plataforma/api/codex/keys*`, `/plataforma/api/codex/auth-*` | `codex-keys stats`, `codex-keys list`, `codex-keys create`, `codex-keys update`, `codex-keys delete`, `codex-keys usage` |
| Sistema de Auditoria | `GET /plataforma/api/audit/*`, `GET /plataforma/api/audit/export`, `POST /plataforma/api/audit-cleanup` | `audit logs`, `audit dashboard`, `audit health`, `audit log`, `audit cleanup`, `audit-export` |
| Gateway/Upload | `/plataforma/api/python-versions`, `/upload-capabilities`, `/gateway/*`, `/upload-status/<id>`, `/clear-dynamic-data` | `upload-admin python-versions`, `upload-admin capabilities`, `upload-admin gateway-pairings`, `upload-admin gateway-generate-pairing-code`, `upload-admin upload-status`, `upload-admin clear-dynamic-data` |
| Gerenciamento de Sistema | `/api/system/storage-path`, `/plataforma/api/sleep-manager/*`, menu cache endpoints, runtime/cache/status endpoints | `storage-path`, `sleep-manager`, `menu`, `menu-maintenance`, `system-admin database-status`, `system-admin runtime-readiness`, `system-admin clear-all-caches`, `route-map routes` |
| Data Engine | `/plataforma/data-engine/api/db/*`, `/repository/*`, `/datasets/*`, `/terminal/*`, `/session/*` | `studio-inventory`, `data-engine inventory`, `data-engine db-connections --project-id 1`, `data-engine create-db-connection --data-file db.json`, `data-engine repository-list --project-id 1`, `data-engine datasets-list --project-id 1`, `data-engine terminal-command --project-id 1`, `data-engine reset-session --project-id 1` |
| Bancos gerenciados | `/plataforma/api/managed-databases/*` | `managed-databases list/get/create/update/schema/query/integrity/download/tokens/create-token/revoke-token/audit/diagnostics/create-table/create-view/create-index/delete-object/inspect-sqlite/migrate-sqlite` |
| BI Studio | `/plataforma/api/bi/*` | `studio-inventory`, `bi-projects`, `bi-create-project`, `bi-export`, `publish-bi`, `echarts-template` |

## Fast Platform Branding

Export current branding:

```powershell
python .\scripts\rejoinbi.py export-platform-config --output .\platform-config.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br backup-platform-branding
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br platform-title --title "Minha Plataforma BI"
```

Apply title, logos, favicon, and images with an automatic rollback backup:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-platform-branding `
  --browser-title "Minha Plataforma BI" `
  --logo-image-file .\logo.png `
  --logo-menu-image-file .\logo-menu.png `
  --favicon-image-file .\favicon.png `
  --colors-file .\cores.json
```

The command prints `backup_output` and a ready restore command. Keep that JSON when testing customer branding.

Apply a saved config:

```powershell
python .\scripts\rejoinbi.py set-platform-config --data-file .\platform-config.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br restore-platform-branding --backup .\platform-config.json --yes
```

Reset colors only:

```powershell
python .\scripts\rejoinbi.py restore-platform-config-defaults --yes
```

## Fast Admin Operations

List and export users or permissions:

```powershell
# Run only after the requester explicitly asks for identity information.
python .\scripts\rejoinbi.py users --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py sectors --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py permission-pages --permissive --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py download-users --output .\usuarios.xlsx --operation-scope identity --identity-scope
python .\scripts\rejoinbi.py download-permissions --output .\permissoes.xlsx --operation-scope identity --identity-scope
```

Check and repair menu/page configuration:

```powershell
python .\scripts\rejoinbi.py menu-maintenance check-duplicates
python .\scripts\rejoinbi.py page-maintenance verify-hierarchy
python .\scripts\rejoinbi.py page-maintenance fix-hierarchy --yes
```

Use JSON payloads for high-variation screens:

```powershell
python .\scripts\rejoinbi.py rls set-config --data-file .\rls-config.json --yes
python .\scripts\rejoinbi.py email create-group --data-file .\email-group.json --yes
python .\scripts\rejoinbi.py whatsapp create-group --data-file .\whatsapp-group.json --yes
python .\scripts\rejoinbi.py email pause-schedule --schedule-id 12 --yes
python .\scripts\rejoinbi.py email resume-schedule --schedule-id 12 --yes
python .\scripts\rejoinbi.py whatsapp pause-schedule --schedule-id 27 --yes
python .\scripts\rejoinbi.py sleep-manager set-config --data-file .\sleep-config.json --yes
python .\scripts\rejoinbi.py codex-keys create --data-file .\codex-key.json --yes
python .\scripts\rejoinbi.py data-engine create-db-connection --data-file .\db-connection.json --yes
```

RLS needs both page mapping and user dimension data. For platform-created workspace pages, always include `container_id`; it prevents route/page confusion when the same technical page id pattern appears in another workspace. A complete RLS validation should prove four things: the page exists in `accessible-pages`, the standard user has direct permission only for that page, `rls test-config` returns only that e-mail's dimension values, and an admin command attempted as `Usuario` is rejected by the plugin profile guard.

Inspect platform infrastructure and upload support:

```powershell
python .\scripts\rejoinbi.py smoke-admin --output-dir .\smoke-admin --operation-scope diagnostics
python .\scripts\rejoinbi.py system-admin database-status --operation-scope system
python .\scripts\rejoinbi.py system-admin runtime-readiness --operation-scope system
python .\scripts\rejoinbi.py route-map routes --operation-scope system
python .\scripts\rejoinbi.py upload-admin capabilities --operation-scope system
python .\scripts\rejoinbi.py upload-admin gateway-pairings --operation-scope system
```

## BI Studio and Data Engine Inventory

Before answering what exists in BI Studio/Data Engine, creating a linked dataset, changing repository files, or publishing a BI project, run the read-only inventory:

```powershell
python .\scripts\rejoinbi.py studio-inventory --output .\bi-data-inventory.json
python .\scripts\rejoinbi.py studio-inventory --project-id 1 --include-raw
python .\scripts\rejoinbi.py data-engine inventory --project-uid projeto-uid
```

The inventory links each BI Studio project to project-scoped Data Engine resources:

- Data Engine service status and SQL Server driver availability.
- Project session status.
- Database connections, with credentials and connection strings redacted.
- Repository tree and global context.
- Datasets and uploaded files.

Use the inventory as the first source of truth for "o que tem no BI Studio" or "o que tem no Data Engine". It is safe for summaries because password, token, key, secret, credential, and connection-string fields are redacted. Use `--include-raw` only when troubleshooting because it includes sanitized endpoint payloads.

Data Engine session, repository, and dataset endpoints are project-scoped. Pass `--project-id`, `--project-uid`, or include `project_id/project_uid` in the JSON payload so the plugin validates the request before reaching the platform API.

Repository upload coverage includes sheet inspection and upload for Excel/CSV/SQLite-style source files:

```powershell
python .\scripts\rejoinbi.py data-engine repository-inspect-sheets --file .\dados.xlsx
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine repository-upload --project-id "Projeto" --file .\dados.xlsx --folder codex --selected-sheet "Visão Geral" --yes
```

BI Studio exports may contain localized display names with non-ASCII slugs. Before uploading an extracted BI export to a workspace, run `bi-normalize-export --path <folder> --remove-old`; then bind platform pages with localized visible names but ASCII `arquivo` and `rota`. This command also adds `pyarrow>=16.0.0` when parquet materialized Data Engine files are present.

## Safety Notes

- Destructive commands keep explicit confirmation flags.
- User, direct-permission, and permission-group operations are disabled until the requester explicitly names that identity area and the command includes `--operation-scope identity --identity-scope`.
- Identity writes require `--yes` plus an exact resolved target confirmation; a broad diagnostic request never authorizes them.
- Workspace deletion remains blocked for password-protected workspaces unless the workspace password is provided and validated by the platform first.
- Secrets, passwords, PINs, and local session files must never be exported.
- Use dedicated commands for supported modules; use `api-get` / `api-send` only for new endpoints that are not yet present in this map, with the endpoint-derived scope and exact `--confirm-api-path`.
