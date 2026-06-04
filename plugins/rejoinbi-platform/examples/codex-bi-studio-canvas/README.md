# Codex BI Studio Canvas

Professional BI Studio/Data Engine canvas example for Codex agents.

Use this example when the user asks for a BI Studio dashboard, canvas dashboard, Data Engine powered BI project, or a polished multi-page executive cockpit. The goal is to avoid generic dashboard blocks and force a production-grade design process.

## Design Standard

Before creating tabs or saving a layout, define:

- Audience: executive, tactical, operational, or analyst.
- Business questions: what decision each tab answers.
- Metric model: fact grain, joins, source fields, denominators, dimensions, derived metrics, trend windows, benchmarks, outlier rules, and risk flags.
- Page architecture: one Rejoin BI page per BI Studio tab after export; no dashboard-internal menu.
- Responsive targets: desktop canvas around `1600x1080`, mobile canvas around `430x940`.
- Visual identity: Rejoin BI dark base, blue/teal brand accents, semantic green/amber/red, 8px radius, no decorative noise.
- Contrast: near-white primary text on dark backgrounds, legible muted text, clear chart/table labels, no gray-on-dark haze, no teal-on-blue text, no red/green-only communication.
- UI/UX hierarchy: executive intent first, then headline KPIs, diagnostics, ranked exceptions, recommendations, and filters. Dense information is allowed, but spacing and reading order must remain calm.
- Data storytelling: each visual must answer trend, comparison, composition, distribution, ranking, risk, or relationship. Remove visuals that only decorate or repeat a KPI.

## Recommended Tab Set

- `Visão Executiva`: KPIs, trend, risk table, filters.
- `Receita e Margem`: product/channel profitability, margin waterfall, ARPU.
- `Clientes e Churn`: active base, churn, NPS, retention risk.
- `Rede e SLA`: uptime, SLA gap, tickets, operational health.

Visible tab/page names may contain accents. Technical slugs, exported filenames, page `route`, and page `file` must be ASCII after `bi-normalize-export`.

## Production Template Reference

`production-template/` contains a screenshot-validated dashboard layer from a real QA run:

- `templates/*.html`: one standalone platform page per route, plus `index.html` as a safe default shell.
- `static/codex/canvas-pro.css`: Rejoin BI dark visual system, responsive KPI grid, panels, tables, and mobile rules.
- `static/codex/canvas-pro.js`: compact telecom decision model with real-looking relationships across revenue, margin, churn, NPS, tickets, risk, and SLA.

Use this as a fallback reference when the BI Studio export renderer publishes raw placeholders or ignores the intended canvas schema. The correct fix is still to make BI Studio/Data Engine produce the right dashboard, but production upload must never ship placeholder templates.

## Workflow

```powershell
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\scripts\rejoinbi.py studio-inventory --output .\inventory-before.json
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-create-project --name "Canvas Executivo Pro"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-init-canvas --project-id "Canvas Executivo Pro"
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-create-tab --project-id "Canvas Executivo Pro" --name "Visão Executiva" --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine repository-upload --project-id "Canvas Executivo Pro" --file .\data\telecom.csv --folder canvas-pro --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine create-dataset --data-file .\payloads\create-dataset.json --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br data-engine finalize-dataset --data-file .\payloads\finalize-dataset.json --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-save-theme --project-id "Canvas Executivo Pro" --data-file .\theme-canvas-pro.json --yes
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br bi-save-layout --project-id "Canvas Executivo Pro" --tab "Visão Executiva" --data-file .\layout-visao-executiva.example.json --yes
python .\scripts\rejoinbi.py bi-export --project-id "Canvas Executivo Pro" --output .\canvas-export.zip
Expand-Archive .\canvas-export.zip .\canvas-export
python .\scripts\rejoinbi.py bi-normalize-export --path .\canvas-export --remove-old
python .\scripts\rejoinbi.py validate-app --manifest .\canvas-export\rejoinbi-app.json --strict
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br deploy-manifest --manifest .\canvas-export\rejoinbi-app.json --create-workspace --replace-pages
python .\scripts\rejoinbi.py --tenant subdomain.rejoinbi.com.br smoke-pages --manifest .\canvas-export\rejoinbi-app.json
```

## Production Checks

- Data Engine dataset status is `completed`.
- Exported `requirements.txt` includes `pyarrow>=16.0.0` when parquet exists.
- `validate-app --strict` has zero warnings.
- `smoke-pages` returns `html_ok`, `browser_route_ok`, and `menu_safe` true for every page.
- Authenticated desktop and mobile screenshots show polished Rejoin BI styling, real KPIs, charts/tables rendered, readable contrast, no clipped text, no placeholder labels, no generic `123`, no `Sem dados`, no console errors, and no horizontal overflow.
- `page-maintenance audit-encoding --strict` reports no encoding issues.
- Workspace logs show the app running and materialized data loaded.
