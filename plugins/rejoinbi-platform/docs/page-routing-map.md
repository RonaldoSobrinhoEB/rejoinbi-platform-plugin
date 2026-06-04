# Rejoin BI Page Routing Map

This map documents the platform behavior the plugin must respect when creating dashboard pages.

## Source Files Checked

- `static/js/client_pages_config.js`
  - `isClientContainerPage(pageId)` treats a page as a workspace/client page when `/plataforma/api/accessible-pages` returns an `arquivo`.
  - `getClientRoute(pageId)` uses `rota` when it is configured; otherwise it falls back to the page `arquivo` without `.html`.
  - `getClientContainer(pageId)` first uses `container_name`. If it is missing, it tries `window.containers` by `container_id`. If that array has not loaded yet, it falls back to `container_<id>`.
- `modules/auth.py`
  - `/plataforma/api/accessible-pages` returns the authenticated menu tree and calls `get_accessible_pages(...)`.
- `modules/utils.py`
  - `get_accessible_pages(...)` builds every page with `container_id`, `container_name`, `rota`, and `arquivo`.
  - `resolve_client_route_for_page(container_id, arquivo, rota)` decides the effective client route from explicit `rota` and file path.
- `modules/paginas_admin.py`
  - Custom routes are ASCII-only paths without `.html`, URLs, or traversal.
  - Page IDs are slugified from the creation name, so the plugin creates with a technical id first and then restores the visible display name.
- `app.py`
  - `/plataforma/<container_name>/client/<client_path>` resolves `container_name` through `client_containers.name`.
  - If the browser opens `/plataforma/container_2/client/...`, the route can 404 even when the page exists, because `container_2` is only a fallback label and not necessarily the real container name.

## Required Contract

Each manifest page must keep these fields separate:

- `id`: technical ASCII slug, globally stable, usually prefixed by the workspace/client slug.
- `name`: visible menu name, localized and allowed to contain accents, such as `Visão Geral`.
- `file`: actual HTML file in the uploaded workspace, such as `visao-geral.html`.
- `route`: ASCII platform route. For static dashboards, prefer the file path without `.html`, such as `visao-geral`.

BI Studio exports follow the same contract. The tab name may be `Visão Geral`, but the published template, static folders, manifest slug, page `arquivo`, and page `rota` should be `visao-geral`. If the BI export contains a slug such as `visão-geral`, normalize it with `bi-normalize-export` before upload.

The plugin must not report production ready until all client pages are present in `/plataforma/api/accessible-pages` with:

- The expected page id.
- The expected visible name when the page has just been renamed after technical creation.
- `container_id`.
- `container_name`.
- A browser route that returns HTTP 200 through `/plataforma/<container_name>/client/<route>?pagina_id=<page_id>`.

## Failure Mode From The Console Logs

The failing logs show:

- The page exists and has `arquivo`, so the platform identifies it as a client page.
- `container_id` is present.
- `container_name` is missing from `accessible-pages`.
- `window.containers` is still empty when the route helper runs.
- The browser falls back to `/plataforma/container_2/client/...`.
- The server cannot resolve `container_2` as the real `client_containers.name`, so the iframe returns 404.

This is why a route can appear to work after a delay but fail immediately through the menu.

## Plugin Safeguards

- `deploy-manifest` refreshes menu caches and waits for page readiness after creating pages.
- `smoke-pages` now fails with exit code 1 if `container_name`, `browser_route_ok`, or `menu_safe` is false.
- Mutating commands require `--tenant subdomain.rejoinbi.com.br` unless `--use-active-tenant` is explicitly passed.
- `validate-app` warns when pt-BR display names look unaccented and warns when a static page route differs from the HTML file route.
- `bi-normalize-export` normalizes extracted BI Studio export folders to ASCII technical slugs and adds a parquet engine dependency when needed.
