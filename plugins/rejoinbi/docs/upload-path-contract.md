# Rejoin BI Upload Path Contract

This is the single source of truth for where an uploaded file lands inside a Rejoin BI workspace. Read it before any `upload-files`, `upload-folder-select`, or `deploy-manifest` command.

Honesty statement: no document can guarantee that every model or every version will understand every path. What this contract guarantees is mechanical enforcement: the CLI builds a local plan, prints every `source -> target`, and rejects the known path errors before authentication or byte transfer. The model must still read the plan it produced and compare it with the requester's intent.

## Vocabulary

| Term | Meaning | Example |
| --- | --- | --- |
| Local absolute path | The real path on this computer | `C:\projects\dashboard\services\production_payload_disk_cache.py` |
| `source_root` | Local base used to compute relative paths | `C:\projects\dashboard` |
| Workspace | Remote platform record that owns one active application tree | workspace `12` |
| `app_root` | Root of the remote application inside the workspace | active `app/` tree |
| Relative path | File path calculated from `source_root` | `services/production_payload_disk_cache.py` |
| `target` | POSIX path relative to `app_root`; the only path the platform receives | `services/production_payload_disk_cache.py` |
| `destination_base` | Plan label reinforcing that `target` is app-relative | `workspace/app` |
| `--folder` | Explicit remote folder prefix applied to selected files | `--folder services` |

A local absolute path is never a valid `target`. Windows drive letters, UNC paths, leading `/`, `..`, and local absolute separators inside a target are rejected.

## Cardinal rule and the incident it prevents

Given:

```text
source_root = C:\projects\dashboard
source      = C:\projects\dashboard\services\production_payload_disk_cache.py
```

The relative path is `services/production_payload_disk_cache.py`, so the default target is:

```text
services/production_payload_disk_cache.py
```

All of these are prefix-loss and wrong for this source:

```text
production_payload_disk_cache.py          # dropped services/; lands at app root
app/production_payload_disk_cache.py      # wrong wrapper folder
C:\projects\dashboard\services\...        # local absolute path is never remote
```

Real incident this prevents: `production_payload_disk_cache.py` was uploaded without the `services/` prefix, so the new file landed at the container root while `services/production_payload_disk_cache.py` kept the old version. Upload returned success, but the remote application did not change.

The CLI refuses `services/x.py -> x.py` unless `--allow-root-drop` was deliberately supplied and the requester authorized relocating that exact file to the app root.

## Which path base applies

| Command | Base for `target` | Notes |
| --- | --- | --- |
| `upload-files --files ... --source-root <root>` | Each file relative to `<root>` | Recommended whenever the file belongs to a project tree |
| `upload-files --files ... --target-path <source>=<target>` | Exact supplied `<target>` | Use when destination must not follow the local tree |
| `upload-files --files ... --folder <folder>` | `<folder>/<file name>` | Prefix only; does not preserve subfolders by itself |
| `upload-folder-select --path <root>` | Each file relative to `<root>` | Publishes the whole selected folder as the project tree |
| `deploy-manifest --upload-mode full` | Each file relative to resolved `app_root` | `app_root` comes from `--path` or the manifest top-level `app_root` |
| `deploy-manifest --upload-mode changed-files --changed-file <relative>` | Path relative to resolved `app_root` | `--changed-target-path <source>=<target>` overrides one destination |

`upload.path` inside a manifest does **not** define `app_root`. Use top-level `app_root` or `--path`.

## Local plan first

Run the upload command with `--dry-run` before it touches the platform. A dry run creates **no authenticated client** and no remote request.

```powershell
python .\scripts\rejoinbi.py upload-files --workspace 12 --source-root C:\projects\dashboard --files C:\projects\dashboard\services\production_payload_disk_cache.py --dry-run --plan-output .\upload-plan.json --operation-scope upload
```

The plan contains:

```json
{
  "success": true,
  "dry_run": true,
  "destination_base": "workspace/app",
  "source_root": "C:\\projects\\dashboard",
  "files": [{"source": "...", "target": "services/production_payload_disk_cache.py", "size": 123, "sha256": "..."}],
  "plan_sha256": "..."
}
```

Review every `target`. If `target` is only a basename while the source relative path contains a folder, stop.

## Exact resolution rules

1. Resolve every local source to an absolute path. Missing file is immediate local error.
2. Resolve `--source-root` when supplied; it must exist and be a directory.
3. If `--source-root` is supplied, every selected file must be inside it after link resolution. A file outside is rejected even with an explicit target.
4. Resolve `--map` and `--target-path`. Each entry must match exactly one selected source; typos, partial matches, and shared basenames in two selected files are rejected.
5. Compute `relative = source.relative_to(source_root)`.
6. Start from the explicit mapping for that source, otherwise `--folder`, otherwise empty.
7. If `relative` has a parent folder, append it to the destination. `services/foo.py` becomes `<base>/services/foo.py`, never `<base>/foo.py`.
8. If the final target has no folder while `relative` does, reject with `[UPLOAD_ROOT_DROP]` unless `--allow-root-drop` is present.
9. Normalize target to POSIX separators. Reject absolute paths, `..`, drive letters, UNC paths, and forbidden characters.
10. Reject two sources converging on the same target, including case-insensitive duplicates.
11. Hash every file and emit `source`, `target`, `size`, and `sha256`.

Without `--source-root`, a selected upload requires an explicit destination through `--target-path` or `--folder`; otherwise reject with `[UPLOAD_SOURCE_ROOT_REQUIRED]`. It never invents a project root from one file's common parent.

`--preserve-paths` is a compatibility alias. It now requires `--source-root`; it does not discover the root.

## Option precedence

Highest to lowest for one source:

1. `--target-path <source>=<exact>` wins; no extra prefix is added.
2. `--map <source>=<folder>` supplies the folder base.
3. `--folder <folder>` supplies the common prefix.
4. `--source-root` contributes the preserved relative parent path.

An explicit target must still pass containment and root-drop rules. An explicit target cannot move a source outside `--source-root`.

## Rejected and accepted examples

```text
# Rejected
upload-files --files C:\projects\dashboard\services\foo.py --folder services
# target would be services/foo.py if --source-root is omitted? No: without --source-root the basename mapping is not inferred and the CLI requires one explicit destination.

# Rejected: drops services/
upload-files --source-root C:\projects\dashboard --files C:\projects\dashboard\services\foo.py --target-path sources/foo.py=src/foo.py

# Accepted with --allow-root-drop only:
upload-files --source-root C:\projects\dashboard --files C:\projects\dashboard\services\foo.py --target-path C:\projects\dashboard\services\foo.py=foo.py --allow-root-drop

# Accepted: preserves project tree
upload-files --source-root C:\projects\dashboard --files C:\projects\dashboard\services\foo.py
# target: services/foo.py
```

## Error codes

| Code | Meaning | Action |
| --- | --- | --- |
| `[UPLOAD_SOURCE_ROOT_REQUIRED]` | Destination would be inferred from a filename only | Pass `--source-root` or an explicit per-file mapping |
| `[UPLOAD_ROOT_DROP]` | A nested source relative path would land at app root | Fix `--source-root`/`--folder`/`--target-path`; only use `--allow-root-drop` after explicit authorization |
| `[UPLOAD_PATH_MAPPING]` | `--map` or `--target-path` is ambiguous, unmatched, or a duplicate source | Use exact source path or source-root-relative path |
| `[UPLOAD_PLAN_CHANGED]` | `--expected-plan-sha256` does not match the current bytes/paths/targets | Rebuild the dry-run plan and review again |
| `[UPLOAD_VERIFY_MISMATCH]` | Remote read-back did not match the plan hash | Stop; inspect the exact remote path before retrying or restarting |

## Upload acceptance is not completion

A resumable transfer success means bytes were received. It does **not** prove the active application reloaded, the selected file was applied, or the old bytes were replaced.

Completion requires:

1. The command reports successful finalization/apply for the exact target list.
2. Optional `--verify-upload` generated `verification.performed = true` and all hashes matched, or you manually read the exact target and its sha256 equals the plan.
3. The workspace status/logs do not show a startup failure.
4. `smoke-pages` reports the required gates only when pages are involved.

Do not claim production readiness from `success: true` on transfer alone.

## Safety reminders

- Uploads include every selected project file; there is no name/type filter. Databases and data files still require explicit flags after review.
- `upload-folder-select` is full publication: it can replace the active project tree.
- `upload-files` and changed-files manifest mode preserve unselected files; they are the safe way to patch one file.
- Never upload a file to prove a path; use `--dry-run` and a planned target. Do not create decoy remote files.
