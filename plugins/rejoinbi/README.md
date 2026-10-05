# Rejoin BI Plugin

Codex plugin for Rejoin BI platforms under `rejoinbi.com.br`. It connects to a specific platform, operates workspaces and platform-managed pages, transfers project files, manages persistent databases, and provides scoped administration commands.

## Start here

Read [skills/rejoinbi-platform/SKILL.md](skills/rejoinbi-platform/SKILL.md) first. Use the detailed guide for the task you are performing:

| Task or uncertainty | Guide |
| --- | --- |
| Understand the platform, translate a request into commands, or decide what proves completion | [Agent operating playbook](docs/agent-operating-playbook.md) |
| Upload a file, preserve `services/` or another folder, inspect a local upload plan, or verify the exact remote destination | [Upload path contract](docs/upload-path-contract.md) |
| Choose full-project versus changed-files deployment, build static/Flask projects, or investigate transfer limits | [Workspace compatibility](docs/workspace-compatibility.md) |
| Understand `id`, visible `name`, HTML `file`, browser `route`, menu readiness, or page smoke output | [Page routing map](docs/page-routing-map.md) |
| Determine a command's operation scope or the extra identity confirmations | [Command scope map](docs/command-scope-map.md) |
| Branding, users, messaging, RLS, AI, audit, infrastructure, or database-slot recovery | [Admin configuration map](docs/admin-configuration-map.md) |
| Delete a workspace/page/file and prove the target is gone | [Destructive operations](docs/destructive-operations.md) |
| Managed SQLite schema, migration, external API tokens, batching, or CSV transfers | [Managed database API](docs/managed-database-external-api.md) |
| Keep sessions and targets separate across platform subdomains | [Multiple subdomains](docs/multi-subdomain-conversations.md) |
| Package structure, version checks, and Marketplace submission | [Marketplace submission](docs/MARKETPLACE_SUBMISSION.md) |

Run the following examples **from this package's root**, where `scripts/rejoinbi.py` exists. Replace the example platform and workspace with the resolved real target. `--tenant` is a global option before the command; `--operation-scope` belongs after the command. Do not guess an installed path in another user's home folder.

~~~powershell
# Local inspection; no login or remote upload.
python .\scripts\rejoinbi.py --help
python .\scripts\rejoinbi.py validate-app --manifest .\examples\codex-advanced-suite\rejoinbi-app.json

# Authenticate only to the chosen platform; opens the local login wizard if needed.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure

# Read the chosen platform and one workspace's repository.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspaceall --operation-scope workspace
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-file list --workspace 12 --operation-scope workspace
~~~

The local login wizard collects credentials and any required PIN in the browser. Never infer an administrative profile from the absence of a PIN prompt; the authenticated platform identity determines the profile. The plugin permits `Administrador Principal`, `Master`, and `Administrador` for ordinary administration, subject to the platform's endpoint permissions. It rejects recognized standard users unless an explicitly requested negative test uses `--allow-standard`.

## Prevent a wrong upload destination

A local filename is not a remote path. A file such as `C:\projects\dashboard\services\production_payload_disk_cache.py` must remain `services/production_payload_disk_cache.py` inside the workspace when that is the intended project-relative location.

~~~powershell
# First inspect the complete local source -> remote target plan.
python .\scripts\rejoinbi.py upload-files --workspace 12 --source-root C:\projects\dashboard --files C:\projects\dashboard\services\production_payload_disk_cache.py --dry-run --plan-output .\upload-plan.json --operation-scope upload

# After checking the plan and the existing authorization, send those same files.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br upload-files --workspace 12 --source-root C:\projects\dashboard --files C:\projects\dashboard\services\production_payload_disk_cache.py --operation-scope upload

# Read the exact intended path and compare its returned sha256 to the local plan.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br workspace-file read --workspace 12 --path services/production_payload_disk_cache.py --operation-scope workspace
~~~

The dry-run plan contains `files[].source`, `target`, `size`, and `sha256`. Review every destination before sending. `--source-root` is the project root, not the `services` folder. Alternatively use an explicit `--target-path`, `--folder`, or `--map` as defined in the [upload path contract](docs/upload-path-contract.md). `--preserve-paths` alone does not discover the intended project root. A nested file sent to the workspace root requires the deliberate `--allow-root-drop` exception.

An accepted upload is only transfer evidence. Completion requires successful apply/publication and a read-back of the exact remote path with the expected hash. A different root-level file with the same basename does not prove that the intended file changed.

## Deployment and page rules

Choose `--upload-mode full` or `--upload-mode changed-files` from the requester's existing instructions. Ask once only if that consequential choice is still unresolved. Full mode publishes a complete tree, versions/replaces the active `app/` tree, and configures startup/pages; changed-files mode applies only the explicitly listed files and preserves unselected files. It does not restart, reselect the entrypoint, or synchronize pages unless those additional actions are explicitly selected.

~~~powershell
# Local full-deployment preview for the included demonstration project.
python .\scripts\rejoinbi.py deploy-manifest --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --upload-mode full --dry-run --plan-output .\deploy-plan.json --operation-scope deployment

# Use only when this complete-project publication is authorized.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --upload-mode full --operation-scope deployment

# Validate actual menu/capture/browser paths after publication.
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\examples\codex-advanced-suite\rejoinbi-app.json --operation-scope pages
~~~

Build one standalone HTML file per platform-managed page. Gerenciar Páginas owns the page hierarchy, menu, permissions, icons, and routes. Keep technical IDs/routes/filenames ASCII; keep visible labels correctly localized. `smoke-pages` must report `success: true`, `readiness.success: true`, and true `html_ok`, `browser_route_ok`, and `menu_safe` gates for each page. It performs authenticated HTTP checks; browser rendering, console errors, and responsive screenshots require their own verification.

Selected project files are not silently filtered by name or extension. Local databases and recognized data artifacts require specific review and `--allow-database-files` / `--allow-data-files`; paths outside the selected project and upload control metadata are rejected. The compatibility `--exclude`/`upload.exclude` values are ignored: prepare the exact complete project folder or select exact files. See the detailed guides before overwriting production data.

## Scope boundaries

Operational commands require their exact `--operation-scope`; local tools and authentication/session commands are deliberate exceptions. A valid administrator login does not authorize access to users, direct permissions, or permission groups. Identity reads require an explicit identity request plus `--operation-scope identity --identity-scope`. Identity writes require `--yes` and the applicable resolved-target confirmations. E-mail/WhatsApp contact groups use `messaging`, not the permission-group domain. Raw API access remains path-confirmed and scope-derived.

Retain authorization already given for the same purpose and target. An instruction to repair one dashboard does not expand into unrelated identity administration or deletion. Use [command-scope-map.md](docs/command-scope-map.md) for the exact parser contract and [admin-configuration-map.md](docs/admin-configuration-map.md) for supported operations.

## Package and sharing

The repository root is the plugin artifact: `.codex-plugin/plugin.json`, `skills/`, `scripts/`, `docs/`, `examples/`, and the official `assets/app-icon.png`. Submit artifact type `PLUGIN`, branch `main`, sparse path empty or `.`; see the Marketplace guide for release validation.

~~~powershell
python .\scripts\rejoinbi.py export-package
~~~

The default export creates `%USERPROFILE%\Downloads\plugin\rejoinbi-platform`, its ZIP, and `INSTALL.md`. Local session folders are omitted from the share package. A project upload has a different file-selection contract; do not confuse package-export hygiene with automatic filtering of dashboard files.
