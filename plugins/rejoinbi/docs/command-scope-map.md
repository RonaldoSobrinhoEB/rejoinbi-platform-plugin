# Command Scope and Governance Map

This is the authoritative scope contract for `scripts/rejoinbi.py`. It prevents a broad request such as "analyze the platform", "fix an upload", or "run diagnostics" from being interpreted as authority to access another operational area.

## Mandatory Scope-Lock Protocol

Every command has one immutable scope. Before an authenticated client is created, the CLI compares that built-in scope with the mandatory `--operation-scope` acknowledgement. A missing or mismatched value stops the command before it can make a remote request.

1. Identify one business area before a remote call.
2. Use the dedicated command for that area and repeat its exact value in `--operation-scope`.
3. Split a multi-area request into explicit steps. Do not use broad administration or diagnostics as a shortcut.
4. Use additional confirmations for identity, mutations, destructive operations, and raw paths.
5. If the requested area or target is unclear, stop before calling the platform.

The only deliberate multi-area transaction is `deploy-manifest`, which is locked to `deployment` and owns its workspace, upload, and page steps internally.

| Scope value | Area | Main commands |
| --- | --- | --- |
| `auth` | Local authentication/session handling | `connect`, `login`, `ensure`, `status`, `tenant` |
| `local` | Local-only tools | `validate-app`, `bi-normalize-export`, `export-package` |
| `workspace` | Workspace lifecycle and configuration | `workspace*`, `create-workspace`, `update-workspace`, `delete-workspace`, `validate-workspace` |
| `upload` | Direct project/file transfer | `upload-folder-select`, `upload-files` |
| `deployment` | Manifest-driven publish transaction | `deploy-manifest` |
| `pages` | Pages, hierarchy, routes, and page smoke | `pages`, `page-*`, `create-page`, `update-page`, `delete-page`, `smoke-pages` |
| `rls` | Row-level-security configuration | `rls`, `rls-export` |
| `bi` | BI Studio and canvas publishing | `bi-*`, `studio-inventory`, `echarts-template`, `publish-bi` |
| `data` | Data Engine and managed databases | `data-engine`, `managed-databases` |
| `platform` | Branding, menu, title, and platform configuration | `platform-*`, `colors-config`, `menu*`, `storage-path` |
| `messaging` | Announcements, e-mail, and WhatsApp | `announcements`, `email`, `whatsapp` |
| `ai` | Page AI configuration and Codex keys | `ai-config`, `set-ai-config`, `codex-keys` |
| `diagnostics` | Audit and reduced core health checks | `audit`, `audit-export`, `smoke-admin` |
| `system` | Runtime, route, sleep, and upload gateway operations | `system-admin`, `route-map`, `sleep-manager`, `upload-admin` |
| `identity` | Users, direct permissions, permission groups, and membership | See protected identity rules below. |
| `raw-api` | An unknown raw API endpoint only | `api-get`, `api-send`, with exact endpoint confirmation. |

## Complete Parser Catalog

The following groups are registered in `COMMAND_OPERATION_SCOPES`. Automated tests derive every parser choice and fail if a new command has no registered scope.

| Scope | Registered commands |
| --- | --- |
| Authentication/local | `auth`, `browser-login`, `connect`, `ensure`, `ensure-connected`, `login`, `status`, `tenant`, `validate-app`, `bi-normalize-export`, `export-package` |
| Workspace | `workspaceall`, `validate-workspace`, `workspace-content`, `create-workspace`, `update-workspace`, `delete-workspace`, `workspace-delete`, `set-workspace-password`, `workspace-start`, `workspace-stop`, `workspace-restart`, `workspace-status`, `workspace-logs`, `workspace-versions`, `workspace-version-export`, `workspace-version-restore`, `workspace-version-delete`, `workspace-schedule`, `workspace-notification`, `workspace-input`, `workspace-build`, `workspace-stop-all` |
| Upload/deployment | `upload-files`, `upload-folder-select`, `deploy-manifest` |
| BI | `bi-projects`, `studio-inventory`, `bi-inventory`, `bi-data-inventory`, `bi-create-project`, `bi-init-canvas`, `bi-tabs`, `bi-tab-content`, `bi-create-tab`, `bi-duplicate-tab`, `bi-rename-tab`, `bi-delete-tab`, `bi-reorder-tabs`, `bi-load-layout`, `bi-save-layout`, `bi-themes`, `bi-save-theme`, `bi-delete-theme`, `bi-export`, `publish-bi`, `echarts-template` |
| Identity | `users`, `sectors`, `setores`, `permission-pages`, `user-presence`, `download-users`, `download-permissions`, `create-user`, `create-users-file`, `update-user`, `set-user-password`, `delete-user`, `user-permissions`, `set-user-permissions`, `recalculate-permissions`, `groups`, `create-group`, `update-group`, `delete-group`, `assign-user-group`, `users-for-groups`, `announcement-groups` |
| Pages/RLS | `pages`, `page-files`, `page-maintenance`, `set-page-order`, `accessible-pages`, `create-page`, `update-page`, `delete-page`, `resolve-page`, `smoke-pages`, `rls`, `rls-export` |
| Platform/messaging/AI/diagnostics/system | `menu`, `menu-maintenance`, `announcements`, `create-announcement`, `delete-announcement`, `platform-config`, `colors-config`, `set-platform-config`, `export-platform-config`, `backup-platform-branding`, `platform-title`, `set-platform-branding`, `restore-platform-branding`, `restore-platform-config-defaults`, `ai-config`, `set-ai-config`, `delete-ai-config`, `cleanup-ai-config`, `storage-path`, `audit`, `audit-export`, `sleep-manager`, `email`, `whatsapp`, `codex-keys`, `route-map`, `system-admin`, `upload-admin`, `smoke-admin` |
| Data/raw | `managed-databases`, `data-engine`, `api-get`, `api-send` |

Special sub-actions that expose identity data are `workspace-notification users`, `sleep-manager users-online`, and `codex-keys users`. They dynamically change from their normal module scope to `identity`. E-mail and WhatsApp contact groups are messaging objects, not platform permission groups.

## Protected Identity Governance

User records, departments, online-user presence, direct permissions, permission reports/pages, permission groups, and membership are denied by default. A successful administrative login is not authorization for this domain.

| Intent | Required acknowledgement |
| --- | --- |
| Read users, reports, permissions, or groups | The user explicitly asked for that exact identity information + `--operation-scope identity --identity-scope`. |
| Create a user or permission group | Exact requested object + both identity flags + `--yes`. |
| Change/delete a user | Both identity flags + `--yes --confirm-user <resolved-id-or-email>`. |
| Replace direct permissions | Both identity flags + `--yes --confirm-user <resolved>`; an empty list also needs `--allow-empty-permissions`. |
| Change/delete a group | Both identity flags + `--yes --confirm-group <resolved-id-or-name>`. |
| Change membership | Both identity flags + `--yes --confirm-user <resolved> --confirm-group <resolved>`. |
| Recalculate all permissions | Both identity flags + `--yes --confirm-all-users RECALCULATE-ALL`. |

The protection exists at two levels: `make_client()` rejects a missing identity declaration and `RejoinBIClient.ensure_scope_allows_path()` blocks an identity API route from any client not locked to `identity`. Therefore a future handler cannot accidentally reach identity endpoints from a workspace, upload, page, BI, system, or messaging command.

`smoke-admin` is permanently limited to core diagnostics. It does not inspect identity, messaging, AI, Data Engine, or RLS. Use the dedicated command with the corresponding scope for those areas.

## Raw API Rules

`api-get` and `api-send` never bypass a scope. Known endpoint paths derive their actual scope: for example, `/plataforma/api/users` is `identity`, `/plataforma/api/platform-config` is `platform`, and `/plataforma/api/containers` is `workspace`. The caller must provide the derived value in `--operation-scope` and repeat the exact endpoint using `--confirm-api-path`.

Identity raw paths additionally require `--identity-scope`; raw writes also require `--yes`. An unknown path is assigned `raw-api`, but still requires its exact path confirmation.

## Examples

```powershell
# Deployment cannot access identity APIs.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --operation-scope deployment `
  --manifest .\rejoinbi-app.json --operation-scope deployment

# Explicit identity read.
python .\scripts\rejoinbi.py users --operation-scope identity --identity-scope

# Exact user-permission change.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions `
  --user pessoa@empresa.com --confirm-user pessoa@empresa.com `
  --permissions relatorio-financeiro --operation-scope identity --identity-scope --yes

# Raw access is path-bound and scope-derived.
python .\scripts\rejoinbi.py api-get --path /plataforma/api/platform-config `
  --confirm-api-path /plataforma/api/platform-config --operation-scope platform
```

No broad request, old conversation topic, or privileged profile substitutes for these acknowledgements.
