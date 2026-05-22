# Rejoin BI Platform Codex Plugin Marketplace

Public Codex plugin marketplace for the Rejoin BI Platform plugin.

## Add In Codex

Use the "Adicionar marketplace" dialog with:

- Origem: this GitHub repository URL
- Referencia do Git: `main`
- Caminhos esparsos: `plugins/codex`

Codex will find `plugins/codex/marketplace.json` and install the plugin from `plugins/codex/plugins/rejoinbi-platform`.

## Plugin

`rejoinbi-platform` helps Codex connect to Rejoin BI tenants under `rejoinbi.com.br`, inspect workspaces, upload static or Flask dashboard projects, publish BI/ECharts projects, manage platform pages, and preview destructive cleanup before deletion.

Important: dashboards should be one standalone page file per Rejoin BI page. Rejoin BI already manages menus, hierarchy, routes, icons, permissions, and active state through Gerenciar Paginas.

## Production Safety

Workspace and page deletion commands are dry-run by default. They print the resolved target, parent-child-grandchild page tree, linked fictitious/hierarchy references, and exact confirmation flags required before any deletion occurs.

## Local Package

The shareable local package is also generated at:

```text
C:\Users\RonaldoSobrinho\Downloads\plugin\rejoinbi-platform
C:\Users\RonaldoSobrinho\Downloads\plugin\rejoinbi-platform.zip
```
