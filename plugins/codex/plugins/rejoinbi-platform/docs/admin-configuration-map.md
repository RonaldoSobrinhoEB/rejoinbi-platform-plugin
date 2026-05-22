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
| Editar Usuarios | `GET /plataforma/api/users`, `POST /plataforma/api/update-user`, `POST /plataforma/api/change-user-password`, `POST /plataforma/api/delete-user` | `users`, `update-user`, `set-user-password`, `delete-user` |
| Gerenciar Permissoes | `GET /plataforma/api/user-permissions/<id>`, `POST /plataforma/api/update-permissions`, `POST /plataforma/api/recalcular-permissoes` | `user-permissions`, `set-user-permissions`, `recalculate-permissions` |
| Gerenciar Grupos | `GET /plataforma/api/groups`, `POST /plataforma/api/create-group`, `POST /plataforma/api/update-group`, `POST /plataforma/api/delete-group`, `POST /plataforma/api/assign-user-to-group` | `groups`, `create-group`, `update-group`, `delete-group`, `assign-user-group` |
| Upload de Arquivos | `POST /plataforma/api/upload-folder`, `POST /plataforma/api/extract-files`, `POST /plataforma/api/select-app-file`, `POST /plataforma/api/upload-multiple-files` | `upload-folder-select`, `upload-zip-select`, `upload-files` |
| Anuncios Internos | `GET /plataforma/api/anuncios/historico`, `GET /plataforma/api/anuncios/ativos`, `POST /plataforma/api/anuncios`, `DELETE /plataforma/api/anuncios/<id>` | `announcements`, `create-announcement`, `delete-announcement`, `announcement-groups` |
| Configuracao WhatsApp | `/plataforma/api/whatsapp/*` | Use `api-get` / `api-send` with the mapped endpoint until a dedicated command is added |
| Gestao de E-mails | `/plataforma/api/email/*` | Use `api-get` / `api-send` with the mapped endpoint until a dedicated command is added |
| Configuracao Plataforma | `GET/POST /plataforma/api/platform-config`, `GET /plataforma/api/cores-config`, `POST /plataforma/api/platform-config/restore-defaults` | `platform-config`, `colors-config`, `set-platform-config`, `export-platform-config`, `restore-platform-config-defaults` |
| Workspace | `GET/POST/PUT /plataforma/api/containers`, workspace actions, upload/version endpoints | `workspaceall`, `create-workspace`, `update-workspace`, `workspace-start`, `workspace-stop`, `workspace-restart`, `workspace-status`, `deploy-manifest` |
| Gerenciar Paginas | `GET/POST/PUT/DELETE /plataforma/api/paginas*` | `pages`, `create-page`, `update-page`, `delete-page`, `resolve-page`, `smoke-pages` |
| Gerenciar RLS | `/plataforma/api/rls*` | Use `api-get` / `api-send` with the mapped endpoint until a dedicated command is added |
| Configuracao IA | `GET/POST/DELETE /plataforma/api/ai-config`, `POST /plataforma/api/ai-config/cleanup` | `ai-config`, `set-ai-config`, `delete-ai-config`, `cleanup-ai-config` |
| Sistema de Auditoria | `GET /plataforma/api/audit/*`, `POST /plataforma/api/audit-cleanup` | Use `api-get` / `api-send` with the mapped endpoint |
| Gerenciamento de Sistema | `/plataforma/api/*`, `/api/system/storage-path` | `storage-path`, `api-get`, `api-send` |
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

## Safety Notes

- Destructive commands keep explicit confirmation flags.
- Workspace deletion remains blocked for password-protected workspaces unless the workspace password is provided and validated by the platform first.
- Secrets, passwords, PINs, and local session files must never be exported.
- Use dedicated commands for supported modules; use `api-get` / `api-send` only for mapped endpoints that do not yet have a first-class command.
