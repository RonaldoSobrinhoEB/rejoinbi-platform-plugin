# Rejoin BI Workspace Compatibility Guide

Use this guide when building or publishing a workspace project. Paths here are relative to the **workspace's active project root** unless explicitly described as local absolute paths. For selected-file mapping, dry-run plans, error codes, and read-back verification, read [upload-path-contract.md](upload-path-contract.md) before choosing a transfer command. The contract file is tracked in version at docs/upload-path-contract.md.

## The objects involved

| Object | Meaning | Do not confuse it with |
| --- | --- | --- |
| Platform / tenant | One full address, such as `subdomain.rejoinbi.com.br` | Another saved session or a GitHub repository |
| Workspace / container | A platform record with an ID/name and an active project tree | A local directory that happens to use the same name |
| Local project root | Directory whose relative tree should become the workspace's project tree | A wrapper directory or a nested `services/` directory |
| Workspace file path | Relative path inside the active project, e.g. `services/cache.py` | Its basename `cache.py` or the host filesystem's absolute `.../app/...` path |
| Platform page | A Gerenciar Páginas record binding a workspace, file, and route | The uploaded HTML file alone |
| Startup configuration | Static mode, Python entrypoint, or a custom command | A menu page route |

A file transfer does not by itself create a page, restart Python, select an entrypoint, or prove that the live app is using that file. Match the command to each required step and verify the resulting behavior.

## Dashboard pages and manifest

Build one standalone HTML file per platform-managed page. Gerenciar Páginas controls hierarchy, menu placement, icon, permissions, parent page, active status, route, and file binding. Shared CSS, JavaScript, images, and fonts can live in `assets/`. Avoid an internal sidebar, SPA router, or tab switcher that duplicates navigation between these platform pages; ordinary filters or interactions within one page remain valid.

Keep each manifest page's fields separate:

| Field | Example | Purpose |
| --- | --- | --- |
| `id` | `cliente-visao-geral` | Stable technical ASCII identifier; a workspace/client prefix belongs here |
| `name` | `Visão Geral` | Clean localized label displayed in the menu |
| `file` | `visao-geral.html` | Actual file path relative to the uploaded project root |
| `route` | `visao-geral` | App path requested through the workspace tunnel |
| `expect_text` | `dashboard-visao-geral` | Distinctive text/HTML marker that proves the intended page was returned |

For a static project, prefer the file path without its `.html` suffix as the route. A nested `reports/visao.html` therefore normally uses `reports/visao`. Visible Portuguese names can contain accents; IDs, routes, and filenames remain ASCII. Save the manifest and source as UTF-8. Corrupted labels such as `Vis?o` or mojibake are blocking text-integrity issues, not acceptable substitutes for accents.

Minimal static project:

~~~text
project/
  visao-geral.html
  operacoes.html
  assets/
    app.css
    app.js
  rejoinbi-app.json
~~~

Minimal manifest:

~~~json
{
  "name": "Dashboard operacional",
  "language": "pt-BR",
  "app_root": ".",
  "workspace": {"name": "dashboard-operacional", "create": false},
  "upload": {"startup_mode": "static", "auto_start": true},
  "pages": [
    {
      "id": "dashboard-operacional-visao",
      "name": "Visão Geral",
      "file": "visao-geral.html",
      "route": "visao-geral",
      "expect_text": "dashboard-visao-geral"
    }
  ]
}
~~~

`app_root` belongs at the manifest's top level. It is resolved relative to the manifest directory unless the command supplies `--path`. `upload.path` does not define the project root. Keep `workspace.create: false` for an update to an existing workspace; changed-files deployment cannot create a new workspace. See [page-routing-map.md](page-routing-map.md) for route inference and readiness details.

When the desired technical ID differs from the slug of the visible name, `deploy-manifest` creates with the technical name and then updates the display name. Inspect the resulting IDs and labels; do not assume the platform ignored its name-derived ID behavior.

## Startup modes

| Mode | Required project shape | Checks and operational consequences |
| --- | --- | --- |
| `static` | At least one HTML file; relative assets | No Python entrypoint is selected. Register each visual file as its own page. |
| `file` | `app.py`, `main.py`, or an explicit `selected_file`; framework templates/assets | Choose the exact application entrypoint. `validate-app` compiles the selected Python entrypoint when present. |
| `command` | A real `startup_command` suitable for the runtime | The platform limits the command to 500 characters. Do not use this mode to compensate for a wrong project root. |

For Flask, keep templates in `templates/` and static assets in `static/`. A page bound to `templates/visao.html` can render at an app route such as `visao`; its browser route is not automatically `templates/visao`. Configure/verify that route and use `allow_custom_route: true` where the manifest validator requires it.

`requirements.txt` is optional. Without it, startup uses the runtime's available/default libraries; this does not guarantee an arbitrary dependency is installed. Include only actual additional dependencies and verify their installation in workspace logs. If the app reads Parquet, include a compatible Parquet engine such as `pyarrow` or `fastparquet`; a running Python process is not evidence that its datasets loaded.

Prefer relative links matching the page location. A root-level HTML can link `./assets/app.css`; nested HTML needs a path consistent with its location. For Flask URLs and API endpoints, account for the platform's `/plataforma/<workspace-name>/client/` prefix and verify the actual tunnel request rather than assuming domain-root routes will work.

Use `/api/` for backend data endpoints, e.g. `/api/status` or `/api/search`. Keep data endpoints separate from visual routes and return the correct content type. Non-API data paths can collide with the page resolver/proxy.

## Select the correct publication behavior

| Request / authorized behavior | Command | Existing unselected files | Other effects |
| --- | --- | --- | --- |
| Replace the complete active project | `upload-folder-select` | The previous `app/` tree is versioned/replaced; files absent from the upload are absent from the new active tree | Configures startup and may start the workspace according to the options |
| Publish complete project plus manifest pages | `deploy-manifest --upload-mode full` | Same complete-tree publication | Creates workspace only when selected; synchronizes pages and startup |
| Apply only reviewed files | `upload-files` | Preserved | Does not replace the tree; `--restart` is optional |
| Apply reviewed manifest-relative files | `deploy-manifest --upload-mode changed-files --changed-file ...` | Preserved | No entrypoint reselection; no restart or page synchronization unless selected |

Resolve full versus selected publication from the requester's instructions. Preserve a choice already made for the same target and operation; do not repeatedly ask. If the scope is still ambiguous and the distinction changes which remote files survive, resolve it before publication.

A complete publication can stop the workspace, archive its old project, and start its new project. A changed-files update applies only the named destinations after resumable transfer finalization. Do not use complete-project publication as a shortcut for replacing one source file. Conversely, changed-files mode cannot bootstrap a working project into an empty workspace.

Changed-files manifest paths are relative to the resolved `app_root`:

~~~powershell
# Package-root command; the project tree is C:\projects\dashboard.
python .\scripts\rejoinbi.py deploy-manifest --manifest C:\projects\dashboard\rejoinbi-app.json --upload-mode changed-files --changed-file services/production_payload_disk_cache.py --dry-run --plan-output .\changed-plan.json --operation-scope deployment
~~~

Inspect `files[].source`, `target`, `size`, and `sha256` in the plan. `--plan-output` must be outside the upload source root. This example must show the target `services/production_payload_disk_cache.py`; a target containing only the basename is a different destination. Read the [upload path contract](upload-path-contract.md) for explicit remapping and the `--allow-root-drop` exception.

`--restart-after-upload` and `--sync-pages` add independent actions to a changed-files manifest update; choose them only when required and authorized. A manifest with `replace_pages: true` also requests page replacement; inspect it before using the manifest against an existing workspace.

## Project selection, data, and recovery

Complete-folder traversal includes regular files under the selected root, including hidden files, caches, virtual environments, archives, and dependency folders. The compatibility `--exclude` and manifest `upload.exclude` values are ignored by the CLI; they are not a reliable way to keep a file out of publication. Prepare the exact complete project folder, or use explicit selected-file mode. Upload controls reject unsafe relative paths and reserved resumable-session metadata; they do not decide that a filename is useful project content.

Local database artifacts and recognized data files require explicit review plus `--allow-database-files` and/or `--allow-data-files` for the applicable categories. These guards apply to complete and selected uploads. A blanket project update instruction does not mean that a production database should be replaced. Keep the exact source/destination list and the authorization together; reuse that authorization if the same upload is retried.

For a protected workspace, validate its workspace password before performing a gated upload or page change. Use the browser/terminal secret flow or the applicable workspace-password input; do not put secrets into shared instructions or logs.

Uploads are resumable bounded requests, not ZIP extraction. Both direct upload commands support `--on-file-error {ask,retry,skip,cancel,fail}` and bounded retries. A skipped file means an incomplete selection: report its exact path and do not claim complete publication. A cancelled/failing upload is not proof that the old runtime changed. Finalization, selected-file apply, and full-project publication are distinct stages.

The local platform defaults to 8 MiB resumable parts, one configured upload worker, three simultaneous HTTP upload requests, two simultaneous writes, and a disk reserve. These values are server configuration, not an overall project-size guarantee. Use `upload-admin capabilities --operation-scope system` to inspect the target platform's actual advertised values. Do not hardcode a remote server's limits from the local defaults.

## Completion checks

Run local validation before publication:

~~~powershell
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json
~~~

Use `--strict` when warnings must block this release. Local validation does not prove remote permissions, dependencies, data freshness, or browser rendering.

After publication, read every changed file's **exact destination** and compare the returned `sha256` with the local plan. JSON read output includes path, byte size, hash, and content metadata; `--raw` omits this verification envelope. A large/binary file may have empty `content` while its hash/size remain usable; do not infer emptiness from the editor's content limit.

~~~powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-file read --workspace dashboard-operacional --path services/production_payload_disk_cache.py --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-status --workspace dashboard-operacional --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-logs --workspace dashboard-operacional --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest C:\projects\dashboard\rejoinbi-app.json --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br pages --workspace dashboard-operacional --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-maintenance verify-hierarchy --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-maintenance audit-encoding --strict --operation-scope pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br page-files --workspace dashboard-operacional --operation-scope pages
~~~

Require `smoke-pages.success`, `readiness.success`, and each page's `html_ok`, `browser_route_ok`, and `menu_safe`. Then verify the app's relevant live API behavior, console, and desktop/mobile rendering. Report separately what was checked locally, remotely, and visually. Never treat a hash match as proof that a Python process restarted or that a dataset reconciled.

## Transfer limits and download streaming

Download streaming is a **response-side** concern in `modules/container_proxy.py`; it is separate from upload chunk concurrency. The local proxy's `_is_download_response` returns true when at least one condition holds:

| Condition | Exact local behavior |
| --- | --- |
| Attachment header | `Content-Disposition` contains `attachment` |
| File MIME | `Content-Type` contains `application/octet-stream`, `application/zip`, `application/pdf`, `application/x-7z-compressed`, `application/vnd.`, or `text/csv` |
| Transfer-like URL | Path contains `/download`, `/export`, `/attachment`, `/blob`, or `/files/`, and its content type starts with neither `text/html` nor `application/json` |
| Large known response | `Content-Length > 8 * 1024 * 1024` with the same HTML/JSON exclusion |

Ordinary HTML/JSON responses normally follow the buffered rewrite/RLS/cache path. An attachment header still takes priority even for those types. Do not assume that every `image/*`, every JSON-like MIME, or every text response is automatically classified the same way. Inspect the actual response headers and target platform code when diagnosing a transfer.

Stream bodies are forwarded in 64 KiB chunks instead of buffering them through `response.content`. Each workspace has a semaphore of concurrent streams:

| Environment setting | Local default | Meaning |
| --- | --- | --- |
| `PROXY_STREAM_MAX_INFLIGHT_PER_CONTAINER` | `8` | Simultaneous transfer slots for one workspace |
| `PROXY_STREAM_LEASE_GRACE_SECONDS` | `120` seconds | Lease expiration guard |
| `PROXY_STREAM_LEASE_SWEEP_SECONDS` | `10` seconds | Background sweep interval |

The response iterator releases its slot in `finally`; `call_on_close` also releases when the client aborts, and the guardian reaps expired leases. A slot cannot be assumed permanently leaked just because a browser cancelled a download.

When no slot can be acquired, the proxy returns `429` with `Retry-After: 2`, `Cache-Control: no-store`, and the message `O limite de transferências deste workspace foi atingido. Tente novamente em alguns segundos.` Stream responses carry `X-Rejoin-Proxy-Transfer: stream` and no-store cache headers. Deployments behind the runtime gateway may additionally carry `X-Rejoin-Gateway` and `X-Rejoin-Gateway-Upstream`; those identify gateway routing and do not themselves prove a file hash or successful app computation.

Serve files with a correct MIME and `Content-Disposition`, using Flask `send_file`/`send_from_directory` or the equivalent. Test the actual endpoint with an authenticated session. Handle `429` by respecting retry hints and rechecking active transfers; if it remains stuck beyond the configured lease/sweep window, inspect runtime logs and use an authorized isolated recovery for the affected workspace.

Download access has a separate RLS guard. The proxy allows the current Master/Principal administrative export path; other users require a valid allowed active page/workspace and cannot receive raw protected-page downloads. Missing or unverifiable page/RLS context fails with `403`. Do not remove RLS checks or stream unfiltered protected datasets to work around that result.

The transfer-slot `429` above is emitted by the stream semaphore, not subscription status. A `trial_undefined` subscription result neither explains that specific limit nor authorizes ignoring an access error.