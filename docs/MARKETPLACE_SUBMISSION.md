# Codex Plugin Submission

This repository root is the plugin artifact. `plugin.json` is the portable Agent Plugins
manifest and `.codex-plugin/plugin.json` is the Codex compatibility overlay. Both declare
the same identity, interface metadata, and `requires_local_executor`; keep them in sync.

The plugin is skills-only: it ships one skill and a local Python CLI, hosts no server, and
runs only on the user's machine. That is why the manifests set `requires_local_executor`,
which lists the plugin as Desktop only in the directory.

## Official directory submission

1. Confirm a verified developer identity in the OpenAI Platform organization settings; the
   submission form does not open without it.
2. Build the submission ZIP so its root contains exactly one `rejoinbi/` folder.
3. Upload it in the plugin submission portal, resolve the automated findings, submit for
   review, then publish when approved.

Skills-only plugins do not need MCP review cases, a demo recording, or screenshots.

## Local validation

```powershell
python -B -c "import json,pathlib;[json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('plugin.json','.codex-plugin/plugin.json')]"
python -B -m py_compile .\scripts\rejoinbi.py
python -B -m pytest .\tests -q
```

## Git marketplace

`.agents/plugins/marketplace.json` exposes this same repository root as the `rejoinbi`
plugin, so no second copy of the plugin exists in the tree. Add it with:

```powershell
codex plugin marketplace add RonaldoSobrinhoEB/rejoinbi-platform-plugin --ref main
```