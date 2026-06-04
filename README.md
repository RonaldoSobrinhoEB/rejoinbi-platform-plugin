# Rejoin BI Marketplace

Codex marketplace for Rejoin BI plugins.

## Install In Codex

Use the Codex "Adicionar marketplace" dialog with:

- Origem: `https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin.git`
- Referencia do Git: `main`
- Caminhos esparsos: leave empty

The Codex marketplace manifest is:

```text
.agents/plugins/marketplace.json
```

A root `marketplace.json` mirror is also kept for readability. The plugin source is:

```text
plugins/rejoinbi
```

The plugin itself keeps its Codex manifest at:

```text
plugins/rejoinbi/.codex-plugin/plugin.json
```
