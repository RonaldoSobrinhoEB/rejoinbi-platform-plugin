# Rejoin BI

Public, read-only Rejoin BI release assistant for ChatGPT and Codex.

The plugin connects to the public MCP endpoint at `https://rejoinbi.com.br/mcp` and helps validate Rejoin BI plugin packages and release plans before publication. It does **not** sign into a Rejoin BI platform, access workspace or customer data, deploy dashboards, manage users, or change any platform state.

## What it can do

- Validate a `rejoinbi-app.json` manifest (`rejoinbi_validate_app_manifest`).
- Check whether upload paths stay project-relative or are unsafe (`rejoinbi_check_upload_paths`).
- Recommend a full versus changed-files deployment plan, or tell you when the choice is unclear (`rejoinbi_choose_deployment_mode`).
- Map an error or log excerpt to likely causes and safe checks (`rejoinbi_troubleshoot_error`).
- Return a release-readiness checklist for `upload`, `deployment`, `pages`, or `managed-database` work (`rejoinbi_release_readiness_checklist`).
- Return public product metadata and scope information (`rejoinbi_plugin_info`).

## What it cannot do

This package is validation-only. It never asks for an e-mail, password, PIN, token, session cookie, or platform address. It cannot upload files, publish pages, deploy dashboards, query managed databases, or administer users and permissions. For Rejoin BI platform administration, use the desktop Rejoin BI plugin with your own authorized account.

## Links

- Website: https://rejoinbi.com.br
- Privacy policy: https://rejoinbi.com.br/privacy
- Terms of service: https://rejoinbi.com.br/terms
- Support: https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin/issues

## Verification

The public endpoint is anonymous and read-only. `GET /healthz` returns `{"status":"ok"}` and `POST /mcp` implements Streamable-HTTP JSON-RPC methods including `initialize`, `tools/list`, and `tools/call`. The endpoint returns no customer data and performs no writes.
