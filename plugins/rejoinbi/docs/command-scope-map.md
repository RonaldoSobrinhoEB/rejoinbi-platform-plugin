# Command Scope and Governance Map

This is the authoritative execution-scope map for `scripts/rejoinbi.py`. It exists so a broad request such as “analyze the platform”, “fix an upload”, “publish a page”, or “run diagnostics” cannot be interpreted as authority to inspect or modify customer identities, direct permissions, or permission groups.

## Scope Contract

Every command belongs to one of the following areas. A command can access only its own area and the authenticated Rejoin BI tenant.

| Area | Commands and API families | Default authority | Additional barriers |
| --- | --- | --- | --- |
| Authentication and session | `connect`, `login`, `ensure`, `status`, `tenant` | Session only | Never exports password, PIN, or cookies. |
| Workspace lifecycle | `workspaceall`, `workspace-*`, `create-workspace`, `update-workspace`, `delete-workspace`, `validate-workspace` | Read or targeted workspace change | Tenant acknowledgement for writes; destructive commands also use name/id/password confirmation. |
| Project transfer | `upload-folder-select`, `upload-files`, `deploy-manifest`, `select-app-file`, upload-session APIs | Targeted workspace only | Explicit tenant, resumable bounded chunks, retry/skip/cancel behavior, no automatic ZIP project upload. |
| Pages and routing | `pages`, `accessible-pages`, `page-*`, `create-page`, `update-page`, `delete-page`, `smoke-pages` | Read or targeted page change | Tenant acknowledgement for writes; page deletion has its own dry-run and cascade confirmations. |
| BI and data | `studio-inventory`, `bi-*`, `echarts-*`, `data-engine`, `managed-databases` | Project/database scoped | Project id/uid or database target is required where applicable; credentials are redacted. |
| Platform operations | branding/configuration, announcements, email, WhatsApp, RLS, audit, sleep, Codex keys, route/system/upload admin | Module scoped | Mutating commands require their module's `--yes` and payload/target validation. |
| Identity governance | users, departments, online-user presence, direct page permissions, permission exports, permission groups, group membership, and identity selectors exposed by notifications/AI keys | **Denied by default** | Requires `--identity-scope`; writes also require `--yes` and exact target confirmation. |
| Raw authenticated APIs | `api-get`, `api-send` | Endpoint scoped | Identity paths receive the same governance barriers; raw writes also require `--yes`. |

## Complete Top-Level Command Catalog

The catalog below is generated from the parser contract in `rejoinbi.py`; aliases are omitted where they invoke the same command. Sub-actions remain inside their named family and inherit the family scope unless this map says otherwise.

| Scope | Top-level commands |
| --- | --- |
| Authentication/session | `connect`, `login`, `ensure`, `ensure-connected`, `tenant`, `auth`, `browser-login`, `status` |
| Workspace/container | `workspaceall`, `validate-workspace`, `workspace-content`, `create-workspace`, `update-workspace`, `delete-workspace`, `set-workspace-password`, `workspace-start`, `workspace-stop`, `workspace-restart`, `workspace-status`, `workspace-logs`, `workspace-versions`, `workspace-version-export`, `workspace-version-restore`, `workspace-version-delete`, `workspace-schedule`, `workspace-notification`, `workspace-input`, `workspace-build`, `workspace-stop-all` |
| Upload/deployment | `upload-files`, `upload-folder-select`, `deploy-manifest`, `smoke-pages`, `validate-app`, `export-package` |
| BI Studio/canvas | `bi-projects`, `studio-inventory`, `bi-create-project`, `bi-init-canvas`, `bi-tabs`, `bi-tab-content`, `bi-create-tab`, `bi-duplicate-tab`, `bi-rename-tab`, `bi-delete-tab`, `bi-reorder-tabs`, `bi-load-layout`, `bi-save-layout`, `bi-themes`, `bi-save-theme`, `bi-delete-theme`, `bi-export`, `bi-normalize-export`, `publish-bi`, `echarts-template` |
| Protected identity governance | `users`, `sectors`, `permission-pages`, `user-presence`, `download-users`, `download-permissions`, `create-user`, `update-user`, `set-user-password`, `delete-user`, `user-permissions`, `set-user-permissions`, `recalculate-permissions`, `groups`, `create-group`, `update-group`, `delete-group`, `assign-user-group`, `users-for-groups`, `announcement-groups` |
| Pages/routes/RLS | `pages`, `page-files`, `page-maintenance`, `set-page-order`, `accessible-pages`, `create-page`, `update-page`, `delete-page`, `resolve-page`, `rls`, `rls-export` |
| Platform config and messaging | `menu`, `menu-maintenance`, `announcements`, `create-announcement`, `delete-announcement`, `platform-config`, `colors-config`, `set-platform-config`, `export-platform-config`, `backup-platform-branding`, `platform-title`, `set-platform-branding`, `restore-platform-branding`, `restore-platform-config-defaults`, `ai-config`, `set-ai-config`, `delete-ai-config`, `cleanup-ai-config`, `storage-path`, `audit`, `audit-export`, `sleep-manager`, `email`, `whatsapp`, `codex-keys`, `route-map`, `system-admin`, `upload-admin` |
| Persistent data | `managed-databases`, `data-engine` |
| Generic API | `api-get`, `api-send` |

Special sub-actions with identity data are `workspace-notification users`, `sleep-manager users-online`, and `codex-keys users`. Those individual reads require `--identity-scope`; other actions in their same module retain their normal module scope. E-mail and WhatsApp groups are messaging/contact objects and are intentionally not classified as platform permission groups.

## Identity Governance: Explicit Opt-In Only

The protected identity area includes all user records, user status, departments, direct user permissions, permission reports, permission pages, permission groups, group membership, and global permission recalculation. The following commands are protected:

| Intent | Commands | Minimum invocation rule |
| --- | --- | --- |
| Read users and reports | `users`, `sectors`, `user-presence`, `download-users`, `download-permissions` | User explicitly asked for this identity information + `--identity-scope`. |
| Read permission structure | `permission-pages`, `user-permissions` | User explicitly asked for permissions + `--identity-scope`. |
| Read groups/memberships | `groups`, `users-for-groups` | User explicitly asked for groups + `--identity-scope`. |
| Read identity selectors in other modules | `announcement-groups`, `workspace-notification users`, `sleep-manager users-online`, `codex-keys users` | User explicitly asked for those users/groups + `--identity-scope`. E-mail and WhatsApp contact groups remain messaging-scope objects. |
| Create identity objects | `create-user`, `create-group` | Exact requested object + `--identity-scope --yes`. |
| Change or delete a user | `update-user`, `set-user-password`, `delete-user` | Exact requested change + `--identity-scope --yes --confirm-user <resolved-id-or-email>`. |
| Replace direct permissions | `set-user-permissions` | Exact requested access set + `--identity-scope --yes --confirm-user <resolved-id-or-email>`. An empty replacement also requires `--allow-empty-permissions`. |
| Change or delete a group | `update-group`, `delete-group` | Exact requested change + `--identity-scope --yes --confirm-group <resolved-id-or-name>`. |
| Change group membership | `assign-user-group` | Exact requested membership + `--identity-scope --yes --confirm-user <resolved> --confirm-group <resolved>`. |
| Recalculate everyone | `recalculate-permissions` | Explicit global request + `--identity-scope --yes --confirm-all-users RECALCULATE-ALL`. |

`smoke-admin` deliberately excludes all identity endpoints. Only a request explicitly asking for an identity smoke check may use `smoke-admin --include-identity --identity-scope`.

The raw API escape hatches cannot bypass this map. `api-get` and `api-send` classify all mapped identity paths under `/plataforma/api/` as identity governance. Therefore an API read still needs `--identity-scope`, and an API write needs both `--identity-scope --yes` in addition to any endpoint-specific data validation.

## What Is Not Authority

None of the following authorizes identity access:

- A valid Administrator, Master, or Administrador Principal session.
- A request to analyze, diagnose, inventory, map, audit, deploy, upload, build, or repair the platform.
- A workspace/page/BI/RLS/WhatsApp/e-mail request that does not explicitly name users, direct permissions, or permission groups.
- A general request to "handle administration", "check everything", or "make it work".
- A previous identity request in the conversation when the present operation has another scope.

When identity work is genuinely requested, the plugin must first state the exact target and intended effect, then use the protected command and flags above. It must not create test users, adjust permissions, or touch groups merely to make a smoke test, deployment, or diagnosis easier.

## Enforcement Points in `rejoinbi.py`

1. `make_client()` calls `ensure_identity_scope_for_command()` before any authenticated request is created.
2. `command_uses_identity_governance()` covers dedicated identity commands, optional identity smoke checks, and raw API paths.
3. `command_mutates_identity_governance()` adds the mandatory `--yes` barrier for identity writes.
4. User and group mutators resolve the target from the server and require it to be repeated through `--confirm-user` or `--confirm-group` before the write.
5. Permission replacement refuses an accidental empty allow/deny list; global recalculation requires a literal global-impact acknowledgement.
6. The parser exposes identity flags only on identity commands and on `api-get`, `api-send`, and the explicitly optional identity smoke mode.
7. Automated tests verify that identity reads, writes, raw endpoints, smoke expansion, parser flags, and target confirmations cannot regress silently.

## Safe Examples

```powershell
# Normal deployment: it has no identity scope and cannot reach identities.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\rejoinbi-app.json

# Explicit read requested by the customer.
python .\scripts\rejoinbi.py users --identity-scope

# Explicit permission change for one resolved user.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br set-user-permissions `
  --user pessoa@empresa.com --confirm-user pessoa@empresa.com `
  --permissions relatorio-financeiro --identity-scope --yes

# Explicit, read-only identity portion of an admin smoke check.
python .\scripts\rejoinbi.py smoke-admin --include-identity --identity-scope
```

If an execution request cannot satisfy this map, stop before calling the protected endpoint and ask the requester to explicitly authorize the identity area and exact target.
