# Codex Marketplace Submission

This repository is structured as a Codex marketplace. The marketplace manifest lives at the repository root, and the Rejoin BI plugin lives under `plugins/rejoinbi`.

Use these settings when submitting:

- Artifact type: `MARKETPLACE`
- GitHub repository: `RonaldoSobrinhoEB/rejoinbi-platform-plugin`
- Git reference: `main`
- Sparse path: empty

The required marketplace manifest is available at:

```text
marketplace.json
```

The plugin manifest is available at:

```text
plugins/rejoinbi/.codex-plugin/plugin.json
```

## Compatibility checklist

- Root `marketplace.json` exists.
- `marketplace.json` points to `./plugins/rejoinbi`.
- `plugins/rejoinbi/.codex-plugin/plugin.json` exists.
- Manifest uses strict semantic versioning.
- Manifest includes `homepage`, `repository`, `license`, `keywords`, and interface metadata aligned with Codex plugin conventions.
- `defaultPrompt` contains three concise prompts.
- Icon and logo use text SVG under `assets/app-icon.svg`.
- No binary image assets are required for marketplace recognition.
- The plugin validates with `plugin-creator/scripts/validate_plugin.py`.

## Local validation

```powershell
python "$HOME\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .\plugins\rejoinbi
python -m py_compile .\plugins\rejoinbi\scripts\rejoinbi.py
python .\plugins\rejoinbi\scripts\rejoinbi.py studio-inventory --help
```
