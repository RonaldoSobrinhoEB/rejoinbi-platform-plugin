# Codex Plugin Submission

This repository root is the plugin artifact. `plugin.json` is the portable Agent Plugins
manifest, `.codex-plugin/plugin.json` is the Codex compatibility overlay, both point to the
single `.mcp.json`, and `server/rejoinbi_mcp.py` implements the local stdio server.
Keep the two manifests in sync with that one MCP file.

The plugin is desktop-only: it ships one skill, a local Python CLI, and a stdio MCP server
that runs on the user's machine. It hosts no server and sends nothing outside the Rejoin BI
platform address the user selects. Both manifests set `requires_local_executor`, which lists
the plugin as Desktop only in the directory.

The portal rejects new skills-only submissions, and an existing skills-only draft cannot
gain an MCP server. Upload a local MCP package from the first version.

## Official directory submission

1. Confirm a verified developer identity in the OpenAI Platform organization settings; the
   submission form does not open without it.
2. Ask the OpenAI representative to allowlist the submitting organization for local MCP
   submissions, then wait for confirmation. There is no self-service path.
3. Build the submission ZIP so its root contains exactly one `rejoinbi/` folder.
4. Upload it in the plugin submission portal. Per the desktop-only instructions, choose
   **Skills only** and upload the ZIP that already contains the local MCP configuration.
5. Resolve the automated findings, submit for review, then publish when approved.

Local MCP plugins do not need MCP app review cases, a demo recording, or screenshots.

## Local validation

```powershell
python -B -c "import json,pathlib;[json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('plugin.json','.codex-plugin/plugin.json','.mcp.json')]"
python -B -m py_compile .\scripts\rejoinbi.py .\server\rejoinbi_mcp.py
python -B -m pytest .\tests -q

Validate the MCP handshake before uploading: `initialize`, `tools/list`, then one
`tools/call` for `rejoinbi_doctor`, which reports whether `requests` is available.
```

## Git marketplace

`.agents/plugins/marketplace.json` exposes this same repository root as the `rejoinbi`
plugin, so no second copy of the plugin exists in the tree. Add it with:

```powershell
codex plugin marketplace add RonaldoSobrinhoEB/rejoinbi-platform-plugin --ref main
```
