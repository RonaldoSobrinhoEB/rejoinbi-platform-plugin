# Codex Marketplace Submission

This repository is structured as a root Codex plugin artifact.

Use these settings when submitting:

- Artifact type: `PLUGIN`
- GitHub repository: `RonaldoSobrinhoEB/rejoinbi-platform-plugin`
- Git reference: `main`
- Sparse path: empty or `.`

The required plugin manifest is available at:

```text
.codex-plugin/plugin.json
```

The plugin intentionally avoids duplicated marketplace wrappers such as `.agents/`, `plugins/`, and `marketplace.json` so scanners can evaluate the artifact directly.

## Compatibility checklist

- Root `.codex-plugin/plugin.json` exists.
- Manifest uses strict semantic versioning.
- Manifest includes `homepage`, `repository`, `license`, `keywords`, and interface metadata aligned with Codex plugin conventions.
- `defaultPrompt` contains three concise prompts.
- Icon and logo use the Rejoin BI platform icon under `assets/app-icon.png`.
- Keep this image asset included in the plugin archive so Codex displays the correct brand icon.
- The plugin validates with `plugin-creator/scripts/validate_plugin.py`.

## Local validation

```powershell
python "$HOME\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
python -m py_compile .\scripts\rejoinbi.py
python .\scripts\rejoinbi.py studio-inventory --help
```
