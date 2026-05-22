# Admin Configuration Map

This map follows the public Rejoin BI user manual and the analyzed Flask blueprints in the local platform codebase.

## Permission Levels

- Administrador Principal: highest access level, full platform/user control, no PIN during login.
- Master: global management and workspace visibility, requires PIN.
- Administrador: operational management for users, groups, permissions, and granted tools, requires PIN.
- Usuario: dashboard/report access and own account changes, requires PIN.

The plugin treats a successful login that does not request PIN as `Administrador Principal`. Saved sessions created through that no-PIN flow keep this profile hint so later `ensure` and administrative commands do not downgrade it to `Master`.

## Sidebar Tools

| Manual tool | Primary API | Plugin command |
| --- | --- | --- |
| Cadastrar Usuario | `POST /plataforma/api/register` | `create-user` |
| Editar Usuarios | `GET /plataforma/api/users`, `GET /plataforma/api/setores`, `GET /plataforma/api/users-presence`, `GET /plataforma/api/download-users`, `POST /plataforma/api/update-user`, `POST /plataforma/api/change-user-password`, `POST /plataforma/api/delete-user` | `users`, `sectors`, `user-presence`, `download-users`, `update-user`, `set-user-password`, `delete-user` |
| Gerenciar Permissoes | `GET /plataforma/api/pages`, `GET /plataforma/api/permissive-pages`, `GET /plataforma/api/user-permissions/<id>`, `GET /plataforma/api/download-permissions`, `POST /plataforma/api/update-permissions`, `POST /plataforma/api/recalcular-permissoes` | `permission-pages`, `user-permissions`, `download-permissions`, `set-user-permissions`, `recalculate-permissions` |
| Gerenciar Grupos | `GET /plataforma/api/groups`, `POST /plataforma/api/create-group`, `POST /plataforma/api/update-group`, `POST /plataforma/api/delete-group`, `POST /plataforma/api/assign-user-to-group` | `groups`, `create-group`, `update-group`, `delete-group`, `assign-user-group` |
| Upload de Arquivos | `POST /plataforma/api/upload-folder`, `POST /plataforma/api/extract-files`, `POST /plataforma/api/select-app-file`, `POST /plataforma/api/upload-multiple-files` | `upload-folder-select`, `upload-zip-select`, `upload-files` |
| Anuncios Internos | `GET /plataforma/api/anuncios/historico`, `GET /plataforma/api/anuncios/ativos`, `POST /plataforma/api/anuncios`, `DELETE /plataforma/api/anuncios/<id>` | `announcements`, `create-announcement`, `delete-announcement`, `announcement-groups` |
| Configuracao WhatsApp | `/plataforma/api/whatsapp/*` | `whatsapp sessions`, `whatsapp groups`, `whatsapp create-group`, `whatsapp broadcast`, `whatsapp schedules`, `whatsapp diagnostics`, `whatsapp restart-service` |
| Gestao de E-mails | `/plataforma/api/email/*` | `email sessions`, `email create-session`, `email groups`, `email create-group`, `email broadcast`, `email schedules`, `email external-contacts` |
| Configuracao Plataforma | `GET/POST /plataforma/api/platform-config`, `GET /plataforma/api/cores-config`, `POST /plataforma/api/platform-config/restore-defaults` | `platform-config`, `colors-config`, `set-platform-config`, `export-platform-config`, `restore-platform-config-defaults` |
| Workspace | `GET/POST/PUT /plataforma/api/containers`, workspace actions, logs, schedules, notifications, versions, upload endpoints | `workspaceall`, `create-workspace`, `update-workspace`, `workspace-start`, `workspace-stop`, `workspace-restart`, `workspace-status`, `workspace-logs`, `workspace-versions`, `workspace-schedule`, `workspace-notification`, `workspace-build`, `deploy-manifest` |
| Gerenciar Paginas | `GET/POST/PUT/DELETE /plataforma/api/paginas*`, hierarchy/order/repair endpoints | `pages`, `page-files`, `create-page`, `update-page`, `delete-page`, `set-page-order`, `page-maintenance`, `resolve-page`, `smoke-pages` |
| Gerenciar RLS | `/plataforma/api/rls*` | `rls pages`, `rls page-config`, `rls config`, `rls set-config`, `rls data`, `rls create-data`, `rls dimensions`, `rls validate`, `rls-export` |
| Configuracao IA | `GET/POST/DELETE /plataforma/api/ai-config`, `POST /plataforma/api/ai-config/cleanup` | `ai-config`, `set-ai-config`, `delete-ai-config`, `cleanup-ai-config` |
| Chaves Codex/IA | `/plataforma/api/codex/keys*`, `/plataforma/api/codex/auth-*` | `codex-keys stats`, `codex-keys list`, `codex-keys create`, `codex-keys update`, `codex-keys delete`, `codex-keys usage` |
| Sistema de Auditoria | `GET /plataforma/api/audit/*`, `GET /plataforma/api/audit/export`, `POST /plataforma/api/audit-cleanup` | `audit logs`, `audit dashboard`, `audit health`, `audit log`, `audit cleanup`, `audit-export` |
| Cloudflare/Dominio | `/plataforma/api/cloudflare/*` | `cloudflare status`, `cloudflare dns-records`, `cloudflare configure`, `cloudflare create-dns-record`, `cloudflare ssl-mode`, `cloudflare set-ssl-mode` |
| Gateway/Upload | `/plataforma/api/python-versions`, `/upload-capabilities`, `/gateway/*`, `/upload-status/<id>`, `/clear-dynamic-data` | `upload-admin python-versions`, `upload-admin capabilities`, `upload-admin gateway-pairings`, `upload-admin gateway-generate-pairing-code`, `upload-admin upload-status`, `upload-admin clear-dynamic-data` |
| Gerenciamento de Sistema | `/api/system/storage-path`, `/plataforma/api/sleep-manager/*`, menu cache endpoints, runtime/cache/status endpoints | `storage-path`, `sleep-manager`, `menu`, `menu-maintenance`, `system-admin database-status`, `system-admin runtime-readiness`, `system-admin clear-all-caches`, `route-map routes` |
| Data Engine | `/plataforma/data-engine/api/db/*`, `/repository/*`, `/datasets/*`, `/terminal/*`, `/session/*` | `data-engine db-connections`, `data-engine create-db-connection`, `data-engine repository-list`, `data-engine datasets-list`, `data-engine terminal-command`, `data-engine reset-session` |
| BI Studio | `/plataforma/api/bi/*` | `bi-projects`, `bi-create-project`, `bi-export`, `publish-bi`, `echarts-template` |

## Fast Platform Branding

Export current branding:

```powershell
python .\scripts\rejoinbi.py export-platform-config --output .\platform-config.json
```

Apply branding and images:

```powershell
python .\scripts\rejoinbi.py set-platform-config `
  --browser-title "Minha Plataforma BI" `
  --logo-image-file .\logo.png `
  --logo-menu-image-file .\logo-menu.png `
  --icon-image-file .\icon.png `
  --colors-file .\cores.json
```

Apply a saved config:

```powershell
python .\scripts\rejoinbi.py set-platform-config --data-file .\platform-config.json
```

Reset colors only:

```powershell
python .\scripts\rejoinbi.py restore-platform-config-defaults --yes
```

## Fast Admin Operations

List and export users or permissions:

```powershell
python .\scripts\rejoinbi.py users
python .\scripts\rejoinbi.py sectors
python .\scripts\rejoinbi.py permission-pages --permissive
python .\scripts\rejoinbi.py download-users --output .\usuarios.xlsx
python .\scripts\rejoinbi.py download-permissions --output .\permissoes.xlsx
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
python .\scripts\rejoinbi.py sleep-manager set-config --data-file .\sleep-config.json --yes
python .\scripts\rejoinbi.py cloudflare set-ssl-mode --mode full --yes
python .\scripts\rejoinbi.py codex-keys create --data-file .\codex-key.json --yes
python .\scripts\rejoinbi.py data-engine create-db-connection --data-file .\db-connection.json --yes
```

Inspect platform infrastructure and upload support:

```powershell
python .\scripts\rejoinbi.py system-admin database-status
python .\scripts\rejoinbi.py system-admin runtime-readiness
python .\scripts\rejoinbi.py route-map routes
python .\scripts\rejoinbi.py upload-admin capabilities
python .\scripts\rejoinbi.py upload-admin gateway-pairings
```

## Safety Notes

- Destructive commands keep explicit confirmation flags.
- Workspace deletion remains blocked for password-protected workspaces unless the workspace password is provided and validated by the platform first.
- Secrets, passwords, PINs, and local session files must never be exported.
- Use dedicated commands for supported modules; use `api-get` / `api-send` only for new endpoints that are not yet present in this map.
