# Codex Marketplace Submission

This repository is structured as a Codex marketplace. The Codex marketplace manifest lives at `.agents/plugins/marketplace.json`, and the Rejoin BI plugin lives under `plugins/rejoinbi`.

Use these settings when submitting:

- Artifact type: `MARKETPLACE`
- GitHub repository: `RonaldoSobrinhoEB/rejoinbi-platform-plugin`
- Git reference: `main`
- Sparse path: empty

The required marketplace manifest is available at:

```text
.agents/plugins/marketplace.json
```

A root `marketplace.json` mirror is kept for readability.

The plugin manifest is available at:

```text
plugins/rejoinbi/.codex-plugin/plugin.json
```

## Compatibility checklist

- `.agents/plugins/marketplace.json` exists.
- `.agents/plugins/marketplace.json` points to `./plugins/rejoinbi`.
- Root `marketplace.json` mirror exists.
- `plugins/rejoinbi/.codex-plugin/plugin.json` exists.
- Manifest uses strict semantic versioning.
- Manifest includes `homepage`, `repository`, `license`, `keywords`, and interface metadata aligned with Codex plugin conventions.
- `defaultPrompt` contains three concise prompts.
- Icon and logo use the real Rejoin BI PNG icon under `assets/app-icon.png`.
- No SVG fallback is shipped for the marketplace icon.
- The plugin validates with `plugin-creator/scripts/validate_plugin.py`.

## Local validation

```powershell
python "$HOME\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .\plugins\rejoinbi
python -m py_compile .\plugins\rejoinbi\scripts\rejoinbi.py
python .\plugins\rejoinbi\scripts\rejoinbi.py studio-inventory --help
```
