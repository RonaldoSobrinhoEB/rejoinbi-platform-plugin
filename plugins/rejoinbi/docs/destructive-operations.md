# Destructive Operation Safety

This plugin treats workspace and page deletion as production-risk operations. Every removal command prints a dry-run plan by default and requires exact confirmation flags before it calls the platform API.

## Workspace Delete

Dry run:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --operation-scope workspace
```

Actual delete for a workspace without password:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12 --operation-scope workspace
```

Actual delete for a password-protected workspace:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite --yes --confirm-name codex-suite --confirm-id 12 --workspace-password "senha-do-workspace" --operation-scope workspace
```

The plan shows:

- Resolved workspace id/name/status.
- Whether the workspace is password-protected.
- Direct pages attached to the workspace.
- All pages that will be reached by parent, real-parent, fictitious-parent, fictitious, or hierarchy references.
- Parent-child-grandchild tree.
- Linked pages outside the workspace.

Password-protected workspaces are blocked unless the caller provides the workspace password through `--workspace-password` or `REJOINBI_WORKSPACE_PASSWORD` and the platform validates it through `/plataforma/api/validate-container-password`. If the password is missing or invalid, no deletion is attempted and the user must remove the workspace manually in Rejoin BI after reviewing the security impact.

Deletion is blocked when linked pages outside the workspace are found. Add `--allow-linked-pages` only after reviewing those pages and confirming they are safe to remove.

Reserved names such as `admin`, `master`, `plataforma`, `default`, `system`, and `home` are blocked unless `--force-reserved` is provided after manual review.

## Page Delete

Dry run:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview --operation-scope pages
```

Actual delete:

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview --yes --confirm-page-id codex-suite-overview --cascade --operation-scope pages
```

The page delete plan shows:

- The resolved page id, route, file, parent, workspace, and active state.
- Descendants reached by `pai`.
- Cross-container fictitious links reached by `ficticio`.
- Additional hierarchy references that may need manual review.

Deletion is blocked when:

- `--confirm-page-id` does not exactly match the resolved page id.
- The page has descendants and `--cascade` is missing.
- The selected id is a fictitious wrapper such as `pai-ficticio-*`.
- Additional hierarchy references exist and `--allow-linked-pages` is missing.

## Verification

After a destructive API call, the CLI reloads workspaces/pages and reports whether the target still exists and whether any planned page ids remain. Treat any remaining planned page as a failed cleanup that needs manual inspection in Gerenciar Paginas.

## Remove File (arquivo avulso)

Removes a single loose file/folder (arquivo avulso) from a workspace container via
`POST /plataforma/api/delete-individual-item`. This targets files uploaded outside the
managed page tree — e.g. stray assets left in the workspace content.

Dry run:

```
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br remove-file --workspace codex-suite --path legado/antigo.html --type file --dry-run
```

Actual removal (requires the workspace operation scope and explicit confirmation):

```
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br --operation-scope workspace remove-file --workspace codex-suite --path legado/antigo.html --type file --confirm-path legado/antigo.html --yes
```

Notes:

- `--path` is the relative path inside the workspace content; `--confirm-path` must exactly match it.
- `--type` is `file` (default) or `folder`.
- `--restart` restarts the container after removal (default: no).
- Removal is blocked when `--yes` is absent or `--confirm-path` does not match `--path`.

