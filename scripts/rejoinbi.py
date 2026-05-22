#!/usr/bin/env python3
"""Rejoin BI Platform helper CLI.

This client talks to the existing Flask API exposed by Rejoin BI tenants.
It stores cookies after login but never persists passwords or PIN values.
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import getpass
import html
import json
import mimetypes
import os
import re
import secrets
import shutil
import sys
import threading
import time
import unicodedata
import zipfile
from contextlib import ExitStack
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse
import webbrowser

try:
    import requests
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("The 'requests' package is required. Install it with: python -m pip install requests") from exc


APP_HOME = Path(os.environ.get("REJOINBI_PLUGIN_HOME") or (Path.home() / ".rejoinbi-platform"))
SESSION_DIR = APP_HOME / "sessions"
CONFIG_PATH = APP_HOME / "config.json"
DEFAULT_DOMAIN = "rejoinbi.com.br"
DEFAULT_TIMEOUT = 120
SAFE_PROFILE_COMMANDS = {"auth", "browser-login", "connect", "ensure", "ensure-connected", "login", "status", "tenant"}
ALLOWED_PROFILE_KEYS = {"administrador principal", "master", "administrador"}
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_PATH_NAMES = {
    ".aws",
    ".azure",
    ".env",
    ".gcloud",
    ".gnupg",
    ".kube",
    ".rejoinbi-platform",
    ".ssh",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "secrets",
}
SENSITIVE_PATH_PATTERNS = (
    ".env*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.ppk",
    "*.crt",
    "*.csr",
    "*.kubeconfig",
    "*credential*",
    "*password*",
    "*secret*",
    "*token*",
)

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MUTATING_COMMANDS_REQUIRING_EXPLICIT_TENANT = {
    "api-send",
    "assign-user-group",
    "cleanup-ai-config",
    "create-announcement",
    "create-group",
    "create-page",
    "create-user",
    "create-workspace",
    "delete-ai-config",
    "delete-announcement",
    "bi-create-tab",
    "delete-group",
    "bi-delete-tab",
    "bi-delete-theme",
    "delete-page",
    "delete-user",
    "delete-workspace",
    "deploy-manifest",
    "bi-create-project",
    "bi-duplicate-tab",
    "bi-init-canvas",
    "bi-rename-tab",
    "bi-reorder-tabs",
    "bi-save-layout",
    "bi-save-theme",
    "menu-maintenance",
    "page-maintenance",
    "publish-bi",
    "recalculate-permissions",
    "restore-platform-config-defaults",
    "restore-platform-branding",
    "rls",
    "set-ai-config",
    "set-page-order",
    "set-platform-branding",
    "set-platform-config",
    "set-workspace-password",
    "set-user-password",
    "set-user-permissions",
    "update-group",
    "update-page",
    "update-user",
    "update-workspace",
    "upload-files",
    "upload-folder-select",
    "upload-zip-select",
    "workspace-build",
    "workspace-delete",
    "workspace-input",
    "workspace-notification",
    "workspace-restart",
    "workspace-schedule",
    "workspace-start",
    "workspace-stop",
    "workspace-stop-all",
    "workspace-version-delete",
    "workspace-version-restore",
}
FICTITIOUS_PAGE_PREFIXES = ("avo-ficticio-", "pai-ficticio-", "filho-ficticio-")
DELETE_PAGE_REFERENCE_FIELDS = ("pai", "ficticio")
DELETE_WORKSPACE_REFERENCE_FIELDS = ("pai", "pai_real", "pai_ficticio", "ficticio", "hierarquia_id")
RESERVED_WORKSPACE_NAMES = {
    "admin",
    "administrador",
    "default",
    "home",
    "master",
    "menu",
    "padrao",
    "platform",
    "plataforma",
    "principal",
    "public",
    "root",
    "sistema",
    "system",
}
WORKSPACE_PASSWORD_FIELDS = (
    "has_password",
    "tem_senha",
    "password_protected",
    "senha_protegida",
    "requires_password",
    "require_password",
    "password_required",
    "protected",
    "locked",
    "is_locked",
)
WORKSPACE_PASSWORD_VALUE_FIELDS = (
    "password",
    "senha",
    "workspace_password",
    "container_password",
    "password_hash",
    "senha_hash",
)
DATA_ENGINE_PROJECT_ACTIONS = {
    "session-status",
    "db-connections",
    "create-db-connection",
    "test-db-connection",
    "query-preview",
    "query-materialize",
    "ai-sql-query",
    "repository-upload",
    "repository-list",
    "repository-content",
    "repository-global-context",
    "repository-execute-global-context",
    "repository-manual-table",
    "create-manual-table",
    "create-folder",
    "move",
    "order",
    "delete",
    "datasets-list",
    "create-dataset",
    "duplicate-dataset",
    "delete-dataset",
    "link-dataset",
    "unlink-dataset",
    "list-files",
    "preview-file",
    "dataset-get",
    "save-column-types",
    "save-notebook-state",
    "finalize-dataset",
    "toggle-visibility",
    "execute-code",
    "agent-mine",
    "chat",
    "load-chat",
    "cancel-execution",
    "reset-session",
    "remove-variable",
    "terminal-command",
    "terminal-auto-install",
}

PT_BR_WORD_ACCENT_FIXES = {
    "acao": "ação",
    "acoes": "ações",
    "analise": "análise",
    "atencao": "atenção",
    "automacao": "automação",
    "avaliacao": "avaliação",
    "composicao": "composição",
    "configuracao": "configuração",
    "configuracoes": "configurações",
    "conversao": "conversão",
    "evolucao": "evolução",
    "gestao": "gestão",
    "metricas": "métricas",
    "operacao": "operação",
    "operacoes": "operações",
    "producao": "produção",
    "satisfacao": "satisfação",
    "usuarios": "usuários",
    "visao": "visão",
    "visoes": "visões",
}


class RejoinBIError(RuntimeError):
    pass


@lru_cache(maxsize=8)
def plugin_asset_data_uri(name: str) -> str:
    path = PLUGIN_ROOT / "assets" / name
    try:
        if not path.is_file():
            return ""
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


def auth_error_messages(error: str) -> tuple[str, str]:
    clean = " ".join(str(error or "").split())
    if not clean:
        return "", ""
    lower = clean.lower()
    if "http 401" in lower or "email ou senha" in lower or "invalid" in lower:
        return "Email ou senha invalidos.", "Confira as credenciais do tenant e tente novamente."
    if "pin" in lower:
        return "Nao foi possivel validar o PIN.", "Confira o codigo informado e tente novamente."
    if "perfil" in lower or "administrador" in lower or "master" in lower:
        return "Perfil sem permissao para este plugin.", clean
    if "timed out" in lower or "timeout" in lower:
        return "Tempo de conexao esgotado.", "Abra esta janela novamente pelo Codex e conclua o login."
    return "Nao foi possivel concluir a conexao.", clean


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def is_loopback_host(host: str) -> bool:
    normalized = str(host or "").split(":", 1)[0].strip("[]").lower()
    return normalized in {"localhost", "127.0.0.1", "::1"}


def is_allowed_tenant_host(host: str) -> bool:
    raw = str(host or "").strip()
    if is_loopback_host(raw):
        return True
    normalized = raw.split("@")[-1].split(":", 1)[0].strip("[]").lower()
    return normalized == DEFAULT_DOMAIN or normalized.endswith(f".{DEFAULT_DOMAIN}")


def sensitive_path_reason(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    for part in parts:
        if part in SENSITIVE_PATH_NAMES:
            return f"sensitive path component '{part}'"
    name = path.name.lower()
    for pattern in SENSITIVE_PATH_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return f"sensitive filename pattern '{pattern}'"
    return ""


def clean_base_url(value: str) -> str:
    raw = str(value or "").strip().strip('"').strip("'")
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise RejoinBIError(f"Invalid base URL: {value}")
    host = parsed.hostname or parsed.netloc
    if parsed.scheme != "https" and not is_loopback_host(host):
        raise RejoinBIError("Refusing non-HTTPS tenant URL outside localhost.")
    if not is_allowed_tenant_host(host) and os.environ.get("REJOINBI_ALLOW_EXTERNAL_BASE_URL") != "1":
        raise RejoinBIError(
            f"Refusing tenant host outside {DEFAULT_DOMAIN}: {host}. "
            "Set REJOINBI_ALLOW_EXTERNAL_BASE_URL=1 only for trusted local development."
        )
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def resolve_base_url(subdomain: str = "", domain: str = DEFAULT_DOMAIN, base_url: str = "") -> str:
    if base_url:
        return clean_base_url(base_url)

    sub = str(subdomain or "").strip().strip('"').strip("'")
    if not sub:
        config = read_json(CONFIG_PATH, {})
        active = str(config.get("active_base_url") or "").strip()
        if active:
            return clean_base_url(active)
        raise RejoinBIError("No tenant selected. Pass --tenant subdomain.rejoinbi.com.br or run ensure first.")

    if re.match(r"^https?://", sub, flags=re.I):
        return clean_base_url(sub)

    sub = sub.replace("https://", "").replace("http://", "").rstrip("/")
    if "." in sub:
        return clean_base_url(sub)

    base_domain = str(domain or DEFAULT_DOMAIN).replace("https://", "").replace("http://", "").strip("/")
    return clean_base_url(f"{sub}.{base_domain}")


def tenant_host_from_base_url(base_url: str) -> str:
    return urlparse(clean_base_url(base_url)).netloc


def args_have_explicit_tenant(args: argparse.Namespace) -> bool:
    return bool(
        str(getattr(args, "tenant", "") or "").strip()
        or str(getattr(args, "subdomain", "") or "").strip()
        or str(getattr(args, "base_url", "") or "").strip()
    )


def command_requires_explicit_tenant(args: argparse.Namespace) -> bool:
    command = str(getattr(args, "command", "") or "").strip()
    if command in MUTATING_COMMANDS_REQUIRING_EXPLICIT_TENANT:
        return True
    if command == "platform-title":
        return bool(str(getattr(args, "title", "") or "").strip())
    if command in {"codex-keys", "data-engine", "email", "route-map", "sleep-manager", "system-admin", "upload-admin", "whatsapp"}:
        action = str(getattr(args, "action", "") or "").strip()
        read_only_actions = {
            "capabilities",
            "database-status",
            "db-connections",
            "datasets-list",
            "dns-records",
            "gateway-pairings",
            "history",
            "inventory",
            "list",
            "list-files",
            "repository-global-context",
            "repository-list",
            "route",
            "routes",
            "sessions",
            "session-status",
            "sqlserver-drivers",
            "status",
            "stats",
            "usage",
        }
        return action not in read_only_actions
    return False


def ensure_explicit_tenant_for_command(args: argparse.Namespace) -> None:
    if not command_requires_explicit_tenant(args):
        return
    if args_have_explicit_tenant(args) or getattr(args, "use_active_tenant", False):
        return
    raise RejoinBIError(
        "This command can change a tenant. Pass --tenant subdomain.rejoinbi.com.br "
        "or add --use-active-tenant after explicitly checking the active session."
    )


def session_slug(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    return re.sub(r"[^a-z0-9_.-]+", "_", host).strip("_") or "default"


def print_payload(payload: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(str(payload))


def prefer_utf8_response(response: requests.Response) -> requests.Response:
    content_type = (response.headers.get("content-type") or "").lower()
    if not (
        "application/json" in content_type
        or "text/" in content_type
        or "html" in content_type
        or "javascript" in content_type
    ):
        return response
    try:
        response.content.decode("utf-8")
    except UnicodeDecodeError:
        return response
    response.encoding = "utf-8"
    return response


def as_bool_flag(value: bool) -> str:
    return "yes" if value else "no"


def truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    raw = str(value).strip().lower()
    if raw in {"", "0", "false", "no", "nao", "não", "off", "none", "null"}:
        return False
    return raw in {"1", "true", "yes", "sim", "s", "on", "locked", "protected", "password"}


def protected_secret_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    raw = str(value).strip()
    if raw.lower() in {"", "0", "false", "no", "nao", "não", "off", "none", "null"}:
        return False
    return True


def workspace_password_indicators(workspace: dict[str, Any]) -> list[str]:
    indicators: list[str] = []
    for field in WORKSPACE_PASSWORD_FIELDS:
        if field in workspace and truthy_flag(workspace.get(field)):
            indicators.append(field)
    for field in WORKSPACE_PASSWORD_VALUE_FIELDS:
        if field in workspace and protected_secret_present(workspace.get(field)):
            indicators.append(field)
    return sorted(set(indicators))


def workspace_password_protected(workspace: dict[str, Any]) -> bool:
    return bool(workspace_password_indicators(workspace))


def render_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "(none)"
    widths = []
    for key, label in columns:
        max_width = len(label)
        for row in rows:
            max_width = max(max_width, len(str(row.get(key, "") if row.get(key, "") is not None else "")))
        widths.append(min(max_width, 60))
    header = "  ".join(label.ljust(widths[i]) for i, (_key, label) in enumerate(columns))
    sep = "  ".join("-" * widths[i] for i in range(len(columns)))
    lines = [header, sep]
    for row in rows:
        parts = []
        for i, (key, _label) in enumerate(columns):
            value = str(row.get(key, "") if row.get(key, "") is not None else "")
            if len(value) > widths[i]:
                value = value[: max(0, widths[i] - 3)] + "..."
            parts.append(value.ljust(widths[i]))
        lines.append("  ".join(parts))
    return "\n".join(lines)


class RejoinBIClient:
    def __init__(self, base_url: str):
        self.base_url = clean_base_url(base_url)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "rejoinbi-platform-plugin/0.1.0"})
        self.session_path = SESSION_DIR / f"{session_slug(self.base_url)}.json"
        self.load_session()

    def load_session(self) -> None:
        data = read_json(self.session_path, {})
        cookies = data.get("cookies") if isinstance(data, dict) else None
        if isinstance(cookies, dict):
            jar = requests.cookies.RequestsCookieJar()
            host = tenant_host_from_base_url(self.base_url).split(":", 1)[0]
            for name, value in cookies.items():
                if value is None:
                    continue
                jar.set(str(name), str(value), domain=host, path="/")
            self.session.cookies.update(jar)

    def save_session(self, identity: dict[str, Any] | None = None, auth_context: dict[str, Any] | None = None) -> None:
        existing = read_json(self.session_path, {})
        payload = {
            "base_url": self.base_url,
            "cookies": requests.utils.dict_from_cookiejar(self.session.cookies),
            "saved_at": utc_now(),
        }
        if identity:
            payload["identity"] = identity
        elif isinstance(existing, dict) and isinstance(existing.get("identity"), dict):
            payload["identity"] = existing.get("identity")
        if auth_context:
            payload["auth_context"] = auth_context
        elif isinstance(existing, dict) and isinstance(existing.get("auth_context"), dict):
            payload["auth_context"] = existing.get("auth_context")
        write_json(self.session_path, payload)
        config = read_json(CONFIG_PATH, {})
        if not isinstance(config, dict):
            config = {}
        config["active_base_url"] = self.base_url
        config["updated_at"] = utc_now()
        write_json(CONFIG_PATH, config)

    def clear_session(self) -> None:
        if self.session_path.exists():
            self.session_path.unlink()
        self.session.cookies.clear()

    def url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            target = clean_base_url(path)
            if target != self.base_url:
                raise RejoinBIError(f"Refusing cross-origin API request: {path}")
            return path
        return self.base_url + "/" + path.lstrip("/")

    def request(self, method: str, path: str, *, timeout: int = DEFAULT_TIMEOUT, **kwargs: Any) -> tuple[Any, requests.Response]:
        try:
            response = self.session.request(method, self.url(path), timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise RejoinBIError(f"{method} {path} failed before response: {exc}") from exc
        prefer_utf8_response(response)
        content_type = response.headers.get("content-type", "")
        payload: Any
        if "application/json" in content_type.lower():
            try:
                payload = response.json()
            except Exception:
                payload = {"raw": response.text}
        else:
            payload = {"raw": response.text}
        if not response.ok:
            message = ""
            if isinstance(payload, dict):
                message = str(payload.get("error") or payload.get("message") or payload.get("raw") or "")
            raise RejoinBIError(f"{method} {path} failed with HTTP {response.status_code}: {message[:600]}")
        return payload, response

    def download(self, path: str, output: Path, *, timeout: int = DEFAULT_TIMEOUT) -> None:
        try:
            response = self.session.get(self.url(path), timeout=timeout, stream=True)
        except requests.RequestException as exc:
            raise RejoinBIError(f"Download failed before response: {exc}") from exc
        if not response.ok:
            try:
                payload = response.json()
                message = payload.get("error") or payload.get("message") or response.text
            except Exception:
                message = response.text
            raise RejoinBIError(f"Download failed with HTTP {response.status_code}: {str(message)[:600]}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def make_client(args: argparse.Namespace) -> RejoinBIClient:
    ensure_explicit_tenant_for_command(args)
    base_url = resolve_base_url(
        subdomain=getattr(args, "tenant", "") or getattr(args, "subdomain", "") or "",
        domain=getattr(args, "domain", DEFAULT_DOMAIN) or DEFAULT_DOMAIN,
        base_url=getattr(args, "base_url", "") or "",
    )
    client = RejoinBIClient(base_url)
    if getattr(args, "command", "") not in SAFE_PROFILE_COMMANDS:
        require_allowed_profile(client, args)
    return client


def secret_value(cli_value: str | None, env_name: str, label: str, *, required: bool = True) -> str:
    if cli_value:
        return cli_value
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value
    if sys.stdin.isatty():
        value = getpass.getpass(f"{label}: ")
        if value:
            return value
    if required:
        raise RejoinBIError(f"{label} not provided. Use --{label.lower()} or set {env_name}.")
    return ""


def has_secret(cli_value: str | None, env_name: str) -> bool:
    return bool(cli_value or os.environ.get(env_name))


def open_browser_url(url: str) -> bool:
    try:
        if webbrowser.open(url, new=1, autoraise=True):
            return True
    except Exception:
        pass
    if os.name == "nt":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False
    return False


def auth_html(
    *,
    title: str,
    base_url: str,
    state: str,
    body: str,
    email: str = "",
    require_pin: bool = False,
    error: str = "",
) -> bytes:
    safe_title = html.escape(title)
    safe_base_url = html.escape(base_url)
    safe_state = html.escape(state)
    safe_email = html.escape(email)
    logo_uri = plugin_asset_data_uri("app-icon.svg") or plugin_asset_data_uri("app-icon.png") or plugin_asset_data_uri("Icon.png")
    logo_markup = f'<img src="{logo_uri}" alt="" class="brand-logo">' if logo_uri else '<span class="brand-fallback">RJ</span>'
    favicon_link = f'<link rel="icon" href="{logo_uri}">' if logo_uri else ""
    error_title, error_detail = auth_error_messages(error)
    safe_error_title = html.escape(error_title)
    safe_error_detail = html.escape(error_detail)
    safe_error_raw = html.escape(str(error or ""))
    error_details = ""
    if error and safe_error_raw and safe_error_raw != safe_error_detail:
        error_details = f"""
          <details>
            <summary>Detalhes tecnicos</summary>
            <code>{safe_error_raw}</code>
          </details>
        """
    error_block = ""
    if error_title:
        error_block = f"""
        <section class="alert alert-error" role="alert">
          <strong>{safe_error_title}</strong>
          <span>{safe_error_detail}</span>
          {error_details}
        </section>
        """
    if require_pin:
        form = f"""
        <form class="auth-form" method="post" action="/pin">
          <input type="hidden" name="state" value="{safe_state}">
          <div class="field">
            <label for="pin">PIN de seguranca</label>
            <input id="pin" name="pin" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*" autofocus required>
          </div>
          <p class="field-note">Use o codigo exibido pelo tenant para finalizar esta sessao.</p>
          <button type="submit"><span>Concluir conexao</span></button>
        </form>
        """
    else:
        form = f"""
        <form class="auth-form" method="post" action="/login">
          <input type="hidden" name="state" value="{safe_state}">
          <div class="field">
            <label for="email">Email</label>
            <input id="email" name="email" type="email" value="{safe_email}" autocomplete="username" spellcheck="false" autofocus required>
          </div>
          <div class="field">
            <label for="password">Senha</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required>
          </div>
          <button type="submit"><span>Conectar Rejoin BI</span></button>
        </form>
        """
    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  {favicon_link}
  <style>
    :root {{
      color-scheme: dark;
      --bg-root: #050505;
      --bg-alt: #0a0a0a;
      --bg-card: #0f0f0f;
      --bg-card-soft: #141414;
      --bg-field: #171717;
      --border-base: #222222;
      --border-light: #333333;
      --primary-solid: #ef4444;
      --primary-deep: #dc2626;
      --primary-dim: #7f1d1d;
      --text-main: #f7f7f7;
      --text-muted: #e0e0e0;
      --text-secondary: #a3a3a3;
      --text-dim: #777777;
      --success: #22c55e;
      --warning: #f59e0b;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg-root);
      color: var(--text-muted);
    }}
    * {{
      box-sizing: border-box;
    }}
    html {{
      min-height: 100%;
      background: var(--bg-root);
    }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      overflow-x: hidden;
      background:
        radial-gradient(ellipse at 50% -20%, rgba(239, 68, 68, 0.24) 0%, rgba(239, 68, 68, 0.06) 38%, transparent 72%),
        linear-gradient(180deg, rgba(5, 5, 5, 0.98) 0%, rgba(10, 10, 10, 1) 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: -20vh -20vw;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(220, 38, 38, 0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(220, 38, 38, 0.055) 1px, transparent 1px);
      background-size: 56px 56px;
      transform: perspective(760px) rotateX(62deg) translateY(-80px) scale(1.8);
      transform-origin: top center;
      mask-image: linear-gradient(to bottom, black 0%, black 58%, transparent 100%);
      -webkit-mask-image: linear-gradient(to bottom, black 0%, black 58%, transparent 100%);
    }}
    .auth-shell {{
      width: min(100%, 1040px);
      padding: 44px 22px;
      position: relative;
      z-index: 1;
      display: grid;
      place-items: center;
    }}
    main {{
      width: min(520px, 100%);
      border: 1px solid var(--border-base);
      border-radius: 16px;
      background:
        radial-gradient(circle at top right, rgba(239, 68, 68, 0.15), transparent 38%),
        linear-gradient(180deg, rgba(15, 15, 15, 0.98), rgba(8, 8, 8, 0.98));
      box-shadow: 0 28px 80px rgba(0, 0, 0, 0.55);
      overflow: hidden;
      position: relative;
    }}
    main::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 50%;
      width: 160px;
      height: 3px;
      border-radius: 999px;
      transform: translateX(-50%);
      background: linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.95), transparent);
    }}
    .panel-inner {{
      padding: 32px;
    }}
    .brand-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .brand-logo,
    .brand-fallback {{
      width: 44px;
      height: 44px;
      border-radius: 12px;
      flex: 0 0 auto;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: #111111;
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4);
    }}
    .brand-logo {{
      object-fit: cover;
      object-position: center;
    }}
    .brand-fallback {{
      display: inline-grid;
      place-items: center;
      color: var(--primary-solid);
      font-weight: 800;
    }}
    .brand-copy {{
      min-width: 0;
    }}
    .eyebrow {{
      margin: 0 0 2px;
      color: #fca5a5;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.11em;
      line-height: 1.2;
      text-transform: uppercase;
    }}
    .brand-name {{
      margin: 0;
      color: var(--text-main);
      font-size: 15px;
      font-weight: 700;
      line-height: 1.35;
    }}
    .status-line {{
      display: inline-flex;
      align-items: center;
      gap: 9px;
      min-height: 30px;
      padding: 5px 10px;
      margin-bottom: 16px;
      border: 1px solid rgba(239, 68, 68, 0.34);
      border-radius: 999px;
      background: rgba(220, 38, 38, 0.11);
      color: #fecaca;
      font-size: 12px;
      font-weight: 700;
    }}
    .status-dot {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 16px rgba(34, 197, 94, 0.72);
      flex: 0 0 auto;
    }}
    h1 {{
      margin: 0 0 10px;
      color: var(--text-main);
      font-size: 30px;
      line-height: 1.15;
      letter-spacing: 0;
      font-weight: 800;
    }}
    .lead {{
      margin: 0 0 18px;
      max-width: 64ch;
      color: var(--text-secondary);
      font-size: 15px;
      line-height: 1.65;
    }}
    .tenant {{
      display: grid;
      gap: 6px;
      margin: 18px 0 20px;
      padding: 14px 15px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.04);
    }}
    .tenant span {{
      color: var(--text-dim);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .tenant strong {{
      color: var(--text-main);
      font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 14px;
      font-weight: 600;
      overflow-wrap: anywhere;
    }}
    .alert {{
      display: grid;
      gap: 5px;
      margin: 0 0 18px;
      padding: 13px 14px;
      border-radius: 12px;
      line-height: 1.45;
    }}
    .alert strong {{
      color: var(--text-main);
      font-size: 14px;
    }}
    .alert span {{
      color: #fecaca;
      font-size: 14px;
    }}
    .alert-error {{
      border: 1px solid rgba(239, 68, 68, 0.34);
      background: rgba(127, 29, 29, 0.28);
    }}
    details {{
      margin-top: 5px;
      color: #fca5a5;
      font-size: 12px;
    }}
    summary {{
      cursor: pointer;
      width: fit-content;
      font-weight: 700;
    }}
    code {{
      display: block;
      margin-top: 8px;
      padding: 10px;
      border-radius: 8px;
      background: rgba(0, 0, 0, 0.26);
      color: #f5b6b6;
      font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 11px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .auth-form {{
      display: grid;
      gap: 14px;
    }}
    .field {{
      display: grid;
      gap: 7px;
    }}
    label {{
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      min-height: 50px;
      border-radius: 10px;
      border: 1px solid var(--border-light);
      background: var(--bg-field);
      color: var(--text-main);
      padding: 0 14px;
      font: inherit;
      outline: none;
      transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }}
    input:focus {{
      border-color: rgba(239, 68, 68, 0.78);
      background: #1b1b1b;
      box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.16);
    }}
    .field-note {{
      margin: -4px 0 0;
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.5;
    }}
    button {{
      margin-top: 2px;
      min-height: 52px;
      border: 1px solid rgba(239, 68, 68, 0.28);
      border-radius: 10px;
      background: linear-gradient(135deg, var(--primary-solid), var(--primary-deep));
      color: #fff7f7;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 10px 28px rgba(220, 38, 38, 0.34);
      transition: transform 0.18s ease, box-shadow 0.2s ease, filter 0.2s ease;
    }}
    button:hover {{
      transform: translateY(-1px);
      filter: brightness(1.06);
      box-shadow: 0 14px 34px rgba(220, 38, 38, 0.42);
    }}
    button:active {{
      transform: translateY(0);
    }}
    button:focus-visible,
    input:focus-visible,
    summary:focus-visible {{
      outline: 2px solid rgba(239, 68, 68, 0.85);
      outline-offset: 3px;
    }}
    .security-note {{
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      color: var(--text-dim);
      font-size: 13px;
      line-height: 1.5;
    }}
    .security-note::before {{
      content: "";
      width: 8px;
      height: 8px;
      margin-top: 6px;
      border-radius: 50%;
      background: var(--primary-solid);
      box-shadow: 0 0 18px rgba(239, 68, 68, 0.78);
      flex: 0 0 auto;
    }}
    @media (max-width: 560px) {{
      .auth-shell {{
        padding: 18px 12px;
      }}
      .panel-inner {{
        padding: 24px 18px;
      }}
      .brand-row {{
        margin-bottom: 18px;
      }}
      h1 {{
        font-size: 25px;
      }}
      .lead {{
        font-size: 14px;
      }}
    }}
  </style>
</head>
<body>
  <div class="auth-shell">
    <main>
      <div class="panel-inner">
        <div class="brand-row">
          {logo_markup}
          <div class="brand-copy">
            <p class="eyebrow">Rejoin BI</p>
            <p class="brand-name">Plataforma Self-Hosted</p>
          </div>
        </div>
        <div class="status-line"><span class="status-dot"></span><span>Tenant validado</span></div>
        <h1>{safe_title}</h1>
        <p class="lead">{html.escape(body)}</p>
        <div class="tenant"><span>URL conectada</span><strong>{safe_base_url}</strong></div>
        {error_block}
        {form}
        <div class="security-note">Senha e PIN ficam somente nesta janela local. O plugin salva apenas a sessao autorizada do tenant.</div>
      </div>
    </main>
  </div>
</body>
</html>"""
    return page.encode("utf-8")


def success_html(base_url: str, email: str, profile: str) -> bytes:
    safe_base_url = html.escape(base_url)
    safe_email = html.escape(email)
    safe_profile = html.escape(profile or "perfil validado")
    logo_uri = plugin_asset_data_uri("app-icon.svg") or plugin_asset_data_uri("app-icon.png") or plugin_asset_data_uri("Icon.png")
    logo_markup = f'<img src="{logo_uri}" alt="" class="brand-logo">' if logo_uri else '<span class="brand-fallback">RJ</span>'
    favicon_link = f'<link rel="icon" href="{logo_uri}">' if logo_uri else ""
    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rejoin BI conectado</title>
  {favicon_link}
  <style>
    :root {{
      color-scheme: dark;
      --bg-root: #050505;
      --bg-card: #0f0f0f;
      --border-base: #222222;
      --border-light: #333333;
      --primary-solid: #ef4444;
      --primary-deep: #dc2626;
      --text-main: #f7f7f7;
      --text-muted: #e0e0e0;
      --text-secondary: #a3a3a3;
      --text-dim: #777777;
      --success: #22c55e;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg-root);
      color: var(--text-muted);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      overflow-x: hidden;
      background:
        radial-gradient(ellipse at 50% -20%, rgba(239, 68, 68, 0.22) 0%, rgba(239, 68, 68, 0.055) 38%, transparent 72%),
        linear-gradient(180deg, rgba(5, 5, 5, 0.98) 0%, rgba(10, 10, 10, 1) 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: -20vh -20vw;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(220, 38, 38, 0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(220, 38, 38, 0.055) 1px, transparent 1px);
      background-size: 56px 56px;
      transform: perspective(760px) rotateX(62deg) translateY(-80px) scale(1.8);
      transform-origin: top center;
      mask-image: linear-gradient(to bottom, black 0%, black 58%, transparent 100%);
      -webkit-mask-image: linear-gradient(to bottom, black 0%, black 58%, transparent 100%);
    }}
    .auth-shell {{
      width: min(100%, 1040px);
      padding: 44px 22px;
      position: relative;
      z-index: 1;
      display: grid;
      place-items: center;
    }}
    main {{
      width: min(520px, 100%);
      border-radius: 16px;
      border: 1px solid var(--border-base);
      background:
        radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 40%),
        linear-gradient(180deg, rgba(15, 15, 15, 0.98), rgba(8, 8, 8, 0.98));
      padding: 32px;
      box-shadow: 0 28px 80px rgba(0, 0, 0, 0.55);
      position: relative;
      overflow: hidden;
    }}
    main::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 50%;
      width: 160px;
      height: 3px;
      border-radius: 999px;
      transform: translateX(-50%);
      background: linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.95), transparent);
    }}
    .brand-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .brand-logo,
    .brand-fallback {{
      width: 44px;
      height: 44px;
      border-radius: 12px;
      flex: 0 0 auto;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: #111111;
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4);
    }}
    .brand-logo {{
      object-fit: cover;
      object-position: center;
    }}
    .brand-fallback {{
      display: inline-grid;
      place-items: center;
      color: var(--primary-solid);
      font-weight: 800;
    }}
    .eyebrow {{
      margin: 0 0 2px;
      color: #fca5a5;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.11em;
      line-height: 1.2;
      text-transform: uppercase;
    }}
    .brand-name {{
      margin: 0;
      color: var(--text-main);
      font-size: 15px;
      font-weight: 700;
      line-height: 1.35;
    }}
    h1 {{
      margin: 0 0 10px;
      color: var(--text-main);
      font-size: 30px;
      line-height: 1.15;
      letter-spacing: 0;
      font-weight: 800;
    }}
    p {{
      margin: 0 0 14px;
      color: var(--text-secondary);
      line-height: 1.6;
    }}
    .success {{
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin-bottom: 16px;
      padding: 7px 11px;
      border-radius: 12px;
      border: 1px solid rgba(34, 197, 94, 0.26);
      background: rgba(34, 197, 94, 0.11);
      color: #bbf7d0;
      font-size: 13px;
      font-weight: 800;
    }}
    .success::before {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 16px rgba(34, 197, 94, 0.72);
    }}
    .tenant-link {{
      display: grid;
      gap: 6px;
      margin-top: 18px;
      padding: 14px 15px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.04);
    }}
    .tenant-link span {{
      color: var(--text-dim);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    a {{
      color: var(--text-main);
      font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 14px;
      font-weight: 700;
      overflow-wrap: anywhere;
      text-decoration-color: rgba(239, 68, 68, 0.7);
      text-underline-offset: 3px;
    }}
    a:focus-visible {{
      outline: 2px solid rgba(239, 68, 68, 0.85);
      outline-offset: 3px;
    }}
    @media (max-width: 560px) {{
      .auth-shell {{
        padding: 18px 12px;
      }}
      main {{
        padding: 24px 18px;
      }}
      h1 {{
        font-size: 25px;
      }}
    }}
  </style>
</head>
<body>
  <div class="auth-shell">
    <main>
      <div class="brand-row">
        {logo_markup}
        <div>
          <p class="eyebrow">Rejoin BI</p>
          <p class="brand-name">Plataforma Self-Hosted</p>
        </div>
      </div>
      <div class="success">Sessao salva com seguranca</div>
      <h1>Conectado</h1>
      <p>{safe_email} foi validado como {safe_profile}. Voce ja pode voltar ao Codex para operar workspaces, paginas, uploads e dashboards.</p>
      <div class="tenant-link"><span>Tenant conectado</span><a href="{safe_base_url}/plataforma" target="_blank" rel="noreferrer">{safe_base_url}</a></div>
    </main>
  </div>
</body>
</html>"""
    return page.encode("utf-8")


def browser_auth_flow(args: argparse.Namespace) -> int:
    client = make_client(args)
    client.clear_session()
    lang = getattr(args, "lang", "pt-BR") or "pt-BR"
    initial_email = str(getattr(args, "email", "") or os.environ.get("REJOINBI_EMAIL") or "").strip().lower()
    state = secrets.token_urlsafe(24)
    done = threading.Event()
    result: dict[str, Any] = {}
    pending: dict[str, str] = {}

    class AuthHandler(BaseHTTPRequestHandler):
        server_version = "RejoinBIAuth/1.0"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def read_form(self) -> dict[str, str]:
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            parsed = parse_qs(raw, keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}

        def send_html(self, payload: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def render_login(self, error: str = "") -> None:
            self.send_html(auth_html(
                title="Conectar tenant",
                base_url=client.base_url,
                state=state,
                body="Digite seu login Rejoin BI nesta janela local. A senha e o PIN nao vao para o chat.",
                email=initial_email,
                error=error,
            ))

        def render_pin(self, error: str = "") -> None:
            self.send_html(auth_html(
                title="Confirmar PIN",
                base_url=client.base_url,
                state=state,
                body="O tenant pediu PIN. Digite o codigo para concluir a conexao do plugin.",
                email=pending.get("email", ""),
                require_pin=True,
                error=error,
            ))

        def finish_success(self, data: Any, email: str, *, admin_principal_hint: bool = False) -> None:
            try:
                identity = require_allowed_profile(client, args, admin_principal_hint=admin_principal_hint)
                client.save_session(
                    identity=identity,
                    auth_context={
                        "admin_principal_no_pin": bool(admin_principal_hint),
                        "pin_required": not bool(admin_principal_hint),
                    },
                )
            except RejoinBIError as exc:
                client.clear_session()
                self.render_login(str(exc))
                return
            result.update({
                "success": True,
                "base_url": client.base_url,
                "email": email,
                "profile": identity.get("profile"),
                "message": data.get("message") if isinstance(data, dict) else "Connected.",
                "session_path": str(client.session_path),
                "auth_method": "browser",
            })
            self.send_html(success_html(client.base_url, email, str(identity.get("profile") or "")))
            done.set()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/login"}:
                self.render_login()
                return
            if parsed.path == "/health":
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            form = self.read_form()
            if form.get("state") != state:
                self.send_error(403)
                return
            if self.path == "/login":
                email = str(form.get("email") or "").strip().lower()
                password = str(form.get("password") or "")
                if not email or not password:
                    self.render_login("Informe email e senha.")
                    return
                try:
                    try:
                        client.request("GET", f"/plataforma/credencial?lang={lang}", timeout=30)
                    except Exception:
                        pass
                    payload = {"email": email, "password": password, "lang": lang}
                    data, _ = client.request("POST", f"/plataforma/api/login?lang={lang}", json=payload)
                    if response_requires_pin(data):
                        pending.clear()
                        pending.update(payload)
                        self.render_pin(data.get("message") or "")
                        return
                    if isinstance(data, dict) and data.get("success"):
                        self.finish_success(data, email, admin_principal_hint=True)
                        return
                    self.render_login(str(data))
                except RejoinBIError as exc:
                    client.clear_session()
                    self.render_login(str(exc))
                return
            if self.path == "/pin":
                pin = str(form.get("pin") or "").strip()
                if not pending:
                    self.render_login("Sessao de PIN expirada. Faca login novamente.")
                    return
                if not pin:
                    self.render_pin("Informe o PIN.")
                    return
                try:
                    payload = {**pending, "pin": pin}
                    data, _ = client.request("POST", f"/plataforma/api/login?lang={lang}", json=payload)
                    if isinstance(data, dict) and data.get("success"):
                        self.finish_success(data, pending.get("email", ""), admin_principal_hint=False)
                        pending.clear()
                        return
                    self.render_pin(str(data))
                except RejoinBIError as exc:
                    client.clear_session()
                    self.render_pin(str(exc))
                return
            self.send_error(404)

    host = "127.0.0.1"
    port = int(getattr(args, "auth_port", 0) or 0)
    timeout = int(getattr(args, "auth_timeout", 600) or 600)
    server = ThreadingHTTPServer((host, port), AuthHandler)
    auth_url = f"http://{host}:{server.server_port}/?state={quote(state)}"
    retry_command = getattr(args, "command", "") or "connect"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opened = False
    if not getattr(args, "no_open_browser", False):
        opened = open_browser_url(auth_url)
    try:
        if not done.wait(timeout):
            raise RejoinBIError(
                "Browser authentication timed out. "
                f"Open {auth_url} and complete login, or run {retry_command} again."
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    result.setdefault("opened_browser", opened)
    result.setdefault("auth_url", auth_url)
    print_payload(result, as_json=args.json)
    return 0


def normalize_text(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def slugify_page_id(value: Any) -> str:
    raw = str(value or "").strip().lower()
    ascii_text = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(ch for ch in ascii_text if not unicodedata.combining(ch))
    ascii_text = ascii_text.replace("ç", "c").replace("ñ", "n")
    ascii_text = re.sub(r"\s+", "-", ascii_text)
    ascii_text = re.sub(r"[^a-z0-9_-]+", "", ascii_text)
    ascii_text = re.sub(r"-{2,}", "-", ascii_text).strip("-_")
    return ascii_text or "pagina"


def detect_manifest_language(manifest: dict[str, Any]) -> str:
    explicit = str(manifest.get("language") or manifest.get("lang") or "").strip()
    if explicit:
        return explicit
    text_parts: list[str] = []
    for page in manifest.get("pages") or []:
        if isinstance(page, dict):
            text_parts.append(str(page.get("name") or page.get("nome") or ""))
            text_parts.append(str(page.get("description") or page.get("descricao") or ""))
    normalized = normalize_text(" ".join(text_parts))
    pt_markers = {
        "analise", "atendimento", "clientes", "comercial", "configuracao", "faturamento",
        "geral", "gestao", "operacoes", "produtos", "receita", "vendas", "visao",
    }
    if any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in pt_markers):
        return "pt-BR"
    return ""


def suggest_pt_br_display_name(value: str) -> str:
    if not value:
        return ""
    parts = re.split(r"(\W+)", value)
    changed = False
    fixed: list[str] = []
    for part in parts:
        key = normalize_text(part)
        replacement = PT_BR_WORD_ACCENT_FIXES.get(key)
        if not replacement:
            fixed.append(part)
            continue
        changed = True
        if part.isupper():
            fixed.append(replacement.upper())
        elif part[:1].isupper():
            fixed.append(replacement[:1].upper() + replacement[1:])
        else:
            fixed.append(replacement)
    return "".join(fixed) if changed else ""


MOJIBAKE_MARKERS = (
    "\u00c3\u00a1", "\u00c3\u00a2", "\u00c3\u00a3", "\u00c3\u00aa", "\u00c3\u00a9",
    "\u00c3\u00ad", "\u00c3\u00b3", "\u00c3\u00b4", "\u00c3\u00b5", "\u00c3\u00ba",
    "\u00c3\u00a7", "\u00c3\u0081", "\u00c3\u0082", "\u00c3\u0083", "\u00c3\u008a",
    "\u00c3\u0089", "\u00c3\u008d", "\u00c3\u0093", "\u00c3\u0094", "\u00c3\u0095",
    "\u00c3\u009a", "\u00c3\u0087", "\u00c2\u00b4", "\u00c2\u00b0", "\u00c2\u00ba",
    "\u00c2\u00aa", "\u00e2\u20ac",
)


def looks_like_corrupted_text(value: Any) -> bool:
    text = str(value or "")
    if not text:
        return False
    if "\ufffd" in text:
        return True
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        return True
    # A literal question mark inside a word usually means a Windows code page
    # replaced an accent before the JSON reached the platform.
    if re.search(r"[A-Za-zÀ-ÿ]\?+[A-Za-zÀ-ÿ]", text):
        return True
    return False


def manifest_text_integrity_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    visible_fields: list[tuple[str, Any]] = []
    app_cfg = manifest.get("app") if isinstance(manifest.get("app"), dict) else {}
    workspace_cfg = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
    for field in ("name", "description", "title"):
        if isinstance(app_cfg, dict) and field in app_cfg:
            visible_fields.append((f"app.{field}", app_cfg.get(field)))
    for field in ("description", "display_name"):
        if isinstance(workspace_cfg, dict) and field in workspace_cfg:
            visible_fields.append((f"workspace.{field}", workspace_cfg.get(field)))
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        for field in ("name", "nome", "description", "descricao", "expect_text"):
            if field in page:
                visible_fields.append((f"pages[{index}].{field}", page.get(field)))
    for path, value in visible_fields:
        text = str(value or "")
        if looks_like_corrupted_text(text):
            errors.append(
                f"{path} contains corrupted text ({text!r}). Save the manifest as UTF-8 and keep visible labels localized; "
                "for pt-BR use accents in name/description while keeping id, route, and file ASCII."
            )
    return errors


def json_text_integrity_errors(value: Any, *, path: str = "$", limit: int = 25) -> list[str]:
    """Find mojibake or replaced accents in arbitrary JSON-like payloads."""
    errors: list[str] = []

    def visit(item: Any, item_path: str) -> None:
        if len(errors) >= limit:
            return
        if isinstance(item, str):
            if looks_like_corrupted_text(item):
                errors.append(
                    f"{item_path} contains corrupted text ({item!r}). Save JSON/code as UTF-8; "
                    "visible labels can use accents, but technical ids/routes/files should stay ASCII."
                )
            return
        if isinstance(item, dict):
            for key, nested in item.items():
                safe_key = str(key).replace("'", "\\'")
                visit(nested, f"{item_path}.{safe_key}")
            return
        if isinstance(item, list):
            for index, nested in enumerate(item):
                visit(nested, f"{item_path}[{index}]")

    visit(value, path)
    if len(errors) >= limit:
        errors.append(f"{path} has more text integrity problems; fix the first {limit} entries and retry.")
    return errors


def require_clean_json_text(value: Any, *, context: str) -> None:
    errors = json_text_integrity_errors(value, path=context)
    if errors:
        details = "\n".join(f"- {error}" for error in errors[:10])
        raise RejoinBIError(
            f"{context} appears to contain corrupted text/encoding. "
            "This would create wrong BI Studio/Data Engine labels or values.\n"
            f"{details}"
        )


def response_requires_pin(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(truthy_flag(payload.get(key)) for key in ("require_pin", "requires_pin", "pin_required", "need_pin"))


def extract_session_identity(payload: Any, *, admin_principal_hint: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"email": "", "profile": "", "permissions": []}
    session_data = payload.get("session_data") if isinstance(payload.get("session_data"), dict) else {}
    permissions = payload.get("user_permissions") or session_data.get("user_permissions") or []
    if isinstance(permissions, str):
        permissions = [p.strip() for p in permissions.split(",") if p.strip()]
    if not isinstance(permissions, list):
        permissions = []
    profile = payload.get("user_perfil") or payload.get("perfil") or session_data.get("user_perfil") or session_data.get("perfil") or ""
    profile_source = "session"
    if admin_principal_hint:
        profile = "Administrador Principal"
        profile_source = "no_pin_login"
    elif not profile and ("*" in permissions or "admin_principal" in permissions):
        profile = "Administrador Principal"
        profile_source = "permissions"
    return {
        "email": payload.get("user_email") or session_data.get("user_email") or "",
        "profile": profile,
        "profile_source": profile_source,
        "permissions": permissions,
        "logged_in": bool(payload.get("logged_in", True) or session_data.get("user_email")),
    }


def is_allowed_identity(identity: dict[str, Any]) -> bool:
    profile_key = normalize_text(identity.get("profile"))
    permissions = [normalize_text(item) for item in identity.get("permissions") or []]
    return profile_key in ALLOWED_PROFILE_KEYS or "*" in permissions or "admin_principal" in permissions


def require_allowed_profile(
    client: RejoinBIClient,
    args: argparse.Namespace,
    *,
    admin_principal_hint: bool = False,
) -> dict[str, Any]:
    data, _ = client.request("GET", "/plataforma/api/session-status", timeout=30)
    saved_session = read_json(client.session_path, {})
    saved_context = saved_session.get("auth_context") if isinstance(saved_session, dict) else {}
    saved_identity = saved_session.get("identity") if isinstance(saved_session, dict) else {}
    saved_admin_principal = isinstance(saved_context, dict) and truthy_flag(saved_context.get("admin_principal_no_pin"))
    identity = extract_session_identity(data, admin_principal_hint=admin_principal_hint or saved_admin_principal)
    if isinstance(saved_identity, dict):
        if not identity.get("email") and saved_identity.get("email"):
            identity["email"] = saved_identity.get("email")
        if saved_admin_principal:
            identity["profile"] = "Administrador Principal"
            identity["profile_source"] = "saved_no_pin_login"
    if getattr(args, "allow_standard", False):
        return identity
    if not is_allowed_identity(identity):
        profile = identity.get("profile") or "unknown"
        email = identity.get("email") or "unknown"
        raise RejoinBIError(
            f"Profile '{profile}' for {email} is not allowed. "
            "This plugin accepts only Administrador Principal, Master, or Administrador."
        )
    return identity


def has_saved_cookies(client: RejoinBIClient) -> bool:
    data = read_json(client.session_path, {})
    cookies = data.get("cookies") if isinstance(data, dict) else None
    return isinstance(cookies, dict) and bool(cookies)


def cmd_ensure_connected(args: argparse.Namespace) -> int:
    client = make_client(args)
    if not has_saved_cookies(client):
        return browser_auth_flow(args)
    try:
        identity = require_allowed_profile(client, args)
    except RejoinBIError:
        client.clear_session()
        return browser_auth_flow(args)

    client.save_session()
    print_payload({
        "success": True,
        "connected": True,
        "base_url": client.base_url,
        "email": identity.get("email"),
        "profile": identity.get("profile"),
        "profile_allowed": True,
        "auth_method": "saved_session",
        "message": "Tenant session is already connected and allowed.",
        "session_path": str(client.session_path),
    }, as_json=args.json)
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    if not getattr(args, "terminal", False) and not has_secret(args.password, "REJOINBI_PASSWORD"):
        return browser_auth_flow(args)

    client = make_client(args)
    client.clear_session()
    email = str(args.email or os.environ.get("REJOINBI_EMAIL") or "").strip().lower()
    if not email:
        return browser_auth_flow(args)
    password = secret_value(args.password, "REJOINBI_PASSWORD", "password")
    lang = args.lang or "pt-BR"

    # Prime the origin/cookie path. CSRF is disabled in the analyzed app, but this mirrors browser flow.
    try:
        client.request("GET", f"/plataforma/credencial?lang={lang}", timeout=30)
    except Exception:
        pass

    payload = {"email": email, "password": password, "lang": lang}
    data, _ = client.request("POST", f"/plataforma/api/login?lang={lang}", json=payload)
    admin_principal_hint = isinstance(data, dict) and data.get("success") and not response_requires_pin(data)

    if response_requires_pin(data):
        admin_principal_hint = False
        pin = args.pin or os.environ.get("REJOINBI_PIN") or ""
        if not pin and sys.stdin.isatty():
            pin = getpass.getpass("PIN: ")
        if not pin:
            print_payload({
                "success": False,
                "require_pin": True,
                "base_url": client.base_url,
                "message": data.get("message") or "PIN required. Set REJOINBI_PIN and run connect again.",
                "remaining_seconds": data.get("remaining_seconds"),
            })
            return 2
        payload["pin"] = str(pin).strip()
        data, _ = client.request("POST", f"/plataforma/api/login?lang={lang}", json=payload)

    if isinstance(data, dict) and data.get("success"):
        try:
            identity = require_allowed_profile(client, args, admin_principal_hint=admin_principal_hint)
        except RejoinBIError:
            client.clear_session()
            raise
        client.save_session(
            identity=identity,
            auth_context={
                "admin_principal_no_pin": bool(admin_principal_hint),
                "pin_required": not bool(admin_principal_hint),
            },
        )
        print_payload({
            "success": True,
            "base_url": client.base_url,
            "email": email,
            "profile": identity.get("profile"),
            "message": data.get("message") or "Connected.",
            "redirect": data.get("redirect"),
            "session_path": str(client.session_path),
        }, as_json=args.json)
        return 0

    raise RejoinBIError(str(data))


def cmd_browser_login(args: argparse.Namespace) -> int:
    return browser_auth_flow(args)


def cmd_status(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/check-session", timeout=30)
    saved_session = read_json(client.session_path, {})
    saved_context = saved_session.get("auth_context") if isinstance(saved_session, dict) else {}
    saved_identity = saved_session.get("identity") if isinstance(saved_session, dict) else {}
    saved_admin_principal = isinstance(saved_context, dict) and truthy_flag(saved_context.get("admin_principal_no_pin"))
    identity = extract_session_identity(data, admin_principal_hint=saved_admin_principal)
    if isinstance(saved_identity, dict):
        if not identity.get("email") and saved_identity.get("email"):
            identity["email"] = saved_identity.get("email")
        if saved_admin_principal:
            identity["profile"] = "Administrador Principal"
            identity["profile_source"] = "saved_no_pin_login"
    if isinstance(data, dict):
        data = {
            **data,
            "plugin_profile_allowed": is_allowed_identity(identity),
            "plugin_identity": identity,
        }
    print_payload(data, as_json=args.json)
    return 0


def load_workspaces(client: RejoinBIClient) -> list[dict[str, Any]]:
    data, _ = client.request("GET", "/plataforma/api/containers", timeout=60)
    if isinstance(data, dict):
        return list(data.get("containers") or [])
    return []


def workspace_matches(item: dict[str, Any], selector: str) -> bool:
    raw = str(selector or "").strip().lower()
    return raw and (str(item.get("id", "")).lower() == raw or str(item.get("name", "")).strip().lower() == raw)


def resolve_workspace(client: RejoinBIClient, selector: str) -> dict[str, Any]:
    workspaces = load_workspaces(client)
    for item in workspaces:
        if workspace_matches(item, selector):
            return item
    raise RejoinBIError(f"Workspace not found: {selector}")


def safe_str(value: Any) -> str:
    return str(value or "").strip()


def same_id(left: Any, right: Any) -> bool:
    return safe_str(left) != "" and safe_str(left) == safe_str(right)


def list_pages(
    client: RejoinBIClient,
    *,
    workspace_id: Any = None,
    all_containers: bool = False,
    include_inactive: bool = True,
    exclude_fictitious: bool = False,
) -> list[dict[str, Any]]:
    params = {
        "all_containers": "true" if all_containers else "false",
        "include_inactive": "true" if include_inactive else "false",
        "exclude_fictitious": "true" if exclude_fictitious else "false",
    }
    if workspace_id is not None:
        params["container_id"] = safe_str(workspace_id)
    data, _ = client.request("GET", "/plataforma/api/paginas", params=params, timeout=60)
    if not isinstance(data, dict):
        return []
    pages = data.get("pages") or data.get("data") or []
    return [item for item in pages if isinstance(item, dict)]


def page_id(page: dict[str, Any]) -> str:
    return safe_str(page.get("id"))


def page_name(page: dict[str, Any]) -> str:
    return safe_str(page.get("nome") or page.get("name") or page_id(page))


def is_fictitious_page_id(value: Any) -> bool:
    return safe_str(value).startswith(FICTITIOUS_PAGE_PREFIXES)


def is_page_in_workspace(page: dict[str, Any], workspace_id: Any) -> bool:
    return any(same_id(page.get(field), workspace_id) for field in ("container_id", "container_origem", "container_destino"))


def page_refs(page: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    for field in fields:
        value = safe_str(page.get(field))
        if value and value not in refs:
            refs.append(value)
    return refs


def page_summary(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": page_id(page),
        "name": page_name(page),
        "route": safe_str(page.get("rota")),
        "file": safe_str(page.get("arquivo")),
        "parent_id": safe_str(page.get("pai")),
        "container_id": page.get("container_id"),
        "container_origin": page.get("container_origem"),
        "container_destination": page.get("container_destino"),
        "fictitious_ref": safe_str(page.get("ficticio")),
        "hierarchy_id": safe_str(page.get("hierarquia_id")),
        "real_parent_id": safe_str(page.get("pai_real")),
        "fictitious_parent_id": safe_str(page.get("pai_ficticio")),
        "active": page.get("ativo"),
        "html_missing": bool(page.get("html_missing")),
        "is_fictitious": is_fictitious_page_id(page_id(page)),
    }


def collect_related_page_ids(pages: list[dict[str, Any]], seed_ids: set[str], reference_fields: tuple[str, ...]) -> set[str]:
    related = {safe_str(item) for item in seed_ids if safe_str(item)}
    changed = True
    while changed and related:
        changed = False
        for page in pages:
            current_id = page_id(page)
            if not current_id or current_id in related:
                continue
            if any(ref in related for ref in page_refs(page, reference_fields)):
                related.add(current_id)
                changed = True
    return related


def build_page_tree(pages: list[dict[str, Any]], root_ids: set[str], included_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {page_id(page): page for page in pages if page_id(page)}
    children_by_parent: dict[str, list[str]] = {}
    for page in pages:
        current_id = page_id(page)
        parent_id = safe_str(page.get("pai"))
        if current_id and parent_id:
            children_by_parent.setdefault(parent_id, []).append(current_id)
    for children in children_by_parent.values():
        children.sort(key=lambda value: normalize_text(page_name(by_id.get(value, {}))) or value)

    visited: set[str] = set()

    def walk(current_id: str, depth: int, ancestry: set[str]) -> dict[str, Any]:
        page = by_id.get(current_id, {"id": current_id, "nome": current_id})
        visited.add(current_id)
        if current_id in ancestry:
            node = page_summary(page)
            node["depth"] = depth
            node["cycle_detected"] = True
            node["children"] = []
            return node
        children = [
            child_id
            for child_id in children_by_parent.get(current_id, [])
            if child_id in included_ids
        ]
        node = page_summary(page)
        node["depth"] = depth
        node["children"] = [walk(child_id, depth + 1, ancestry | {current_id}) for child_id in children]
        return node

    ordered_roots = sorted(root_ids, key=lambda value: normalize_text(page_name(by_id.get(value, {}))) or value)
    tree = [walk(root_id, 0, set()) for root_id in ordered_roots if root_id in included_ids]
    linked_outside_tree = sorted(included_ids - visited)
    return tree, linked_outside_tree


def resolve_page_from_pages(pages: list[dict[str, Any]], selector: str) -> dict[str, Any] | None:
    raw = safe_str(selector)
    if not raw:
        return None
    for page in pages:
        if page_id(page) == raw:
            return page
    route_matches = [page for page in pages if safe_str(page.get("rota")) == raw]
    if len(route_matches) == 1:
        return route_matches[0]
    name_matches = [page for page in pages if normalize_text(page_name(page)) == normalize_text(raw)]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(route_matches) > 1 or len(name_matches) > 1:
        raise RejoinBIError(f"Page selector is ambiguous: {selector}. Use the exact page id.")
    return None


def workspace_delete_plan(client: RejoinBIClient, workspace: dict[str, Any]) -> dict[str, Any]:
    workspace_id = workspace.get("id")
    password_indicators = workspace_password_indicators(workspace)
    password_protected = bool(password_indicators)
    pages = list_pages(client, all_containers=True, include_inactive=True, exclude_fictitious=False)
    direct_ids = {page_id(page) for page in pages if page_id(page) and is_page_in_workspace(page, workspace_id)}
    related_ids = collect_related_page_ids(pages, direct_ids, DELETE_WORKSPACE_REFERENCE_FIELDS)
    by_id = {page_id(page): page for page in pages if page_id(page)}
    root_ids = {
        item
        for item in direct_ids
        if safe_str(by_id.get(item, {}).get("pai")) not in related_ids
    } or direct_ids
    tree, linked_outside_tree = build_page_tree(pages, root_ids, related_ids)
    external_linked = [
        page_summary(by_id[item])
        for item in sorted(related_ids - direct_ids)
        if item in by_id and not is_page_in_workspace(by_id[item], workspace_id)
    ]
    return {
        "workspace": {
            "id": workspace_id,
            "name": workspace.get("name"),
            "active": bool(workspace.get("is_active")),
            "locked": password_protected,
            "password_protected": password_protected,
            "password_indicators": password_indicators,
            "status": workspace.get("deploy_status") or "",
        },
        "blocked": password_protected,
        "password_validation_required": password_protected,
        "manual_deletion_required": False,
        "security_message": (
            "Workspace protegido por senha detectado. O plugin so remove apos validar a senha do workspace; "
            "informe --workspace-password ou REJOINBI_WORKSPACE_PASSWORD. Sem senha validada, remova manualmente."
            if password_protected
            else ""
        ),
        "delete_endpoint": f"/plataforma/api/containers/{workspace_id}",
        "destructive": True,
        "dry_run_default": True,
        "pages": {
            "direct_count": len(direct_ids),
            "cascade_count": len(related_ids),
            "direct_ids": sorted(direct_ids),
            "cascade_ids": sorted(related_ids),
            "tree": tree,
            "linked_outside_parent_tree": [page_summary(by_id[item]) for item in linked_outside_tree if item in by_id],
            "external_linked_pages": external_linked,
        },
        "guards": [
            "Exact --confirm-name must match the resolved workspace name when --yes is used.",
            "Optional --confirm-id must match the resolved workspace id when provided.",
            "Password-protected workspaces require successful workspace password validation before deletion.",
            "External linked pages block deletion unless --allow-linked-pages is provided.",
            "Reserved workspace names block deletion unless --force-reserved is provided.",
        ],
    }


def page_delete_plan(client: RejoinBIClient, selector: str) -> dict[str, Any]:
    pages = list_pages(client, all_containers=True, include_inactive=True, exclude_fictitious=False)
    target = resolve_page_from_pages(pages, selector)
    if not target:
        return {
            "found": False,
            "selector": selector,
            "destructive": True,
            "message": "Page not found.",
        }
    target_id = page_id(target)
    cascade_ids = collect_related_page_ids(pages, {target_id}, DELETE_PAGE_REFERENCE_FIELDS)
    full_link_ids = collect_related_page_ids(pages, {target_id}, DELETE_WORKSPACE_REFERENCE_FIELDS)
    extra_linked_ids = full_link_ids - cascade_ids
    tree, linked_outside_tree = build_page_tree(pages, {target_id}, cascade_ids)
    by_id = {page_id(page): page for page in pages if page_id(page)}
    return {
        "found": True,
        "selector": selector,
        "target": page_summary(target),
        "delete_endpoint": f"/plataforma/api/paginas/{target_id}",
        "destructive": True,
        "dry_run_default": True,
        "cascade": {
            "count": len(cascade_ids),
            "ids": sorted(cascade_ids),
            "descendant_ids": sorted(cascade_ids - {target_id}),
            "tree": tree,
            "linked_outside_parent_tree": [page_summary(by_id[item]) for item in linked_outside_tree if item in by_id],
        },
        "additional_linked_pages": [page_summary(by_id[item]) for item in sorted(extra_linked_ids) if item in by_id],
        "guards": [
            "Exact --confirm-page-id must match the resolved page id when --yes is used.",
            "Pages with descendants require --cascade.",
            "Fictitious page ids cannot be deleted directly.",
            "Additional linked pages block deletion unless --allow-linked-pages is provided.",
        ],
    }


def cmd_workspaceall(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspaces = load_workspaces(client)
    if args.json:
        print_payload({"success": True, "base_url": client.base_url, "workspaces": workspaces, "count": len(workspaces)})
    else:
        rows = []
        for item in workspaces:
            rows.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "active": as_bool_flag(bool(item.get("is_active"))),
                "locked": as_bool_flag(workspace_password_protected(item)),
                "status": item.get("deploy_status") or "",
                "last_upload": item.get("last_upload") or "",
            })
        print(render_table(rows, [
            ("id", "ID"),
            ("name", "Workspace"),
            ("active", "Active"),
            ("locked", "Locked"),
            ("status", "Status"),
            ("last_upload", "Last upload"),
        ]))
    return 0


def cmd_validate_workspace(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    password = secret_value(args.password, "REJOINBI_WORKSPACE_PASSWORD", "password")
    data, _ = client.request(
        "POST",
        "/plataforma/api/validate-container-password",
        json={"container_id": workspace.get("id"), "password": password},
        timeout=60,
    )
    client.save_session()
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_content(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    params = {"container_id": workspace.get("id"), "folder": args.folder or ""}
    data, _ = client.request("GET", "/plataforma/api/container-content", params=params, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def open_upload_files(paths: list[str], stack: ExitStack, *, allow_sensitive: bool = False) -> list[tuple[str, tuple[str, Any, str]]]:
    result = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise RejoinBIError(f"File not found: {path}")
        reason = sensitive_path_reason(path)
        if reason and not allow_sensitive:
            raise RejoinBIError(f"Refusing to upload sensitive-looking file {path}: {reason}. Use --allow-sensitive-files only after manual review.")
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        result.append(("files", (path.name, stack.enter_context(path.open("rb")), mime)))
    return result


def cmd_upload_files(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    if args.workspace_password:
        client.request(
            "POST",
            "/plataforma/api/validate-container-password",
            json={"container_id": workspace.get("id"), "password": args.workspace_password},
            timeout=60,
        )

    file_paths_map = {}
    for item in args.map or []:
        if "=" not in item:
            raise RejoinBIError(f"Invalid --map value: {item}. Use filename=target/folder.")
        key, value = item.split("=", 1)
        file_paths_map[key.strip()] = value.strip()

    with ExitStack() as stack:
        files = open_upload_files(args.files, stack, allow_sensitive=bool(args.allow_sensitive_files))
        form_data: list[tuple[str, str]] = [
            ("container_name", str(workspace.get("name") or "")),
            ("folder_path", args.folder or ""),
            ("commit_message", args.message or "Uploaded by rejoinbi-platform plugin"),
            ("restart_container", "true" if args.restart else "false"),
        ]
        if file_paths_map:
            form_data.append(("file_paths", json.dumps(file_paths_map, ensure_ascii=False)))
        data, _ = client.request("POST", "/plataforma/api/upload-multiple-files", data=form_data, files=files, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def iter_folder_files(root: Path, exclude_names: set[str], *, allow_sensitive: bool = False) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = {part.lower() for part in path.relative_to(root).parts}
        if rel_parts.intersection(exclude_names):
            continue
        if sensitive_path_reason(path.relative_to(root)) and not allow_sensitive:
            continue
        files.append(path)
    return files


def validate_zip_for_upload(zip_path: Path, *, allow_sensitive: bool = False) -> None:
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise RejoinBIError(f"Invalid ZIP file: {zip_path}") from exc
    with archive:
        for info in archive.infolist():
            raw_name = (info.filename or "").replace("\\", "/")
            if not raw_name or raw_name.endswith("/"):
                continue
            rel = PurePosixPath(raw_name)
            if rel.is_absolute() or any(part in ("", ".", "..") or part.endswith(":") for part in rel.parts):
                raise RejoinBIError(f"Refusing ZIP with unsafe entry path: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RejoinBIError(f"Refusing ZIP with symlink entry: {info.filename}")
            reason = sensitive_path_reason(Path(*rel.parts))
            if reason and not allow_sensitive:
                raise RejoinBIError(
                    f"Refusing ZIP with sensitive-looking entry {info.filename}: {reason}. "
                    "Use --allow-sensitive-files only after manual review."
                )


def choose_entry_file(files_payload: list[dict[str, Any]], startup_mode: str, selected_file: str = "") -> str | None:
    if startup_mode in {"command", "static"}:
        return None
    if selected_file:
        return selected_file.replace("\\", "/")
    paths = [str(item.get("path") or "").replace("\\", "/") for item in files_payload if isinstance(item, dict)]
    preferred = ("app.py", "main.py", "server.py", "index.py", "src/app.py", "index.html")
    lower_to_real = {p.lower(): p for p in paths}
    for name in preferred:
        if name in lower_to_real:
            return lower_to_real[name]
    for path in paths:
        if path.lower().endswith("/app.py") or path.lower().endswith("/main.py"):
            return path
    return paths[0] if paths else None


def poll_upload(client: RejoinBIClient, payload: dict[str, Any], timeout: int, interval: float) -> dict[str, Any]:
    if not payload.get("background_processing") or not payload.get("process_id"):
        return payload
    poll_url = payload.get("poll_url") or f"/plataforma/api/upload-status/{payload.get('process_id')}"
    deadline = time.time() + timeout
    last_payload = payload
    while time.time() < deadline:
        time.sleep(interval)
        status_payload, _ = client.request("GET", poll_url, timeout=60)
        last_payload = status_payload if isinstance(status_payload, dict) else {"raw": status_payload}
        status = str(last_payload.get("status") or "").lower()
        if status in {"completed", "error", "not_found"}:
            return last_payload
    raise RejoinBIError(f"Upload polling timed out. Last status: {last_payload}")


def select_app_file(
    client: RejoinBIClient,
    workspace: dict[str, Any],
    files_payload: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    selected = choose_entry_file(files_payload, args.startup_mode, args.selected_file or "")
    request_data = {
        "selected_file": selected,
        "rpa_support": bool(args.rpa_support),
        "auto_start": bool(args.auto_start),
        "python_path": args.python_path or "auto",
        "startup_command": args.startup_command or "",
        "startup_mode": args.startup_mode or "file",
        "container_id": workspace.get("id"),
        "container_name": workspace.get("name"),
        "github_url": workspace.get("github_url"),
        "railway_internal_url": workspace.get("railway_internal_url") or "",
    }
    data, _ = client.request("POST", "/plataforma/api/select-app-file", json=request_data, timeout=120)
    payload = data if isinstance(data, dict) else {"raw": data}
    result = poll_upload(client, payload, args.timeout, args.interval)
    return {
        "success": bool(result.get("success")),
        "selected_file": selected,
        "workspace": {"id": workspace.get("id"), "name": workspace.get("name")},
        "initial_response": payload,
        "final_response": result,
    }


def cmd_upload_zip_select(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    if args.workspace_password:
        client.request("POST", "/plataforma/api/validate-container-password", json={"container_id": workspace.get("id"), "password": args.workspace_password})
    zip_path = Path(args.zip).expanduser().resolve()
    if not zip_path.is_file():
        raise RejoinBIError(f"ZIP not found: {zip_path}")
    validate_zip_for_upload(zip_path, allow_sensitive=bool(args.allow_sensitive_files))
    with zip_path.open("rb") as handle:
        files = {"file": (zip_path.name, handle, "application/zip")}
        data, _ = client.request("POST", "/plataforma/api/extract-files", data={"container_id": str(workspace.get("id"))}, files=files, timeout=args.timeout)
    files_payload = list((data or {}).get("files") or []) if isinstance(data, dict) else []
    result = select_app_file(client, workspace, files_payload, args)
    print_payload(result, as_json=args.json)
    return 0


def cmd_upload_folder_select(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    if args.workspace_password:
        client.request("POST", "/plataforma/api/validate-container-password", json={"container_id": workspace.get("id"), "password": args.workspace_password})
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        raise RejoinBIError(f"Folder not found: {root}")
    exclude = set(args.exclude or [])
    with ExitStack() as stack:
        data_items: list[tuple[str, str]] = [("container_id", str(workspace.get("id")))]
        files = []
        for path in iter_folder_files(root, {item.lower() for item in exclude}, allow_sensitive=bool(args.allow_sensitive_files)):
            rel = str(path.relative_to(root)).replace("\\", "/")
            mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            data_items.append(("paths", rel))
            files.append(("files", (path.name, stack.enter_context(path.open("rb")), mime)))
        if not files:
            raise RejoinBIError("No files found to upload.")
        data, _ = client.request("POST", "/plataforma/api/upload-folder", data=data_items, files=files, timeout=args.timeout)
    files_payload = list((data or {}).get("files") or []) if isinstance(data, dict) else []
    result = select_app_file(client, workspace, files_payload, args)
    print_payload(result, as_json=args.json)
    return 0


def cmd_bi_projects(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/bi/projects", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_create_project(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = {"name": args.name}
    if args.password:
        payload["password"] = args.password
    data, _ = client.request("POST", "/plataforma/api/bi/projects", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_export(args: argparse.Namespace) -> int:
    client = make_client(args)
    output = Path(args.output or f"{args.project_id}.zip").expanduser().resolve()
    params = ""
    if args.project_password:
        params = f"?password={quote(args.project_password)}"
    client.download(bi_project_path(args.project_id, f"/export{params}"), output, timeout=args.timeout)
    print_payload({"success": True, "output": str(output)}, as_json=args.json)
    return 0


def bi_project_path(project_id: str, suffix: str = "") -> str:
    base = f"/plataforma/api/bi/projects/{quote(str(project_id), safe='')}"
    return f"{base}{suffix}"


def cmd_bi_tabs(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", bi_project_path(args.project_id, "/tabs"), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_tab_content(args: argparse.Namespace) -> int:
    client = make_client(args)
    path = path_with_query(bi_project_path(args.project_id, "/tabs/content"), {"name": args.tab})
    data, _ = client.request("GET", path, timeout=args.timeout)
    print_payload({"success": True, "project_id": args.project_id, "tab": args.tab, "content": data}, as_json=args.json)
    return 0


def cmd_bi_init_canvas(args: argparse.Namespace) -> int:
    require_yes(args, "bi-init-canvas initializes BI Studio canvas files and requires --yes.")
    client = make_client(args)
    data, _ = client.request("POST", bi_project_path(args.project_id, "/canvas/init"), json={}, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_create_tab(args: argparse.Namespace) -> int:
    require_yes(args, "bi-create-tab changes a BI Studio project and requires --yes.")
    payload = {"name": args.name}
    require_clean_json_text(payload, context="bi-create-tab payload")
    client = make_client(args)
    data, _ = client.request("POST", bi_project_path(args.project_id, "/tabs"), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_duplicate_tab(args: argparse.Namespace) -> int:
    require_yes(args, "bi-duplicate-tab changes a BI Studio project and requires --yes.")
    payload = {"new_name": args.new_name}
    if args.source_slug:
        payload["source_slug"] = args.source_slug
    if args.source_name:
        payload["source_name"] = args.source_name
    require_clean_json_text(payload, context="bi-duplicate-tab payload")
    client = make_client(args)
    data, _ = client.request("POST", bi_project_path(args.project_id, "/tabs/duplicate"), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_rename_tab(args: argparse.Namespace) -> int:
    require_yes(args, "bi-rename-tab changes a BI Studio project and requires --yes.")
    payload = {"new_name": args.new_name}
    if args.old_slug:
        payload["old_slug"] = args.old_slug
    if args.old_name:
        payload["old_name"] = args.old_name
    require_clean_json_text(payload, context="bi-rename-tab payload")
    client = make_client(args)
    data, _ = client.request("PATCH", bi_project_path(args.project_id, "/tabs/rename"), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_delete_tab(args: argparse.Namespace) -> int:
    require_yes(args, "bi-delete-tab deletes BI Studio tab files and requires --yes.")
    params: dict[str, Any] = {}
    if args.slug:
        params["slug"] = args.slug
    if args.name:
        params["name"] = args.name
    if not params:
        raise RejoinBIError("bi-delete-tab requires --slug or --name.")
    client = make_client(args)
    data, _ = client.request("DELETE", path_with_query(bi_project_path(args.project_id, "/tabs"), params), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_reorder_tabs(args: argparse.Namespace) -> int:
    require_yes(args, "bi-reorder-tabs changes BI Studio tab order and requires --yes.")
    order = split_list(args.order)
    if not order:
        raise RejoinBIError("bi-reorder-tabs requires --order with comma-separated tab names/slugs or a JSON array.")
    require_clean_json_text(order, context="bi-reorder-tabs order")
    client = make_client(args)
    data, _ = client.request("PATCH", bi_project_path(args.project_id, "/tabs/reorder"), json={"order": order}, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_load_layout(args: argparse.Namespace) -> int:
    client = make_client(args)
    params = {"tab": args.tab}
    data, _ = client.request("GET", path_with_query(bi_project_path(args.project_id, "/layout"), params), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_save_layout(args: argparse.Namespace) -> int:
    require_yes(args, "bi-save-layout writes BI Studio canvas layout/assets and requires --yes.")
    payload = load_json_file(args.data_file)
    if not isinstance(payload, dict):
        raise RejoinBIError("bi-save-layout --data-file must contain a JSON object.")
    if args.tab and not payload.get("tab"):
        payload["tab"] = args.tab
    if not payload.get("tab"):
        raise RejoinBIError("bi-save-layout requires --tab or a JSON payload containing tab.")
    require_clean_json_text(payload, context="bi-save-layout payload")
    client = make_client(args)
    data, _ = client.request("POST", bi_project_path(args.project_id, "/layout"), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_themes(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", bi_project_path(args.project_id, "/themes"), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_save_theme(args: argparse.Namespace) -> int:
    require_yes(args, "bi-save-theme changes BI Studio project themes and requires --yes.")
    payload = load_json_file(args.data_file)
    require_clean_json_text(payload, context="bi-save-theme payload")
    client = make_client(args)
    data, _ = client.request("POST", bi_project_path(args.project_id, "/themes"), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_bi_delete_theme(args: argparse.Namespace) -> int:
    require_yes(args, "bi-delete-theme deletes a BI Studio project theme and requires --yes.")
    client = make_client(args)
    data, _ = client.request("DELETE", bi_project_path(args.project_id, f"/themes/{quote(args.theme_id, safe='')}"), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def ensure_child_path(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RejoinBIError(f"Refusing path outside export root: {resolved_path}") from exc
    return resolved_path


def copy_or_move_export_path(root: Path, source: Path, target: Path, *, remove_old: bool, dry_run: bool) -> dict[str, Any]:
    source = ensure_child_path(root, source)
    target = ensure_child_path(root, target)
    result = {"source": str(source), "target": str(target), "exists": source.exists(), "changed": False}
    if not source.exists() or source == target:
        return result
    result["changed"] = True
    if dry_run:
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
        if remove_old:
            shutil.rmtree(source)
    else:
        shutil.copy2(source, target)
        if remove_old:
            source.unlink()
    return result


def replace_text_in_file(path: Path, replacements: list[tuple[str, str]], *, dry_run: bool) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")
    updated = text
    for old, new in replacements:
        if old and new and old != new:
            updated = updated.replace(old, new)
    if updated == text:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def ensure_parquet_requirement(root: Path, *, dry_run: bool) -> dict[str, Any]:
    parquet_files = [path for path in (root / "dados" / "df").rglob("*.parquet")] if (root / "dados" / "df").exists() else []
    requirements_path = root / "requirements.txt"
    if not parquet_files:
        return {"needed": False, "changed": False, "reason": "no_parquet_files"}
    existing = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    normalized = existing.lower()
    if "pyarrow" in normalized or "fastparquet" in normalized:
        return {"needed": True, "changed": False, "path": str(requirements_path), "engine_present": True}
    if not dry_run:
        requirements_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = "" if not existing or existing.endswith(("\n", "\r")) else "\n"
        requirements_path.write_text(existing + suffix + "pyarrow>=16.0.0\n", encoding="utf-8")
    return {
        "needed": True,
        "changed": True,
        "path": str(requirements_path),
        "reason": "parquet_files_require_pyarrow_or_fastparquet",
        "parquet_count": len(parquet_files),
    }


def fix_export_python_backslash_literals(root: Path, *, dry_run: bool) -> dict[str, Any]:
    """Fix BI Studio exports that accidentally emit an invalid backslash string literal."""
    bad = ".replace('" + "\\" + "', '/')"
    good = ".replace('\\\\', '/')"
    changed: list[str] = []
    for py_file in root.rglob("*.py"):
        rel_parts = {part.lower() for part in py_file.relative_to(root).parts}
        if rel_parts.intersection({"venv", ".venv", "__pycache__"}):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = py_file.read_text(encoding="utf-8-sig")
        if bad not in text:
            continue
        changed.append(str(py_file))
        if not dry_run:
            py_file.write_text(text.replace(bad, good), encoding="utf-8")
    return {
        "changed": bool(changed),
        "files": changed,
        "reason": "fixed_invalid_python_backslash_literal",
    }


def cmd_bi_normalize_export(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not root.is_dir():
        raise RejoinBIError(f"BI export path is not a directory: {root}")
    if not manifest_path.exists():
        raise RejoinBIError(f"manifest.json not found in BI export path: {root}")
    manifest = read_json(manifest_path, {})
    tabs = manifest.get("tabs") if isinstance(manifest.get("tabs"), list) else []
    used_slugs: set[str] = set()
    slug_changes: list[dict[str, Any]] = []
    path_changes: list[dict[str, Any]] = []
    text_changes: list[str] = []

    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        old_slug = safe_str(tab.get("slug") or "")
        if not old_slug:
            continue
        proposed = slugify_page_id(old_slug)
        if old_slug == "index":
            proposed = "index"
        base = proposed
        suffix = 2
        while proposed in used_slugs and proposed != old_slug:
            proposed = f"{base}-{suffix}"
            suffix += 1
        used_slugs.add(proposed)
        if proposed == old_slug:
            continue

        tab["slug"] = proposed
        slug_changes.append({"name": tab.get("name"), "old_slug": old_slug, "new_slug": proposed})
        replacements = [(old_slug, proposed), (quote(old_slug, safe=""), quote(proposed, safe=""))]

        file_pairs = [
            (root / "templates" / f"{old_slug}.html", root / "templates" / f"{proposed}.html"),
            (root / "layouts" / f"{old_slug}_layout.json", root / "layouts" / f"{proposed}_layout.json"),
            (root / "router" / f"{old_slug}_router.py", root / "router" / f"{proposed}_router.py"),
        ]
        dir_pairs = [
            (root / "static" / "css" / old_slug, root / "static" / "css" / proposed),
            (root / "static" / "js" / old_slug, root / "static" / "js" / proposed),
        ]
        for source, target in [*file_pairs, *dir_pairs]:
            path_changes.append(copy_or_move_export_path(root, source, target, remove_old=args.remove_old, dry_run=args.dry_run))
        new_template = root / "templates" / f"{proposed}.html"
        if replace_text_in_file(new_template, replacements, dry_run=args.dry_run):
            text_changes.append(str(new_template))

    manifest_changed = bool(slug_changes)
    if manifest_changed and not args.dry_run:
        write_json(manifest_path, manifest)
    parquet_requirement = ensure_parquet_requirement(root, dry_run=args.dry_run)
    python_syntax_fix = fix_export_python_backslash_literals(root, dry_run=args.dry_run)
    result = {
        "success": True,
        "path": str(root),
        "dry_run": bool(args.dry_run),
        "manifest_changed": manifest_changed,
        "slug_changes": slug_changes,
        "path_changes": [item for item in path_changes if item.get("changed")],
        "text_changes": text_changes,
        "parquet_requirement": parquet_requirement,
        "python_syntax_fix": python_syntax_fix,
        "notes": [
            "Visible BI Studio tab names can stay localized with accents.",
            "Published workspace files, slugs, platform page routes, and page arquivo values should stay ASCII.",
            "Run upload-folder-select or deploy pages again after normalization, then run smoke-pages.",
        ],
    }
    print_payload(result, as_json=args.json)
    return 0


def poll_publish(client: RejoinBIClient, project_id: str, job_id: str, timeout: int, interval: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        time.sleep(interval)
        data, _ = client.request("GET", bi_project_path(project_id, f"/internal-publish/status/{quote(str(job_id), safe='')}"), timeout=60)
        last = data if isinstance(data, dict) else {"raw": data}
        if last.get("done") or str(last.get("status") or "").lower() in {"success", "error", "cancelled"}:
            return last
    raise RejoinBIError(f"Publish polling timed out. Last status: {last}")


def bi_manifest_slug_issues(client: RejoinBIClient, project_id: str) -> list[dict[str, Any]]:
    manifest, _ = client.request("GET", bi_project_path(project_id, "/manifest"), timeout=60)
    tabs = manifest.get("tabs") if isinstance(manifest, dict) and isinstance(manifest.get("tabs"), list) else []
    issues: list[dict[str, Any]] = []
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        slug = safe_str(tab.get("slug") or "")
        if not slug or slug == "index":
            continue
        ascii_slug = slugify_page_id(slug)
        if slug != ascii_slug:
            issues.append({
                "name": tab.get("name"),
                "slug": slug,
                "recommended_slug": ascii_slug,
                "reason": "non_ascii_or_unsafe_technical_slug",
            })
    return issues


POST_PUBLISH_FATAL_PATTERNS = (
    ("python_syntax_error", "syntaxerror"),
    ("python_traceback", "traceback (most recent call last)"),
    ("parquet_engine_missing", "unable to find a usable engine"),
    ("parquet_engine_missing", "pyarrow is required for parquet support"),
    ("parquet_engine_missing", "fastparquet is required for parquet support"),
    ("materialized_dataframe_missing", "nenhum artefato legível"),
)


def payload_text_tail(payload: Any, *, limit: int = 6000) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            parts.append(value)
            return
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested)
            return

    visit(payload)
    text = "\n".join(part for part in parts if part)
    return text[-limit:]


def workspace_log_running(payload: dict[str, Any]) -> bool:
    runtime_details = payload.get("runtime_details") if isinstance(payload.get("runtime_details"), dict) else {}
    status_values = [
        payload.get("status"),
        payload.get("docker_status"),
        runtime_details.get("status"),
    ]
    if runtime_details.get("running") is True:
        return True
    return any(str(value or "").strip().lower() == "running" for value in status_values)


def analyze_workspace_runtime(logs_payload: dict[str, Any]) -> dict[str, Any]:
    text_tail = payload_text_tail(logs_payload)
    lower_tail = text_tail.lower()
    findings: list[dict[str, str]] = []
    for code, pattern in POST_PUBLISH_FATAL_PATTERNS:
        if pattern in lower_tail and not any(item.get("code") == code for item in findings):
            findings.append({"severity": "fatal", "code": code, "pattern": pattern})
    return {
        "running": workspace_log_running(logs_payload),
        "fatal_findings": findings,
        "log_tail": text_tail,
    }


def wait_workspace_post_publish_ready(
    client: RejoinBIClient,
    workspace: dict[str, Any],
    *,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    workspace_id = workspace.get("id")
    deadline = time.time() + max(float(timeout), 0.0)
    attempts: list[dict[str, Any]] = []
    last_status: dict[str, Any] = {}
    last_logs: dict[str, Any] = {}
    last_analysis: dict[str, Any] = {}

    while time.time() <= deadline:
        attempt: dict[str, Any] = {"checked_at": utc_now()}
        try:
            status_payload, _ = client.request("GET", f"/plataforma/api/containers/{workspace_id}/status", timeout=60)
            last_status = status_payload if isinstance(status_payload, dict) else {"raw": status_payload}
            attempt["status"] = {
                "success": last_status.get("success"),
                "status": last_status.get("status"),
                "details_status": (last_status.get("details") or {}).get("status") if isinstance(last_status.get("details"), dict) else None,
                "running": (last_status.get("details") or {}).get("running") if isinstance(last_status.get("details"), dict) else None,
            }
        except RejoinBIError as exc:
            attempt["status_error"] = str(exc)

        try:
            logs_payload, _ = client.request("GET", f"/plataforma/api/containers/{workspace_id}/logs", timeout=60)
            last_logs = logs_payload if isinstance(logs_payload, dict) else {"raw": logs_payload}
            last_analysis = analyze_workspace_runtime(last_logs)
            attempt["logs"] = {
                "success": last_logs.get("success"),
                "status": last_logs.get("status"),
                "docker_status": last_logs.get("docker_status"),
                "running": last_analysis.get("running"),
                "fatal_findings": last_analysis.get("fatal_findings"),
            }
        except RejoinBIError as exc:
            attempt["logs_error"] = str(exc)

        attempts.append(attempt)
        fatal_findings = last_analysis.get("fatal_findings") if isinstance(last_analysis, dict) else []
        if fatal_findings:
            return {
                "success": False,
                "reason": "runtime_logs_contain_fatal_findings",
                "workspace": {"id": workspace.get("id"), "name": workspace.get("name")},
                "fatal_findings": fatal_findings,
                "status": last_status,
                "logs_summary": {
                    "status": last_logs.get("status"),
                    "docker_status": last_logs.get("docker_status"),
                    "running": last_analysis.get("running"),
                    "log_tail": last_analysis.get("log_tail"),
                },
                "attempts": attempts,
            }
        if last_analysis.get("running"):
            return {
                "success": True,
                "workspace": {"id": workspace.get("id"), "name": workspace.get("name")},
                "status": last_status,
                "logs_summary": {
                    "status": last_logs.get("status"),
                    "docker_status": last_logs.get("docker_status"),
                    "running": True,
                },
                "attempts": attempts,
            }
        time.sleep(max(float(interval), 0.5))

    return {
        "success": False,
        "reason": "workspace_runtime_not_running_before_timeout",
        "workspace": {"id": workspace.get("id"), "name": workspace.get("name")},
        "status": last_status,
        "logs_summary": {
            "status": last_logs.get("status") if isinstance(last_logs, dict) else None,
            "docker_status": last_logs.get("docker_status") if isinstance(last_logs, dict) else None,
            "running": last_analysis.get("running") if isinstance(last_analysis, dict) else False,
            "log_tail": last_analysis.get("log_tail") if isinstance(last_analysis, dict) else "",
        },
        "attempts": attempts,
    }


def cmd_publish_bi(args: argparse.Namespace) -> int:
    client = make_client(args)
    slug_issues = bi_manifest_slug_issues(client, args.project_id)
    if slug_issues and not args.allow_non_ascii_routes:
        print_payload({
            "success": False,
            "error": "BI Studio project contains non-ASCII/unsafe technical tab slugs. Direct publish is blocked to avoid broken workspace/page routes.",
            "project_id": args.project_id,
            "slug_issues": slug_issues,
            "next_steps": [
                "Export with bi-export.",
                "Extract the ZIP locally.",
                "Run bi-normalize-export --path <extracted-export> --remove-old.",
                "Upload the normalized folder with upload-folder-select or deploy-manifest.",
                "Create/update pages with accented visible names but ASCII file/route values, then run smoke-pages.",
            ],
        }, as_json=args.json)
        return 1
    workspace = resolve_workspace(client, args.workspace)
    password = args.workspace_password or os.environ.get("REJOINBI_WORKSPACE_PASSWORD") or ""
    payload = {
        "container_id": workspace.get("id"),
        "password": password,
        "python_version": args.python_version or "auto",
    }
    data, _ = client.request(
        "POST",
        bi_project_path(args.project_id, "/internal-publish/start"),
        json=payload,
        timeout=60,
    )
    result = data if isinstance(data, dict) else {"raw": data}
    if result.get("job_id"):
        final = poll_publish(client, args.project_id, result["job_id"], args.timeout, args.interval)
        result = {"initial_response": result, "final_response": final, "success": bool(final.get("success"))}
    publish_success = bool(result.get("success"))
    if publish_success and not args.no_post_publish_check:
        post_check = wait_workspace_post_publish_ready(
            client,
            workspace,
            timeout=args.post_publish_timeout,
            interval=args.interval,
        )
        result["post_publish_check"] = post_check
        result["success"] = bool(post_check.get("success"))
    print_payload(result, as_json=args.json)
    return 0 if bool(result.get("success")) else 1


def cmd_echarts_template(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/bi/echarts/template", params={"id": args.template_id}, timeout=60)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(str(data.get("code") or ""), encoding="utf-8")
        print_payload({"success": True, "template_id": args.template_id, "output": str(output)}, as_json=args.json)
    else:
        print_payload(data, as_json=args.json)
    return 0


def build_studio_inventory(client: RejoinBIClient, args: argparse.Namespace) -> dict[str, Any]:
    timeout = int(getattr(args, "timeout", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
    limit = int(getattr(args, "limit", 25) or 25)
    include_raw = bool(getattr(args, "include_raw", False))
    include_files = bool(getattr(args, "include_files", True))
    include_sessions = bool(getattr(args, "include_sessions", True))
    include_global_context = bool(getattr(args, "include_global_context", True))
    requested_project_id = safe_str(getattr(args, "project_id", "") or "")
    requested_project_uid = safe_str(getattr(args, "project_uid", "") or "")
    issues: list[dict[str, Any]] = []

    bi_payload = optional_inventory_get(
        client,
        "/plataforma/api/bi/projects",
        label="bi_projects",
        timeout=timeout,
        issues=issues,
    )
    projects = extract_inventory_items(bi_payload or {}, ("projects", "data", "items", "results"))
    project_records = [project for project in projects if isinstance(project, dict)]
    if requested_project_id or requested_project_uid:
        project_records = [
            project
            for project in project_records
            if (
                not requested_project_id
                or safe_str(first_present_value(project, ("id", "project_id", "projectId"))) == requested_project_id
            )
            and (
                not requested_project_uid
                or safe_str(first_present_value(project, ("uid", "project_uid", "projectUid"))) == requested_project_uid
            )
        ]

    data_engine_base = "/plataforma/data-engine"
    data_engine: dict[str, Any] = {}
    global_status = optional_inventory_get(
        client,
        f"{data_engine_base}/api/status",
        label="data_engine_status",
        timeout=timeout,
        issues=issues,
    )
    data_engine["status"] = (
        inventory_endpoint_result(global_status, limit=limit, include_raw=include_raw)
        if global_status is not None
        else inventory_error_result("status endpoint unavailable")
    )
    drivers_payload = optional_inventory_get(
        client,
        f"{data_engine_base}/api/db/providers/sqlserver/drivers",
        label="sqlserver_drivers",
        timeout=timeout,
        issues=issues,
    )
    data_engine["sqlserver_drivers"] = (
        inventory_endpoint_result(drivers_payload, limit=limit, include_raw=include_raw)
        if drivers_payload is not None
        else inventory_error_result("sqlserver drivers endpoint unavailable")
    )

    project_summaries: list[dict[str, Any]] = []
    for project in project_records:
        ref = project_inventory_ref(project)
        query = project_query_from_ref(ref)
        project_summary: dict[str, Any] = {
            "project": compact_inventory_item(project),
            "project_ref": ref,
            "data_engine": {},
        }
        if not query:
            project_summary["data_engine"]["skipped"] = "Project has no id or uid for Data Engine project-scoped endpoints."
            project_summaries.append(project_summary)
            continue

        endpoint_specs: list[tuple[str, str, tuple[str, ...]]] = []
        if include_sessions:
            endpoint_specs.append(("session", f"{data_engine_base}/api/session/status", INVENTORY_COLLECTION_KEYS))
        endpoint_specs.extend([
            ("db_connections", f"{data_engine_base}/api/db/connections", ("connections", "data", "items", "results")),
            ("repository", f"{data_engine_base}/api/repository/list", ("items", "children", "files", "data", "results")),
            ("datasets", f"{data_engine_base}/api/datasets/list", ("datasets", "data", "items", "results")),
        ])
        if include_files:
            endpoint_specs.append(("files", f"{data_engine_base}/api/list-files", ("files", "items", "data", "results")))
        if include_global_context:
            endpoint_specs.append(("global_context", f"{data_engine_base}/api/repository/global-context", INVENTORY_COLLECTION_KEYS))

        for key, path, collection_keys in endpoint_specs:
            payload = optional_inventory_get(
                client,
                path,
                label=f"data_engine_{key}",
                timeout=timeout,
                issues=issues,
                query=query,
            )
            if payload is None:
                project_summary["data_engine"][key] = inventory_error_result("endpoint unavailable")
            else:
                project_summary["data_engine"][key] = inventory_endpoint_result(
                    payload,
                    limit=limit,
                    include_raw=include_raw,
                    collection_keys=collection_keys,
                )
        project_summaries.append(project_summary)

    result: dict[str, Any] = {
        "success": True,
        "read_only": True,
        "tenant": tenant_host_from_base_url(client.base_url),
        "generated_at": utc_now(),
        "bi_studio": {
            "projects_endpoint": (
                inventory_endpoint_result(
                    bi_payload,
                    limit=limit,
                    include_raw=include_raw,
                    collection_keys=("projects", "data", "items", "results"),
                )
                if bi_payload is not None
                else inventory_error_result("BI Studio projects endpoint unavailable")
            ),
            "projects_count": len(project_records),
            "projects": project_summaries,
        },
        "data_engine": data_engine,
        "issues": issues,
        "usage_notes": [
            "This command is read-only and redacts password, token, key, secret, and connection-string fields.",
            "Use --project-id or --project-uid to inspect one project. Use --include-raw only for sanitized troubleshooting output.",
            "Use data-engine repository-content, preview-file, dataset-get, or query-preview only after reviewing this inventory.",
        ],
    }
    return result


def cmd_studio_inventory(args: argparse.Namespace) -> int:
    client = make_client(args)
    result = build_studio_inventory(client, args)
    if getattr(args, "output", None):
        output = Path(args.output).expanduser().resolve()
        write_json(output, result)
        result = {**result, "output": str(output)}
    print_payload(result, as_json=args.json)
    return 0


def load_users(client: RejoinBIClient) -> list[dict[str, Any]]:
    data, _ = client.request("GET", "/plataforma/api/users", timeout=60)
    if isinstance(data, dict):
        return list(data.get("users") or [])
    return []


def resolve_user(client: RejoinBIClient, selector: str) -> dict[str, Any]:
    raw = str(selector or "").strip().lower()
    for user in load_users(client):
        user_id = str(user.get("user_id") or user.get("id") or "").strip().lower()
        email = str(user.get("email") or "").strip().lower()
        if raw and raw in {user_id, email}:
            return user
    raise RejoinBIError(f"User not found: {selector}")


def cmd_users(args: argparse.Namespace) -> int:
    client = make_client(args)
    users = load_users(client)
    if args.profile:
        wanted = normalize_text(args.profile)
        users = [user for user in users if normalize_text(user.get("perfil")) == wanted]
    if args.json:
        print_payload({"success": True, "base_url": client.base_url, "users": users, "count": len(users)})
    else:
        print(render_table(users, [
            ("user_id", "ID"),
            ("email", "Email"),
            ("nome", "Name"),
            ("perfil", "Profile"),
            ("setor", "Department"),
            ("ultimo_acesso", "Last access"),
        ]))
    return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = {
        "email": args.email.strip().lower(),
        "nome": args.name.strip(),
        "matricula": args.matricula or "",
        "setor": args.setor or "Codex",
        "contato": args.contato or "",
        "perfil": args.perfil,
    }
    data, _ = client.request("POST", "/plataforma/api/register", json=payload, timeout=60)
    result = data if isinstance(data, dict) else {"raw": data}
    try:
        created = resolve_user(client, args.email)
        result = {**result, "user": created}
    except RejoinBIError:
        pass
    print_payload(result, as_json=args.json)
    return 0


def cmd_set_user_password(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    password = secret_value(args.password, "REJOINBI_NEW_PASSWORD", "new-password")
    payload = {
        "user_id": user.get("user_id") or user.get("id"),
        "newPassword": password,
        "confirmPassword": password,
    }
    data, _ = client.request("POST", "/plataforma/api/change-user-password", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_delete_user(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    if not args.yes:
        raise RejoinBIError("Deleting users requires --yes.")
    data, _ = client.request(
        "POST",
        "/plataforma/api/delete-user",
        json={"user_id": user.get("user_id") or user.get("id")},
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_user_permissions(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    data, _ = client.request(
        "GET",
        f"/plataforma/api/user-permissions/{user.get('user_id') or user.get('id')}",
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            payload = json.loads(raw)
            if isinstance(payload, list):
                return [str(item).strip() for item in payload if str(item).strip()]
        except Exception:
            pass
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_json_file(path: str) -> Any:
    payload_path = Path(path).expanduser().resolve()
    if not payload_path.is_file():
        raise RejoinBIError(f"JSON file not found: {payload_path}")
    return json.loads(payload_path.read_text(encoding="utf-8-sig"))


def image_file_to_data_uri(path: str) -> str:
    image_path = Path(path).expanduser().resolve()
    if not image_path.is_file():
        raise RejoinBIError(f"Image file not found: {image_path}")
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def tenant_file_stem(client: RejoinBIClient) -> str:
    host = tenant_host_from_base_url(client.base_url).lower()
    return re.sub(r"[^a-z0-9._-]+", "-", host).strip("-") or "tenant"


def default_branding_backup_path(client: RejoinBIClient, label: str = "branding") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.home() / "Downloads" / "plugin" / "branding-backups" / f"{tenant_file_stem(client)}-{label}-{timestamp}.json"


def platform_config_payload_from_loaded(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RejoinBIError("Platform branding backup must contain a JSON object.")
    if isinstance(data.get("platform_config"), dict):
        data = data["platform_config"]
    if isinstance(data.get("config"), dict):
        payload = dict(data["config"])
        if data.get("browser_title") and not payload.get("browser_title"):
            payload["browser_title"] = data.get("browser_title")
        return payload
    return dict(data)


def save_platform_config_backup(client: RejoinBIClient, output: str | None = None, *, label: str = "branding") -> tuple[dict[str, Any], Path]:
    data, _ = client.request("GET", "/plataforma/api/platform-config", timeout=60)
    if not isinstance(data, dict):
        raise RejoinBIError("Platform config backup returned a non-object response.")
    backup_path = Path(output).expanduser().resolve() if output else default_branding_backup_path(client, label)
    write_json(backup_path, data)
    return data, backup_path


def cmd_update_user(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    payload = {
        "user_id": user.get("user_id") or user.get("id"),
        "nome": args.name if args.name is not None else user.get("nome", ""),
        "matricula": args.matricula if args.matricula is not None else user.get("matricula", ""),
        "setor": args.setor if args.setor is not None else user.get("setor", ""),
        "email": user.get("email", ""),
        "perfil": args.perfil if args.perfil is not None else user.get("perfil", "Usuario"),
        "contato": args.contato if args.contato is not None else user.get("contato", ""),
    }
    data, _ = client.request("POST", "/plataforma/api/update-user", json=payload, timeout=60)
    result = data if isinstance(data, dict) else {"raw": data}
    try:
        result = {**result, "user": resolve_user(client, str(user.get("email") or args.user))}
    except RejoinBIError:
        pass
    print_payload(result, as_json=args.json)
    return 0


def cmd_set_user_permissions(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    if args.permissions_file:
        payload = load_json_file(args.permissions_file)
        if not isinstance(payload, dict):
            raise RejoinBIError("Permissions file must contain a JSON object.")
        permissions = split_list(payload.get("permissions", []))
        denied_permissions = split_list(payload.get("denied_permissions", []))
    else:
        permissions = split_list(args.permissions)
        denied_permissions = split_list(args.denied_permissions)
    data, _ = client.request(
        "POST",
        "/plataforma/api/update-permissions",
        json={
            "user_id": user.get("user_id") or user.get("id"),
            "permissions": permissions,
            "denied_permissions": denied_permissions,
        },
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_recalculate_permissions(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Recalculating permissions for all users requires --yes.")
    client = make_client(args)
    data, _ = client.request("POST", "/plataforma/api/recalcular-permissoes", json={}, timeout=120)
    print_payload(data, as_json=args.json)
    return 0


def load_groups(client: RejoinBIClient) -> list[dict[str, Any]]:
    data, _ = client.request("GET", "/plataforma/api/groups", timeout=60)
    if isinstance(data, dict):
        return list(data.get("groups") or data.get("grupos") or [])
    return []


def resolve_group(client: RejoinBIClient, selector: str) -> dict[str, Any]:
    raw = str(selector or "").strip().lower()
    for group in load_groups(client):
        group_id = str(group.get("id") or "").strip().lower()
        name = str(group.get("nome") or group.get("name") or "").strip().lower()
        if raw and raw in {group_id, name}:
            return group
    raise RejoinBIError(f"Group not found: {selector}")


def cmd_groups(args: argparse.Namespace) -> int:
    client = make_client(args)
    groups = load_groups(client)
    if args.json:
        print_payload({"success": True, "groups": groups, "count": len(groups)})
    else:
        print(render_table(groups, [
            ("id", "ID"),
            ("nome", "Group"),
            ("descricao", "Description"),
            ("cor", "Color"),
        ]))
    return 0


def cmd_create_group(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = {
        "nome": args.name,
        "descricao": args.description or "",
        "permissoes": split_list(args.permissions),
        "cor": args.color or "#6c757d",
    }
    data, _ = client.request("POST", "/plataforma/api/create-group", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_update_group(args: argparse.Namespace) -> int:
    client = make_client(args)
    group = resolve_group(client, args.group)
    payload = {
        "id": group.get("id"),
        "nome": args.name if args.name is not None else group.get("nome", ""),
        "descricao": args.description if args.description is not None else group.get("descricao", ""),
        "permissoes": split_list(args.permissions) if args.permissions is not None else split_list(group.get("permissoes", [])),
        "cor": args.color if args.color is not None else group.get("cor", "#6c757d"),
    }
    data, _ = client.request("POST", "/plataforma/api/update-group", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_delete_group(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Deleting groups requires --yes.")
    client = make_client(args)
    group = resolve_group(client, args.group)
    data, _ = client.request("POST", "/plataforma/api/delete-group", json={"id": group.get("id")}, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_assign_user_group(args: argparse.Namespace) -> int:
    client = make_client(args)
    user = resolve_user(client, args.user)
    group = resolve_group(client, args.group)
    data, _ = client.request(
        "POST",
        "/plataforma/api/assign-user-to-group",
        json={
            "user_id": user.get("user_id") or user.get("id"),
            "group_id": group.get("id"),
            "action": args.action,
        },
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_users_for_groups(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/users-for-groups", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_announcements(args: argparse.Namespace) -> int:
    client = make_client(args)
    path = "/plataforma/api/anuncios/ativos" if args.active else "/plataforma/api/anuncios/historico"
    data, _ = client.request("GET", path, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_announcement_groups(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/grupos", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_create_announcement(args: argparse.Namespace) -> int:
    client = make_client(args)
    groups = split_list(args.groups)
    payload = {
        "titulo": args.title,
        "mensagem": args.message,
        "prioridade": args.priority,
        "enviar_todos": str(bool(args.all)).lower(),
        "grupos_destino": groups,
    }
    if args.expires:
        payload["data_expiracao"] = args.expires
    if args.color:
        payload["cor"] = args.color
    if args.icon:
        payload["icone"] = args.icon
    if args.file:
        with ExitStack() as stack:
            file_path = Path(args.file).expanduser().resolve()
            if not file_path.is_file():
                raise RejoinBIError(f"Announcement file not found: {file_path}")
            handle = stack.enter_context(file_path.open("rb"))
            form_data = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value) for key, value in payload.items()}
            files = {"arquivo": (file_path.name, handle, mimetypes.guess_type(str(file_path))[0] or "application/octet-stream")}
            data, _ = client.request("POST", "/plataforma/api/anuncios", data=form_data, files=files, timeout=120)
    else:
        data, _ = client.request("POST", "/plataforma/api/anuncios", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_delete_announcement(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Deleting announcements requires --yes.")
    client = make_client(args)
    announcement_id = required_int(args, "announcement_id", "--announcement-id")
    data, _ = client.request("DELETE", f"/plataforma/api/anuncios/{announcement_id}", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_platform_config(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/platform-config", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_colors_config(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/cores-config", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def platform_config_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if getattr(args, "data_file", None):
        data = load_json_file(args.data_file)
        payload.update(platform_config_payload_from_loaded(data))
    for attr, key in (
        ("browser_title", "browser_title"),
        ("logo_width", "logo_width"),
        ("logo_menu_width", "logo_menu_width"),
    ):
        value = getattr(args, attr, None)
        if value is not None:
            payload[key] = value
    if getattr(args, "colors_file", None):
        payload["cores"] = load_json_file(args.colors_file)
    if getattr(args, "logo_image_file", None):
        payload["logo_image"] = image_file_to_data_uri(args.logo_image_file)
    icon_file = getattr(args, "icon_image_file", None) or getattr(args, "favicon_image_file", None)
    if icon_file:
        payload["icon_image"] = image_file_to_data_uri(icon_file)
    if getattr(args, "logo_menu_image_file", None):
        payload["logo_menu_image"] = image_file_to_data_uri(args.logo_menu_image_file)
    if getattr(args, "remove_logo", False):
        payload["remove_logo"] = True
    if getattr(args, "remove_icon", False) or getattr(args, "remove_favicon", False):
        payload["remove_icon"] = True
    if getattr(args, "remove_logo_menu", False):
        payload["remove_logo_menu"] = True
    return payload


def cmd_set_platform_config(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = platform_config_payload_from_args(args)
    if not payload:
        raise RejoinBIError("No platform config values provided.")
    data, _ = client.request("POST", "/plataforma/api/platform-config", json=payload, timeout=120)
    print_payload(data, as_json=args.json)
    return 0


def cmd_export_platform_config(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/platform-config", timeout=60)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print_payload({"success": True, "output": str(output), "platform_config": data}, as_json=args.json)
    return 0


def cmd_backup_platform_branding(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, backup_path = save_platform_config_backup(client, args.output, label="branding-backup")
    print_payload({
        "success": True,
        "base_url": client.base_url,
        "backup_output": str(backup_path),
        "browser_title": data.get("browser_title") or (data.get("config") or {}).get("browser_title"),
        "message": "Platform branding backup saved.",
    }, as_json=args.json)
    return 0


def cmd_platform_title(args: argparse.Namespace) -> int:
    client = make_client(args)
    current_data, _ = client.request("GET", "/plataforma/api/platform-config", timeout=60)
    current_title = current_data.get("browser_title") or (current_data.get("config") or {}).get("browser_title")
    new_title = str(getattr(args, "title", "") or "").strip()
    if not new_title:
        print_payload({
            "success": True,
            "base_url": client.base_url,
            "browser_title": current_title,
            "message": "Current Rejoin BI platform browser title.",
            "change_command": f"python scripts/rejoinbi.py --tenant {tenant_host_from_base_url(client.base_url)} platform-title --title \"Novo titulo\"",
        }, as_json=args.json)
        return 0

    _backup_data, backup_path = save_platform_config_backup(client, args.backup_output, label="before-title-change")
    data, _ = client.request("POST", "/plataforma/api/platform-config", json={"browser_title": new_title}, timeout=120)
    print_payload({
        "success": True,
        "base_url": client.base_url,
        "previous_browser_title": current_title,
        "browser_title": new_title,
        "backup_output": str(backup_path),
        "changed_fields": ["browser_title"],
        "platform_response": data,
        "restore_command": f"python scripts/rejoinbi.py --tenant {tenant_host_from_base_url(client.base_url)} restore-platform-branding --backup \"{backup_path}\" --yes",
    }, as_json=args.json)
    return 0


def cmd_set_platform_branding(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = platform_config_payload_from_args(args)
    if not payload:
        raise RejoinBIError("No branding values provided.")
    _backup_data, backup_path = save_platform_config_backup(client, args.backup_output, label="before-branding-change")
    data, _ = client.request("POST", "/plataforma/api/platform-config", json=payload, timeout=120)
    print_payload({
        "success": True,
        "base_url": client.base_url,
        "backup_output": str(backup_path),
        "changed_fields": sorted(payload.keys()),
        "platform_response": data,
        "restore_command": f"python scripts/rejoinbi.py --tenant {tenant_host_from_base_url(client.base_url)} restore-platform-branding --backup \"{backup_path}\" --yes",
    }, as_json=args.json)
    return 0


def cmd_restore_platform_branding(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Restoring platform branding requires --yes.")
    client = make_client(args)
    backup_data = load_json_file(args.backup)
    payload = platform_config_payload_from_loaded(backup_data)
    if not payload:
        raise RejoinBIError("Backup does not contain platform branding values.")
    pre_restore_path = None
    if not args.no_pre_restore_backup:
        _current_data, pre_restore_path = save_platform_config_backup(client, args.backup_output, label="before-branding-restore")
    data, _ = client.request("POST", "/plataforma/api/platform-config", json=payload, timeout=120)
    print_payload({
        "success": True,
        "base_url": client.base_url,
        "restored_from": str(Path(args.backup).expanduser().resolve()),
        "pre_restore_backup": str(pre_restore_path) if pre_restore_path else None,
        "restored_fields": sorted(payload.keys()),
        "platform_response": data,
    }, as_json=args.json)
    return 0


def cmd_restore_platform_config_defaults(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Restoring platform config defaults requires --yes.")
    client = make_client(args)
    data, _ = client.request("POST", "/plataforma/api/platform-config/restore-defaults", json={}, timeout=120)
    print_payload(data, as_json=args.json)
    return 0


def cmd_ai_config_get(args: argparse.Namespace) -> int:
    client = make_client(args)
    params = {"pagina_id": args.page_id}
    if args.workspace:
        params["container_id"] = safe_str(resolve_workspace(client, args.workspace).get("id"))
    elif args.container_id:
        params["container_id"] = safe_str(args.container_id)
    if args.config_id:
        params["config_id"] = safe_str(args.config_id)
    data, _ = client.request("GET", "/plataforma/api/ai-config", params=params, timeout=60)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_ai_config_set(args: argparse.Namespace) -> int:
    client = make_client(args)
    if args.data_file:
        payload = load_json_file(args.data_file)
        if not isinstance(payload, dict):
            raise RejoinBIError("AI config file must contain a JSON object.")
    else:
        payload = {}
    payload["pagina_id"] = args.page_id or payload.get("pagina_id")
    if args.workspace:
        payload["container_id"] = resolve_workspace(client, args.workspace).get("id")
    elif args.container_id:
        payload["container_id"] = args.container_id
    for attr, key in (
        ("business_context", "contexto_negocio"),
        ("title", "titulo_customizado"),
        ("metrics", "metricas_principais"),
        ("objectives", "objetivos_dashboard"),
        ("glossary", "glossario_termos"),
        ("alerts", "alertas_customizados"),
        ("benchmarks", "benchmarks"),
        ("historical_insights", "insights_historicos"),
        ("analysis_priority", "prioridade_analise"),
        ("detail_level", "nivel_detalhe"),
        ("recommendation_focus", "foco_recomendacoes"),
        ("forced_key_id", "forced_key_id"),
        ("forced_key_name", "forced_key_name"),
        ("forced_key_model", "forced_key_model"),
        ("forced_reasoning_effort", "forced_reasoning_effort"),
        ("forced_service_tier", "forced_service_tier"),
        ("page_name", "nome_pagina"),
        ("full_path", "caminho_completo"),
    ):
        value = getattr(args, attr, None)
        if value is not None:
            payload[key] = value
    if args.active is not None:
        payload["ativo"] = "True" if args.active else "False"
    if not payload.get("pagina_id"):
        raise RejoinBIError("AI config requires --page-id or data_file.pagina_id.")
    if not payload.get("contexto_negocio"):
        raise RejoinBIError("AI config requires contexto_negocio / --business-context.")
    data, _ = client.request("POST", "/plataforma/api/ai-config", json=payload, timeout=120)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_ai_config_delete(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Deleting AI config requires --yes.")
    client = make_client(args)
    params = {"pagina_id": args.page_id}
    if args.workspace:
        params["container_id"] = safe_str(resolve_workspace(client, args.workspace).get("id"))
    elif args.container_id:
        params["container_id"] = safe_str(args.container_id)
    if args.config_id:
        params["config_id"] = safe_str(args.config_id)
    data, _ = client.request("DELETE", "/plataforma/api/ai-config", params=params, timeout=60)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_ai_config_cleanup(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RejoinBIError("Cleaning orphan AI configs requires --yes.")
    client = make_client(args)
    data, _ = client.request("POST", "/plataforma/api/ai-config/cleanup", json={}, timeout=120)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_storage_path(args: argparse.Namespace) -> int:
    client = make_client(args)
    if args.path:
        data, _ = client.request("POST", "/api/system/storage-path", json={"path": args.path}, timeout=60)
    else:
        data, _ = client.request("GET", "/api/system/storage-path", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def compact_params(**items: Any) -> dict[str, Any]:
    return {key: value for key, value in items.items() if value not in (None, "")}


def parse_query_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in getattr(args, "query", None) or []:
        if "=" not in item:
            raise RejoinBIError(f"Invalid --query value: {item}. Use key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RejoinBIError(f"Invalid --query value: {item}. Key cannot be empty.")
        if key in params:
            current = params[key]
            if isinstance(current, list):
                current.append(value)
            else:
                params[key] = [current, value]
        else:
            params[key] = value
    return params


def path_with_query(path: str, params: dict[str, Any] | None = None) -> str:
    clean = compact_params(**(params or {}))
    if not clean:
        return path
    return f"{path}?{urlencode(clean, doseq=True)}"


def payload_has_project_reference(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("project_id") or payload.get("project_uid") or payload.get("projectId") or payload.get("projectUid"))


SENSITIVE_INVENTORY_KEY_RE = re.compile(
    r"(password|senha|secret|token|credential|connection[_-]?string|conn[_-]?str|api[_-]?key|access[_-]?key|private[_-]?key)",
    flags=re.I,
)
INVENTORY_COLLECTION_KEYS = (
    "projects",
    "connections",
    "datasets",
    "files",
    "items",
    "children",
    "objects",
    "records",
    "rows",
    "data",
    "result",
    "results",
)
INVENTORY_SCALAR_KEYS = (
    "id",
    "uid",
    "project_id",
    "project_uid",
    "projectId",
    "projectUid",
    "name",
    "nome",
    "title",
    "titulo",
    "type",
    "tipo",
    "kind",
    "status",
    "state",
    "engine",
    "provider",
    "created_by",
    "owner",
    "tab_count",
    "database",
    "schema",
    "table",
    "path",
    "file",
    "filename",
    "route",
    "created_at",
    "updated_at",
    "createdAt",
    "updatedAt",
)


def scrub_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_INVENTORY_KEY_RE.search(key_text):
                clean[key_text] = "***redacted***"
            else:
                clean[key_text] = scrub_sensitive(item)
        return clean
    if isinstance(value, list):
        return [scrub_sensitive(item) for item in value]
    return value


def extract_inventory_items(payload: Any, keys: tuple[str, ...] = INVENTORY_COLLECTION_KEYS) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_inventory_items(value, keys)
            if nested:
                return nested
    return []


def compact_inventory_item(item: Any) -> dict[str, Any]:
    item = scrub_sensitive(item)
    if not isinstance(item, dict):
        return {"value": item}
    compact: dict[str, Any] = {}
    for key in INVENTORY_SCALAR_KEYS:
        if key in item and isinstance(item.get(key), (str, int, float, bool, type(None))):
            compact[key] = item.get(key)
    compact["raw_keys"] = sorted(str(key) for key in item.keys())[:30]
    return compact


def inventory_endpoint_result(
    payload: Any,
    *,
    limit: int,
    include_raw: bool,
    collection_keys: tuple[str, ...] = INVENTORY_COLLECTION_KEYS,
) -> dict[str, Any]:
    clean = scrub_sensitive(payload)
    items = extract_inventory_items(clean, collection_keys)
    result: dict[str, Any] = {
        "ok": True,
        "summary": payload_summary(clean),
    }
    if items:
        result["count"] = len(items)
        result["items"] = [compact_inventory_item(item) for item in items[: max(0, limit)]]
        if len(items) > limit:
            result["truncated"] = True
            result["limit"] = limit
    if include_raw:
        result["raw"] = clean
    return result


def inventory_error_result(error: Exception | str) -> dict[str, Any]:
    return {"ok": False, "error": str(error)}


def optional_inventory_get(
    client: RejoinBIClient,
    path: str,
    *,
    label: str,
    timeout: int,
    issues: list[dict[str, Any]],
    query: dict[str, Any] | None = None,
) -> Any:
    try:
        data, _ = client.request("GET", path_with_query(path, query), timeout=timeout)
        return data
    except RejoinBIError as exc:
        issues.append({"area": label, "path": path, "error": str(exc)})
        return None


def first_present_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def project_inventory_ref(project: dict[str, Any]) -> dict[str, str]:
    project_id_value = first_present_value(project, ("id", "project_id", "projectId"))
    project_uid_value = first_present_value(project, ("uid", "project_uid", "projectUid"))
    name_value = first_present_value(project, ("name", "nome", "title", "titulo"))
    ref: dict[str, str] = {}
    if project_id_value not in (None, ""):
        ref["project_id"] = safe_str(project_id_value)
    if project_uid_value not in (None, ""):
        ref["project_uid"] = safe_str(project_uid_value)
    if name_value not in (None, ""):
        ref["name"] = safe_str(name_value)
    return ref


def project_query_from_ref(ref: dict[str, str]) -> dict[str, str]:
    if ref.get("project_id"):
        return {"project_id": ref["project_id"]}
    if ref.get("project_uid"):
        return {"project_uid": ref["project_uid"]}
    return {}


def resolve_bi_project_id_from_uid(client: RejoinBIClient, project_uid: str) -> str:
    uid = safe_str(project_uid)
    if not uid:
        return ""
    data, _ = client.request("GET", "/plataforma/api/bi/projects", timeout=60)
    for project in extract_inventory_items(data, ("projects", "items", "data", "result", "results")):
        if not isinstance(project, dict):
            continue
        candidate_uid = safe_str(first_present_value(project, ("uid", "project_uid", "projectUid")))
        if candidate_uid != uid:
            continue
        project_id = safe_str(first_present_value(project, ("id", "project_id", "projectId")))
        if project_id:
            return project_id
    return ""


def payload_summary(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"type": "list", "count": len(payload)}
    if isinstance(payload, dict):
        summary: dict[str, Any] = {"type": "object", "keys": sorted(str(key) for key in payload.keys())[:12]}
        for key in ("count", "total", "success", "status", "message"):
            if key in payload and isinstance(payload.get(key), (str, int, float, bool, type(None))):
                summary[key] = payload.get(key)
        for key in ("users", "containers", "pages", "data", "items", "groups", "announcements", "sessions"):
            value = payload.get(key)
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
        return summary
    return {"type": type(payload).__name__}


def classify_smoke_error(error: str) -> str:
    if "HTTP 401" in error:
        return "session_expired"
    if "HTTP 403" in error and "local_only" in error:
        return "blocked_local_only"
    if "HTTP 403" in error:
        return "forbidden"
    if "HTTP 404" in error:
        return "not_available"
    if "HTTP 400" in error and re.search(r"project[_ ]?(id|uid)|Project ID", error, flags=re.I):
        return "requires_project"
    if "HTTP 500" in error:
        return "tenant_error"
    return "failed"


def require_yes(args: argparse.Namespace, message: str) -> None:
    if not getattr(args, "yes", False):
        raise RejoinBIError(message)


def required_arg(args: argparse.Namespace, attr: str, label: str | None = None) -> str:
    value = getattr(args, attr, None)
    if value in (None, ""):
        raise RejoinBIError(f"{label or '--' + attr.replace('_', '-')} is required for this action.")
    return str(value)


def required_int(args: argparse.Namespace, attr: str, label: str | None = None) -> int:
    raw = required_arg(args, attr, label)
    try:
        return int(raw)
    except ValueError as exc:
        raise RejoinBIError(f"{label or '--' + attr.replace('_', '-')} must be an integer.") from exc


def print_download_result(output: Path, payload_name: str, args: argparse.Namespace) -> int:
    print_payload({"success": True, payload_name: str(output), "bytes": output.stat().st_size}, as_json=args.json)
    return 0


def cmd_sectors(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/setores", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_permission_pages(args: argparse.Namespace) -> int:
    client = make_client(args)
    path = "/plataforma/api/permissive-pages" if args.permissive else "/plataforma/api/pages"
    data, _ = client.request("GET", path, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_user_presence(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/users-presence", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_download_users(args: argparse.Namespace) -> int:
    client = make_client(args)
    path = path_with_query("/plataforma/api/download-users", {
        "perfil": args.profile,
        "setor": args.setor,
        "search": args.search,
    })
    output = Path(args.output).expanduser().resolve()
    client.download(path, output, timeout=args.timeout)
    return print_download_result(output, "users_export", args)


def cmd_download_permissions(args: argparse.Namespace) -> int:
    client = make_client(args)
    output = Path(args.output).expanduser().resolve()
    client.download("/plataforma/api/download-permissions", output, timeout=args.timeout)
    return print_download_result(output, "permissions_export", args)


def cmd_menu(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/menu", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_menu_maintenance(args: argparse.Namespace) -> int:
    client = make_client(args)
    action_map = {
        "check-duplicates": ("GET", "/plataforma/api/check-menu-duplicates", False),
        "reload": ("POST", "/plataforma/api/reload-menu", False),
        "clear-cache": ("POST", "/plataforma/api/clear-menu-cache", False),
    }
    method, path, destructive = action_map[args.action]
    if destructive:
        require_yes(args, f"{args.action} requires --yes.")
    data, _ = client.request(method, path, json={} if method != "GET" else None, timeout=120)
    print_payload(data, as_json=args.json)
    return 0


def cmd_page_maintenance(args: argparse.Namespace) -> int:
    client = make_client(args)
    action_map = {
        "verify-orphan-permissions": ("GET", "/plataforma/api/paginas/verificar-permissoes-orfas", False),
        "clear-orphan-permissions": ("POST", "/plataforma/api/paginas/limpar-permissoes-orfas", True),
        "verify-conflicts": ("GET", "/plataforma/api/paginas/verificar-conflitos", False),
        "fix-conflicts": ("POST", "/plataforma/api/paginas/corrigir-conflito-paginas", True),
        "verify-hierarchy": ("GET", "/plataforma/api/paginas/verificar-hierarquia", False),
        "fix-hierarchy": ("POST", "/plataforma/api/paginas/corrigir-hierarquia", True),
        "clear-fictitious-orphans": ("POST", "/plataforma/api/paginas/limpar-ficticias-orfas", True),
        "clear-rls-cache": ("POST", "/plataforma/api/paginas/limpar-cache-rls", True),
    }
    method, path, destructive = action_map[args.action]
    if destructive:
        require_yes(args, f"{args.action} changes page configuration and requires --yes.")
    data, _ = client.request(method, path, json=parse_json_payload(args) if method != "GET" else None, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_page_files(args: argparse.Namespace) -> int:
    client = make_client(args)
    if not args.workspace and not args.container_id:
        raise RejoinBIError("Provide --workspace or --container-id to list page files.")
    workspace_id = resolve_workspace(client, args.workspace).get("id") if args.workspace else args.container_id
    path = path_with_query("/plataforma/api/paginas/arquivos", {"container_id": workspace_id})
    data, _ = client.request("GET", path, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_set_page_order(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = parse_json_payload(args)
    if not isinstance(payload, dict):
        raise RejoinBIError("Page order payload must be a JSON object.")
    if args.position is not None:
        payload["ordem"] = args.position
    if args.parent is not None:
        payload["pai"] = args.parent
    if args.before is not None:
        payload["before"] = args.before
    if args.after is not None:
        payload["after"] = args.after
    if not payload:
        raise RejoinBIError("Provide --data-file, --data-json, --position, --parent, --before, or --after.")
    data, _ = client.request("PUT", f"/plataforma/api/paginas/{quote(args.page_id)}/ordem", json=payload, timeout=120)
    print_payload(data, as_json=args.json)
    return 0


def cmd_rls(args: argparse.Namespace) -> int:
    client = make_client(args)
    path_map = {
        "pages": lambda: ("GET", "/plataforma/api/rls-pages", False, {}),
        "page-config": lambda: ("GET", "/plataforma/api/rls-page-config", False, compact_params(pagina=required_arg(args, "page_id", "--page-id"), container_id=args.container_id)),
        "page-info": lambda: ("GET", "/plataforma/api/rls/page-info", False, {"pagina_id": required_arg(args, "page_id", "--page-id")}),
        "config": lambda: ("GET", "/plataforma/api/rls-config", False, compact_params(pagina_id=args.page_id, container_id=args.container_id, user_id=args.user_id)),
        "data": lambda: ("GET", "/plataforma/api/rls-data", False, compact_params(container_id=args.container_id, user_id=args.user_id)),
        "dimensions": lambda: ("GET", f"/plataforma/api/rls-dimensions/{required_int(args, 'rls_id', '--rls-id')}", False, {}),
        "values": lambda: ("GET", "/plataforma/api/rls/values", False, compact_params(rls_id=required_arg(args, "rls_id", "--rls-id"), column=args.column)),
        "validate": lambda: ("POST", "/plataforma/api/rls/validate", False, {}),
        "set-config": lambda: ("POST", "/plataforma/api/rls-config", True, {}),
        "set-page-mapping": lambda: ("POST", "/plataforma/api/rls-page", True, {}),
        "delete-config": lambda: ("DELETE", "/plataforma/api/rls-config", True, {}),
        "create-data": lambda: ("POST", "/plataforma/api/rls-data", True, {}),
        "update-data": lambda: ("PUT", f"/plataforma/api/rls-data/{required_int(args, 'rls_id', '--rls-id')}", True, {}),
        "delete-data": lambda: ("DELETE", f"/plataforma/api/rls-data/{required_int(args, 'rls_id', '--rls-id')}", True, {}),
        "create-dimension": lambda: ("POST", "/plataforma/api/rls-dimensao", True, {}),
        "update-dimension": lambda: ("PUT", f"/plataforma/api/rls-dimension/{required_int(args, 'dimension_id', '--dimension-id')}", True, {}),
        "delete-dimension": lambda: ("DELETE", f"/plataforma/api/rls-dimension/{required_int(args, 'dimension_id', '--dimension-id')}", True, {}),
        "scan-columns": lambda: ("POST", "/plataforma/api/rls/scan-columns", False, {}),
        "fetch-columns": lambda: ("POST", "/plataforma/api/rls/fetch-columns", False, {}),
        "test-config": lambda: ("GET", "/plataforma/api/rls/test-config", False, compact_params(pagina_id=args.page_id, container_id=args.container_id)),
    }
    method, path, destructive, params = path_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes RLS configuration and requires --yes.")
    payload = None
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        payload = parse_json_payload(args)
        if not isinstance(payload, dict):
            raise RejoinBIError("RLS payload must be a JSON object.")
        if args.page_id and not any(key in payload for key in ("pagina_id", "pagina", "page_id")):
            payload["pagina_id"] = args.page_id
        if args.container_id and "container_id" not in payload:
            payload["container_id"] = int(args.container_id) if str(args.container_id).isdigit() else args.container_id
        if args.page_rls_id and args.action == "set-page-mapping" and "pagina_rls_id" not in payload:
            payload["pagina_rls_id"] = args.page_rls_id
    data, _ = client.request(method, path_with_query(path, params), json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_rls_export(args: argparse.Namespace) -> int:
    client = make_client(args)
    params = compact_params(format=args.format, pagina=args.page_id, user_id=args.user_id)
    output = Path(args.output).expanduser().resolve()
    client.download(path_with_query("/plataforma/api/rls-export", params), output, timeout=args.timeout)
    return print_download_result(output, "rls_export", args)


def cmd_audit(args: argparse.Namespace) -> int:
    client = make_client(args)
    if args.action == "logs":
        params = compact_params(
            page=args.page,
            per_page=args.per_page,
            date_from=args.date_from,
            date_to=args.date_to,
            action_type=args.action_type,
            user_email=args.user_email,
            level=args.level,
        )
        path = path_with_query("/plataforma/api/audit/logs", params)
        data, _ = client.request("GET", path, timeout=args.timeout)
    elif args.action == "dashboard":
        data, _ = client.request("GET", "/plataforma/api/audit/dashboard", timeout=args.timeout)
    elif args.action == "health":
        data, _ = client.request("GET", "/plataforma/api/audit/health", timeout=args.timeout)
    elif args.action == "log":
        log_id = required_int(args, "log_id", "--log-id")
        data, _ = client.request("GET", f"/plataforma/api/audit/logs/{log_id}", timeout=args.timeout)
    elif args.action == "cleanup":
        require_yes(args, "Audit cleanup requires --yes.")
        data, _ = client.request("POST", "/plataforma/api/audit-cleanup", json={"days_to_keep": args.days_to_keep}, timeout=args.timeout)
    else:
        raise RejoinBIError(f"Unsupported audit action: {args.action}")
    print_payload(data, as_json=args.json)
    return 0


def cmd_audit_export(args: argparse.Namespace) -> int:
    client = make_client(args)
    params = compact_params(
        format=args.format,
        date_from=args.date_from,
        date_to=args.date_to,
        action_type=args.action_type,
        user_email=args.user_email,
        level=args.level,
    )
    output = Path(args.output).expanduser().resolve()
    client.download(path_with_query("/plataforma/api/audit/export", params), output, timeout=args.timeout)
    return print_download_result(output, "audit_export", args)


def cmd_sleep_manager(args: argparse.Namespace) -> int:
    client = make_client(args)
    action_map = {
        "status": lambda: ("GET", "/plataforma/api/sleep-manager/status", False),
        "config": lambda: ("GET", "/plataforma/api/sleep-manager/config", False),
        "configs": lambda: ("GET", "/plataforma/api/sleep-manager/configs", False),
        "metrics": lambda: ("GET", "/plataforma/api/sleep-manager/metrics", False),
        "history": lambda: ("GET", "/plataforma/api/sleep-manager/history", False),
        "users-online": lambda: ("GET", "/plataforma/api/sleep-manager/users-online", False),
        "shutdown-warning": lambda: ("GET", "/plataforma/api/sleep-manager/shutdown-warning", False),
        "create-config": lambda: ("POST", "/plataforma/api/sleep-manager/configs", True),
        "set-config": lambda: ("POST", "/plataforma/api/sleep-manager/config", True),
        "update-config": lambda: ("PUT", f"/plataforma/api/sleep-manager/config/{required_int(args, 'config_id', '--config-id')}", True),
        "activate": lambda: ("POST", f"/plataforma/api/sleep-manager/config/{required_int(args, 'config_id', '--config-id')}/activate", True),
        "toggle": lambda: ("POST", f"/plataforma/api/sleep-manager/configs/{required_int(args, 'config_id', '--config-id')}/toggle", True),
        "delete-config": lambda: ("DELETE", f"/plataforma/api/sleep-manager/config/{required_int(args, 'config_id', '--config-id')}", True),
        "force-sleep": lambda: ("POST", "/plataforma/api/sleep-manager/force-sleep", True),
        "force-active": lambda: ("POST", "/plataforma/api/sleep-manager/force-active", True),
        "force-logout-all": lambda: ("POST", "/plataforma/api/sleep-manager/force-logout-all", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes system sleep state/configuration and requires --yes.")
    payload = parse_json_payload(args) if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path, json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_email_manager(args: argparse.Namespace) -> int:
    client = make_client(args)
    params = compact_params(group_id=args.group_id, page_id=args.page_id, limit=args.limit)
    action_map = {
        "history": lambda: ("GET", path_with_query("/plataforma/api/email/history", params), False),
        "queue-status": lambda: ("GET", "/plataforma/api/email/queue/status", False),
        "sessions": lambda: ("GET", "/plataforma/api/email/sessions", False),
        "create-session": lambda: ("POST", "/plataforma/api/email/sessions", True),
        "test-session": lambda: ("POST", "/plataforma/api/email/test-connection", False),
        "update-session": lambda: ("PUT", f"/plataforma/api/email/sessions/{required_int(args, 'session_id', '--session-id')}", True),
        "delete-session": lambda: ("DELETE", f"/plataforma/api/email/sessions/{required_int(args, 'session_id', '--session-id')}", True),
        "groups": lambda: ("GET", path_with_query("/plataforma/api/email/groups", compact_params(page_id=args.page_id)), False),
        "create-group": lambda: ("POST", "/plataforma/api/email/groups/create", True),
        "update-group": lambda: ("PUT", f"/plataforma/api/email/groups/{required_int(args, 'group_id', '--group-id')}", True),
        "delete-group": lambda: ("DELETE", f"/plataforma/api/email/groups/{required_int(args, 'group_id', '--group-id')}", True),
        "recipients": lambda: ("GET", path_with_query("/plataforma/api/email/recipients", compact_params(group_id=args.group_id)), False),
        "add-recipient": lambda: ("POST", "/plataforma/api/email/recipients", True),
        "delete-recipient": lambda: ("DELETE", f"/plataforma/api/email/recipients/{required_int(args, 'recipient_id', '--recipient-id')}", True),
        "external-contacts": lambda: ("GET", "/plataforma/api/email/external_contacts", False),
        "create-external-contact": lambda: ("POST", "/plataforma/api/email/external_contacts", True),
        "delete-external-contact": lambda: ("DELETE", f"/plataforma/api/email/external_contacts/{required_int(args, 'contact_id', '--contact-id')}", True),
        "schedules": lambda: ("GET", f"/plataforma/api/email/groups/{required_int(args, 'group_id', '--group-id')}/schedules", False),
        "create-schedule": lambda: ("POST", f"/plataforma/api/email/groups/{required_int(args, 'group_id', '--group-id')}/schedules", True),
        "delete-schedule": lambda: ("DELETE", f"/plataforma/api/email/schedules/{required_int(args, 'schedule_id', '--schedule-id')}", True),
        "broadcast": lambda: ("POST", "/plataforma/api/email/broadcast", True),
        "cancel-history": lambda: ("POST", f"/plataforma/api/email/history/{required_int(args, 'history_id', '--history-id')}/cancel", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes e-mail configuration or sends/cancels messages and requires --yes.")
    payload = parse_json_payload(args) if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path, json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_whatsapp_manager(args: argparse.Namespace) -> int:
    client = make_client(args)
    action_map = {
        "history": lambda: ("GET", path_with_query("/plataforma/api/whatsapp/history", compact_params(limit=args.limit)), False),
        "queue-status": lambda: ("GET", "/plataforma/api/whatsapp/queue/status", False),
        "diagnostics": lambda: ("GET", "/plataforma/api/whatsapp/admin/diagnostics", False),
        "sessions": lambda: ("GET", "/plataforma/api/whatsapp/sessions", False),
        "start-session": lambda: ("POST", "/plataforma/api/whatsapp/session/start", True),
        "stop-session": lambda: ("POST", "/plataforma/api/whatsapp/session/stop", True),
        "session-groups": lambda: ("GET", f"/plataforma/api/whatsapp/session/groups/{quote(required_arg(args, 'session_name', '--session-name'))}", False),
        "groups": lambda: ("GET", "/plataforma/api/whatsapp/groups", False),
        "create-group": lambda: ("POST", "/plataforma/api/whatsapp/groups/create", True),
        "update-group": lambda: ("PUT", f"/plataforma/api/whatsapp/groups/{required_int(args, 'group_id', '--group-id')}", True),
        "delete-group": lambda: ("DELETE", f"/plataforma/api/whatsapp/groups/{required_int(args, 'group_id', '--group-id')}", True),
        "recipients": lambda: ("GET", path_with_query("/plataforma/api/whatsapp/recipients", compact_params(group_id=args.group_id)), False),
        "add-recipient": lambda: ("POST", "/plataforma/api/whatsapp/recipients", True),
        "delete-recipient": lambda: ("DELETE", f"/plataforma/api/whatsapp/recipients/{required_int(args, 'recipient_id', '--recipient-id')}", True),
        "external-contacts": lambda: ("GET", "/plataforma/api/whatsapp/external_contacts", False),
        "create-external-contact": lambda: ("POST", "/plataforma/api/whatsapp/external_contacts", True),
        "delete-external-contact": lambda: ("DELETE", f"/plataforma/api/whatsapp/external_contacts/{required_int(args, 'contact_id', '--contact-id')}", True),
        "schedules": lambda: ("GET", f"/plataforma/api/whatsapp/groups/{required_int(args, 'group_id', '--group-id')}/schedules", False),
        "create-schedule": lambda: ("POST", f"/plataforma/api/whatsapp/groups/{required_int(args, 'group_id', '--group-id')}/schedules", True),
        "delete-schedule": lambda: ("DELETE", f"/plataforma/api/whatsapp/schedules/{required_int(args, 'schedule_id', '--schedule-id')}", True),
        "broadcast": lambda: ("POST", "/plataforma/api/whatsapp/broadcast", True),
        "cancel-history": lambda: ("POST", f"/plataforma/api/whatsapp/history/{required_int(args, 'history_id', '--history-id')}/cancel", True),
        "restart-service": lambda: ("POST", "/plataforma/api/whatsapp/admin/restart_service", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes WhatsApp configuration or sends/cancels messages and requires --yes.")
    payload = parse_json_payload(args) if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path, json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_codex_keys(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = parse_json_payload(args)
    if not isinstance(payload, dict):
        raise RejoinBIError("Codex keys payload must be a JSON object.")
    if args.provider_id is not None:
        payload.setdefault("provider_id", args.provider_id)
    params = compact_params(
        provider_id=args.provider_id,
        page=args.page,
        limit=args.limit,
        user_email=args.user_email,
        days=args.days,
    )
    action_map = {
        "stats": lambda: ("GET", "/plataforma/api/codex/keys/stats", False, {}),
        "active": lambda: ("GET", "/plataforma/api/codex/keys/active", False, {}),
        "list": lambda: ("GET", "/plataforma/api/codex/keys", False, {}),
        "auth-status": lambda: ("GET", "/plataforma/api/codex/auth-status", False, compact_params(provider_id=args.provider_id)),
        "auth-login": lambda: ("POST", "/plataforma/api/codex/auth-login", True, {}),
        "create": lambda: ("POST", "/plataforma/api/codex/keys", True, {}),
        "get": lambda: ("GET", f"/plataforma/api/codex/keys/{required_int(args, 'key_id', '--key-id')}", False, {}),
        "unlock": lambda: ("POST", f"/plataforma/api/codex/keys/{required_int(args, 'key_id', '--key-id')}/unlock", False, {}),
        "update": lambda: ("PUT", f"/plataforma/api/codex/keys/{required_int(args, 'key_id', '--key-id')}", True, {}),
        "delete": lambda: ("DELETE", f"/plataforma/api/codex/keys/{required_int(args, 'key_id', '--key-id')}", True, {}),
        "user-delete": lambda: ("DELETE", f"/plataforma/api/codex/keys/user-delete/{required_int(args, 'key_id', '--key-id')}", True, {}),
        "usage": lambda: ("GET", "/plataforma/api/codex/keys/usage", False, params),
        "users": lambda: ("GET", "/plataforma/api/codex/keys/users", False, {}),
    }
    method, path, destructive, query_params = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes Codex/AI provider configuration and requires --yes.")
    request_payload = payload if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path_with_query(path, query_params), json=request_payload, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_route_map(args: argparse.Namespace) -> int:
    client = make_client(args)
    action_map = {
        "routes": lambda: ("GET", "/plataforma/api/route-mapping/routes", False),
        "route": lambda: ("GET", f"/plataforma/api/route-mapping/routes/{quote(required_arg(args, 'route_name', '--route-name'))}", False),
        "uploads": lambda: ("GET", "/plataforma/api/route-mapping/uploads", False),
        "scan": lambda: ("POST", "/plataforma/api/route-mapping/scan", False),
        "clear": lambda: ("POST", "/plataforma/api/route-mapping/clear", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes route mapping state and requires --yes.")
    data, _ = client.request(method, path, json={} if method != "GET" else None, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_system_admin(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = parse_json_payload(args)
    if not isinstance(payload, dict):
        raise RejoinBIError("System admin payload must be a JSON object.")
    query_params = parse_query_params(args)
    action_map = {
        "auto-stress-start": ("GET", "/plataforma/api/auto-stress/start", True),
        "auto-stress-results": ("GET", "/plataforma/api/auto-stress/results", False),
        "database-status": ("GET", "/plataforma/api/database/status", False),
        "subscription-status": ("GET", "/plataforma/api/subscription/status", False),
        "clear-dynamic-cache": ("GET", "/plataforma/api/clear-dynamic-cache", True),
        "dynamic-apps-monitoring": ("GET", "/plataforma/api/dynamic-apps-monitoring", False),
        "check-work-status": ("GET", "/plataforma/api/check-work-status", False),
        "dynamic-pages": ("GET", "/plataforma/api/dynamic-pages", False),
        "init-status": ("GET", "/plataforma/api/status-inicializacao", False),
        "restart-dynamics": ("POST", "/plataforma/api/reinicializar-dinamicas", True),
        "dynamic-status": ("GET", "/plataforma/api/status-dinamicas", False),
        "public-ready": ("GET", "/plataforma/api/public-ready", False),
        "runtime-readiness": ("GET", "/plataforma/api/runtime-readiness", False),
        "runtime-build-info": ("GET", "/plataforma/api/runtime-build-info", False),
        "file-recognition": ("POST", "/plataforma/api/file-recognition", False),
        "test-url-rewriting": ("POST", "/plataforma/api/test-url-rewriting", False),
        "active-container": ("GET", "/plataforma/api/active-container", False),
        "force-reload": ("POST", "/plataforma/api/force-reload", True),
        "clear-all-caches": ("POST", "/plataforma/api/clear-all-caches", True),
        "middleware-status": ("GET", "/plataforma/api/middleware/status", False),
        "middleware-cleanup": ("GET", "/plataforma/api/middleware/cleanup", True),
    }
    method, path, destructive = action_map[args.action]
    if destructive:
        require_yes(args, f"{args.action} changes platform runtime/system state and requires --yes.")
    request_payload = payload if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path_with_query(path, query_params), json=request_payload, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_upload_admin(args: argparse.Namespace) -> int:
    client = make_client(args)
    if args.action == "gateway-download-client":
        output = Path(args.output or "rejoinbi-gateway-client.zip").expanduser().resolve()
        client.download("/plataforma/api/gateway/download-client", output, timeout=args.timeout)
        return print_download_result(output, "gateway_client", args)

    payload = parse_json_payload(args)
    if not isinstance(payload, dict):
        raise RejoinBIError("Upload admin payload must be a JSON object.")
    query_params = parse_query_params(args)
    action_map = {
        "python-versions": lambda: ("GET", "/plataforma/api/python-versions", False),
        "capabilities": lambda: ("GET", "/plataforma/api/upload-capabilities", False),
        "gateway-pairings": lambda: ("GET", "/plataforma/api/gateway/pairings", False),
        "gateway-generate-pairing-code": lambda: ("POST", "/plataforma/api/gateway/generate-pairing-code", True),
        "gateway-delete-pairing": lambda: ("DELETE", f"/plataforma/api/gateway/pairings/{required_int(args, 'pairing_id', '--pairing-id')}", True),
        "gateway-pause-pairing": lambda: ("POST", f"/plataforma/api/gateway/pairings/{required_int(args, 'pairing_id', '--pairing-id')}/pause", True),
        "gateway-confirm-access": lambda: ("POST", f"/plataforma/api/gateway/pairings/{required_int(args, 'pairing_id', '--pairing-id')}/confirm-access", True),
        "gateway-confirm-link": lambda: ("POST", "/plataforma/api/gateway/confirm-link", True),
        "gateway-bootstrap": lambda: ("POST", "/plataforma/api/gateway/bootstrap", True),
        "gateway-delete-item": lambda: ("POST", "/plataforma/api/gateway/delete-item", True),
        "upload-status": lambda: ("GET", f"/plataforma/api/upload-status/{quote(required_arg(args, 'process_id', '--process-id'))}", False),
        "clear-dynamic-data": lambda: ("POST", "/plataforma/api/clear-dynamic-data", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes upload/gateway state and requires --yes.")
    request_payload = payload if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path_with_query(path, query_params), json=request_payload, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_data_engine(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = parse_json_payload(args)
    if not isinstance(payload, dict):
        raise RejoinBIError("Data Engine payload must be a JSON object.")
    query_params = parse_query_params(args)
    if getattr(args, "project_id", None):
        query_params["project_id"] = args.project_id
    if getattr(args, "project_uid", None):
        query_params["project_uid"] = args.project_uid
    if query_params.get("project_uid") and not query_params.get("project_id"):
        resolved_project_id = resolve_bi_project_id_from_uid(client, safe_str(query_params["project_uid"]))
        if resolved_project_id:
            query_params["project_id"] = resolved_project_id
    if payload.get("project_uid") and not payload.get("project_id"):
        resolved_project_id = resolve_bi_project_id_from_uid(client, safe_str(payload["project_uid"]))
        if resolved_project_id:
            payload["project_id"] = resolved_project_id
    if payload:
        require_clean_json_text(payload, context=f"data-engine {args.action} payload")
    if args.action == "inventory":
        result = build_studio_inventory(client, args)
        if getattr(args, "output", None):
            output = Path(args.output).expanduser().resolve()
            write_json(output, result)
            result = {**result, "output": str(output)}
        print_payload(result, as_json=args.json)
        return 0
    if args.action in DATA_ENGINE_PROJECT_ACTIONS and not (
        query_params.get("project_id")
        or query_params.get("project_uid")
        or payload_has_project_reference(payload)
    ):
        raise RejoinBIError(
            f"data-engine {args.action} requires --project-id, --project-uid, "
            "or a JSON payload containing project_id/project_uid."
        )
    base = "/plataforma/data-engine"
    if args.action == "repository-inspect-sheets":
        file_path = Path(required_arg(args, "file", "--file")).expanduser().resolve()
        if not file_path.is_file():
            raise RejoinBIError(f"File not found: {file_path}")
        reason = sensitive_path_reason(file_path)
        if reason and not getattr(args, "allow_sensitive_files", False):
            raise RejoinBIError(
                f"Refusing to inspect sensitive-looking file {file_path}: {reason}. "
                "Use --allow-sensitive-files only after manual review."
            )
        with ExitStack() as stack:
            mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            files = {"file": (file_path.name, stack.enter_context(file_path.open("rb")), mime)}
            data, _ = client.request("POST", f"{base}/api/repository/inspect-sheets", files=files, timeout=args.timeout)
        print_payload(scrub_sensitive(data), as_json=args.json)
        return 0
    if args.action == "repository-upload":
        project_id = safe_str(query_params.get("project_id") or payload.get("project_id") or getattr(args, "project_id", ""))
        if not project_id and query_params.get("project_uid"):
            project_id = safe_str(resolve_bi_project_id_from_uid(client, safe_str(query_params["project_uid"])) or "")
        if not project_id:
            raise RejoinBIError("data-engine repository-upload requires --project-id or --project-uid.")
        file_path = Path(required_arg(args, "file", "--file")).expanduser().resolve()
        if not file_path.is_file():
            raise RejoinBIError(f"File not found: {file_path}")
        reason = sensitive_path_reason(file_path)
        if reason and not getattr(args, "allow_sensitive_files", False):
            raise RejoinBIError(
                f"Refusing to upload sensitive-looking file {file_path}: {reason}. "
                "Use --allow-sensitive-files only after manual review."
            )
        form_data: dict[str, str] = {"project_id": project_id}
        if getattr(args, "folder", None):
            form_data["folder"] = str(args.folder)
        if getattr(args, "selected_sheet", None):
            require_clean_json_text(args.selected_sheet, context="data-engine repository-upload selected sheets")
            form_data["selected_sheets"] = json.dumps(args.selected_sheet, ensure_ascii=False)
        if getattr(args, "sheet_states", None):
            sheet_states_text = Path(args.sheet_states).expanduser().read_text(encoding="utf-8")
            try:
                require_clean_json_text(json.loads(sheet_states_text), context="data-engine repository-upload sheet states")
            except json.JSONDecodeError:
                require_clean_json_text(sheet_states_text, context="data-engine repository-upload sheet states")
            form_data["sheet_states"] = sheet_states_text
        if getattr(args, "csv_separator", None):
            form_data["csv_separator"] = str(args.csv_separator)
        with ExitStack() as stack:
            mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            files = {"file": (file_path.name, stack.enter_context(file_path.open("rb")), mime)}
            data, _ = client.request("POST", f"{base}/api/repository/upload", data=form_data, files=files, timeout=args.timeout)
        print_payload(scrub_sensitive(data), as_json=args.json)
        return 0
    action_map = {
        "status": lambda: ("GET", f"{base}/api/status", False),
        "session-status": lambda: ("GET", f"{base}/api/session/status", False),
        "db-connections": lambda: ("GET", f"{base}/api/db/connections", False),
        "create-db-connection": lambda: ("POST", f"{base}/api/db/connections", True),
        "db-connection": lambda: ("GET", f"{base}/api/db/connections/{required_int(args, 'connection_id', '--connection-id')}", False),
        "update-db-connection": lambda: ("PUT", f"{base}/api/db/connections/{required_int(args, 'connection_id', '--connection-id')}", True),
        "delete-db-connection": lambda: ("DELETE", f"{base}/api/db/connections/{required_int(args, 'connection_id', '--connection-id')}", True),
        "test-db-connection": lambda: ("POST", f"{base}/api/db/connections/test", False),
        "sqlserver-drivers": lambda: ("GET", f"{base}/api/db/providers/sqlserver/drivers", False),
        "db-objects": lambda: ("GET", f"{base}/api/db/connections/{required_int(args, 'connection_id', '--connection-id')}/objects", False),
        "query": lambda: ("GET", f"{base}/api/db/queries/{required_int(args, 'query_id', '--query-id')}", False),
        "query-preview": lambda: ("POST", f"{base}/api/db/query/preview", False),
        "query-materialize": lambda: ("POST", f"{base}/api/db/query/materialize", True),
        "query-materialize-saved": lambda: ("POST", f"{base}/api/db/queries/{required_int(args, 'query_id', '--query-id')}/materialize", True),
        "query-run": lambda: ("GET", f"{base}/api/db/query-runs/{required_int(args, 'run_id', '--run-id')}", False),
        "ai-sql-query": lambda: ("POST", f"{base}/api/ai/sql-query", False),
        "repository-list": lambda: ("GET", f"{base}/api/repository/list", False),
        "repository-content": lambda: ("GET", f"{base}/api/repository/content", False),
        "repository-global-context": lambda: ("GET", f"{base}/api/repository/global-context", False),
        "repository-execute-global-context": lambda: ("POST", f"{base}/api/repository/execute-global-context", False),
        "repository-manual-table": lambda: ("GET", f"{base}/api/repository/manual-table", False),
        "create-manual-table": lambda: ("POST", f"{base}/api/repository/manual-table", True),
        "create-folder": lambda: ("POST", f"{base}/api/repository/create-folder", True),
        "move": lambda: ("POST", f"{base}/api/repository/move", True),
        "order": lambda: ("POST", f"{base}/api/repository/order", True),
        "delete": lambda: ("POST", f"{base}/api/repository/delete", True),
        "datasets-list": lambda: ("GET", f"{base}/api/datasets/list", False),
        "create-dataset": lambda: ("POST", f"{base}/api/datasets/create", True),
        "duplicate-dataset": lambda: ("POST", f"{base}/api/datasets/duplicate", True),
        "delete-dataset": lambda: ("POST", f"{base}/api/datasets/delete", True),
        "link-dataset": lambda: ("POST", f"{base}/api/dataset/link", True),
        "unlink-dataset": lambda: ("POST", f"{base}/api/dataset/unlink", True),
        "list-files": lambda: ("GET", f"{base}/api/list-files", False),
        "preview-file": lambda: ("GET", f"{base}/api/preview-file", False),
        "dataset-get": lambda: ("GET", f"{base}/api/datasets/get", False),
        "save-column-types": lambda: ("POST", f"{base}/api/datasets/column-types/save", True),
        "save-notebook-state": lambda: ("POST", f"{base}/api/datasets/notebook-state/save", True),
        "finalize-dataset": lambda: ("POST", f"{base}/api/datasets/finalize", True),
        "toggle-visibility": lambda: ("POST", f"{base}/api/datasets/toggle-visibility", True),
        "execute-code": lambda: ("POST", f"{base}/api/execute_code", False),
        "agent-mine": lambda: ("POST", f"{base}/api/agent/mine", False),
        "chat": lambda: ("POST", f"{base}/api/chat", False),
        "load-chat": lambda: ("GET", f"{base}/api/load-chat", False),
        "cancel-execution": lambda: ("POST", f"{base}/api/execute/cancel", True),
        "reset-session": lambda: ("POST", f"{base}/api/session/reset", True),
        "remove-variable": lambda: ("POST", f"{base}/api/session/remove-variable", True),
        "terminal-command": lambda: ("POST", f"{base}/api/terminal/command", True),
        "terminal-auto-install": lambda: ("POST", f"{base}/api/terminal/auto-install", True),
    }
    method, path, destructive = action_map[args.action]()
    if destructive:
        require_yes(args, f"{args.action} changes Data Engine configuration/data/session state and requires --yes.")
    request_payload = payload if method in {"POST", "PUT", "PATCH", "DELETE"} else None
    data, _ = client.request(method, path_with_query(path, query_params), json=request_payload, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_workspace_logs(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    path = f"/plataforma/api/containers/{workspace.get('id')}/logs"
    if args.deploy_id:
        path = f"{path}/{quote(args.deploy_id)}"
    data, _ = client.request("GET", path, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_versions(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    data, _ = client.request("GET", f"/plataforma/api/containers/{workspace.get('id')}/versions", timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_version_action(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    workspace_id = workspace.get("id")
    sha = quote(args.sha)
    if args.action == "export":
        output = Path(args.output).expanduser().resolve()
        client.download(f"/plataforma/api/containers/{workspace_id}/versions/{sha}/export", output, timeout=args.timeout)
        return print_download_result(output, "workspace_version_export", args)
    require_yes(args, f"workspace-version-{args.action} requires --yes.")
    if args.action == "restore":
        method = "POST"
        path = f"/plataforma/api/containers/{workspace_id}/versions/{sha}/restore"
    else:
        method = "DELETE"
        path = f"/plataforma/api/containers/{workspace_id}/versions/{sha}"
    data, _ = client.request(method, path, json={}, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_schedule(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    workspace_id = workspace.get("id")
    if args.action == "get":
        data, _ = client.request("GET", f"/plataforma/api/containers/{workspace_id}/schedule", timeout=args.timeout)
    elif args.action == "set":
        require_yes(args, "Setting workspace schedule requires --yes.")
        data, _ = client.request("POST", f"/plataforma/api/containers/{workspace_id}/schedule", json=parse_json_payload(args), timeout=args.timeout)
    else:
        require_yes(args, "Deleting workspace schedule requires --yes.")
        schedule_id = required_int(args, "schedule_id", "--schedule-id")
        data, _ = client.request("DELETE", f"/plataforma/api/containers/{workspace_id}/schedule/{schedule_id}", timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_notification(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    workspace_id = workspace.get("id")
    action_map = {
        "config": ("GET", f"/plataforma/api/containers/{workspace_id}/notification-config", False),
        "set-config": ("PUT", f"/plataforma/api/containers/{workspace_id}/notification-config", True),
        "history": ("GET", f"/plataforma/api/containers/{workspace_id}/notification-history", False),
        "users": ("GET", f"/plataforma/api/containers/{workspace_id}/notification/users", False),
        "email-sessions": ("GET", f"/plataforma/api/containers/{workspace_id}/notification/email-sessions", False),
        "email-groups": ("GET", f"/plataforma/api/containers/{workspace_id}/notification/email-groups", False),
        "whatsapp-sessions": ("GET", f"/plataforma/api/containers/{workspace_id}/notification/whatsapp-sessions", False),
        "whatsapp-groups": ("GET", f"/plataforma/api/containers/{workspace_id}/notification/whatsapp-groups", False),
    }
    method, path, destructive = action_map[args.action]
    if destructive:
        require_yes(args, f"{args.action} changes workspace notification configuration and requires --yes.")
    payload = parse_json_payload(args) if method in {"POST", "PUT", "PATCH"} else None
    data, _ = client.request(method, path, json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_terminal_input(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    require_yes(args, "Sending terminal input to a workspace requires --yes.")
    data, _ = client.request(
        "POST",
        f"/plataforma/api/containers/{workspace.get('id')}/input",
        json={"input": args.input},
        timeout=args.timeout,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_build(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    require_yes(args, "Building a workspace container requires --yes.")
    data, _ = client.request("POST", f"/plataforma/api/containers/{workspace.get('id')}/docker/build", json=parse_json_payload(args), timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_stop_all(args: argparse.Namespace) -> int:
    require_yes(args, "Stopping all workspaces requires --yes.")
    client = make_client(args)
    data, _ = client.request("POST", "/plataforma/api/stop-all", json={}, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_update_workspace(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    if args.password is None and workspace_password_protected(workspace):
        raise RejoinBIError(
            "Workspace protegido por senha detectado. A API de edicao exige o campo password e poderia limpar a senha; "
            "informe --password explicitamente ou altere a senha pela tela manual."
        )
    payload = {
        "name": args.name if args.name is not None else workspace.get("name"),
        "password": args.password if args.password is not None else "",
        "is_active": True if args.active else (False if args.inactive else bool(workspace.get("is_active", True))),
    }
    data, _ = client.request("PUT", f"/plataforma/api/containers/{workspace.get('id')}", json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_pages(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace_id = None
    if args.workspace:
        workspace = resolve_workspace(client, args.workspace)
        workspace_id = workspace.get("id")
    pages = list_pages(
        client,
        workspace_id=workspace_id,
        all_containers=bool(args.all_containers),
        include_inactive=bool(args.include_inactive),
        exclude_fictitious=bool(args.exclude_fictitious),
    )
    print_payload({"success": True, "pages": pages, "data": pages, "count": len(pages)}, as_json=args.json)
    return 0


def cmd_accessible_pages(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", "/plataforma/api/accessible-pages", timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_create_workspace(args: argparse.Namespace) -> int:
    client = make_client(args)
    password = args.password or os.environ.get("REJOINBI_WORKSPACE_PASSWORD") or ""
    payload = {
        "name": args.name,
        "password": password,
        "description": args.description or "",
    }
    data, _ = client.request("POST", "/plataforma/api/containers", json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_delete_workspace(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    plan = workspace_delete_plan(client, workspace)
    workspace_name = safe_str(workspace.get("name"))
    workspace_id = safe_str(workspace.get("id"))
    password_protected = bool(plan.get("workspace", {}).get("password_protected") or plan.get("workspace", {}).get("locked"))
    if args.dry_run or not args.yes:
        print_payload({
            "success": True,
            "dry_run": True,
            "message": (
                "No deletion performed. Re-run with --yes, --confirm-name, optional --confirm-id, "
                "and --workspace-password if the workspace is protected."
            ),
            "plan": plan,
        }, as_json=args.json)
        return 0

    errors: list[str] = []
    if safe_str(args.confirm_name) != workspace_name:
        errors.append(f"--confirm-name must exactly match resolved workspace name: {workspace_name}")
    if args.confirm_id and safe_str(args.confirm_id) != workspace_id:
        errors.append(f"--confirm-id must exactly match resolved workspace id: {workspace_id}")
    if password_protected:
        if not has_secret(getattr(args, "workspace_password", None), "REJOINBI_WORKSPACE_PASSWORD"):
            errors.append(
                "Workspace protegido por senha detectado. Para remover pelo plugin, informe --workspace-password "
                "ou defina REJOINBI_WORKSPACE_PASSWORD. Sem senha validada, remova manualmente pela plataforma."
            )
        else:
            try:
                workspace_password = secret_value(args.workspace_password, "REJOINBI_WORKSPACE_PASSWORD", "workspace-password")
                validation = validate_workspace_if_password(client, workspace, workspace_password)
                validation_success = bool(validation and validation.get("success", True))
                plan["workspace_password_validation"] = {
                    "success": validation_success,
                    "validated": validation_success,
                    "message": validation.get("message") if isinstance(validation, dict) else "",
                }
                if not validation_success:
                    errors.append("Senha do workspace nao foi validada. A remocao foi bloqueada.")
                else:
                    plan["blocked"] = False
                    plan["password_validation_required"] = False
                    plan["security_message"] = "Senha do workspace validada pela plataforma; remocao liberada pelos guards do plugin."
            except RejoinBIError as exc:
                plan["workspace_password_validation"] = {"success": False, "validated": False, "error": str(exc)}
                errors.append("Senha do workspace invalida ou nao validada. A remocao foi bloqueada.")
    if normalize_text(workspace_name) in RESERVED_WORKSPACE_NAMES and not args.force_reserved:
        errors.append("Workspace name is reserved/protected. Use --force-reserved only after manual review.")
    external = plan.get("pages", {}).get("external_linked_pages") or []
    if external and not args.allow_linked_pages:
        errors.append("Deletion would also affect pages linked from another workspace. Review plan and use --allow-linked-pages if intended.")
    if errors:
        print_payload({"success": False, "errors": errors, "plan": plan}, as_json=args.json)
        return 2

    data, _ = client.request("DELETE", f"/plataforma/api/containers/{workspace_id}", timeout=args.timeout)
    deleted_payload = data if isinstance(data, dict) else {"raw": data}
    remaining_workspaces = load_workspaces(client)
    workspace_still_exists = any(same_id(item.get("id"), workspace_id) for item in remaining_workspaces)
    remaining_pages = list_pages(client, all_containers=True, include_inactive=True, exclude_fictitious=False)
    planned_page_ids = set(plan.get("pages", {}).get("cascade_ids") or [])
    remaining_planned_pages = [page_summary(page) for page in remaining_pages if page_id(page) in planned_page_ids]
    print_payload({
        "success": bool(deleted_payload.get("success", True)) and not workspace_still_exists,
        "deleted": True,
        "plan": plan,
        "response": deleted_payload,
        "verification": {
            "workspace_still_exists": workspace_still_exists,
            "remaining_planned_pages": remaining_planned_pages,
            "remaining_planned_page_count": len(remaining_planned_pages),
        },
    }, as_json=args.json)
    return 0


def cmd_set_workspace_password(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    password = args.password or os.environ.get("REJOINBI_WORKSPACE_PASSWORD") or ""
    data, _ = client.request(
        "PUT",
        f"/plataforma/api/containers/{workspace.get('id')}/password",
        json={"password": password},
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_workspace_action(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    data, _ = client.request(
        "POST" if args.action != "status" else "GET",
        f"/plataforma/api/containers/{workspace.get('id')}/{args.action}",
        timeout=args.timeout,
    )
    print_payload(data, as_json=args.json)
    return 0


def cmd_create_page(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    payload = {
        "nome": args.name,
        "container_id": workspace.get("id"),
        "arquivo": args.file or "",
        "rota": args.route or "",
        "icone": args.icon or "fas fa-chart-line",
        "descricao": args.description or "",
        "pai": args.parent or "",
        "ativo": not args.inactive,
        "rls": bool(args.rls),
    }
    if args.workspace_password:
        payload["container_password"] = args.workspace_password
    data, _ = client.request("POST", "/plataforma/api/paginas", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def delete_page(client: RejoinBIClient, page_id: str, *, missing_ok: bool = False) -> dict[str, Any]:
    try:
        data, _ = client.request("DELETE", f"/plataforma/api/paginas/{quote(str(page_id), safe='')}", timeout=60)
        return data if isinstance(data, dict) else {"raw": data}
    except RejoinBIError as exc:
        if missing_ok and "404" in str(exc):
            return {"success": True, "skipped": True, "message": f"Page not found: {page_id}"}
        raise


def cmd_delete_page(args: argparse.Namespace) -> int:
    client = make_client(args)
    plan = page_delete_plan(client, args.page_id)
    if not plan.get("found"):
        if args.missing_ok:
            print_payload({"success": True, "skipped": True, "plan": plan}, as_json=args.json)
            return 0
        print_payload({"success": False, "plan": plan}, as_json=args.json)
        return 2
    if args.dry_run or not args.yes:
        print_payload({
            "success": True,
            "dry_run": True,
            "message": "No deletion performed. Re-run with --yes and --confirm-page-id to delete.",
            "plan": plan,
        }, as_json=args.json)
        return 0

    target_id = safe_str(plan.get("target", {}).get("id"))
    errors: list[str] = []
    if safe_str(args.confirm_page_id) != target_id:
        errors.append(f"--confirm-page-id must exactly match resolved page id: {target_id}")
    if is_fictitious_page_id(target_id):
        errors.append("Fictitious pages cannot be deleted directly. Delete the original page/container instead.")
    descendants = plan.get("cascade", {}).get("descendant_ids") or []
    if descendants and not args.cascade:
        errors.append("Page has descendants. Review the tree and use --cascade if deleting the whole branch is intended.")
    additional_linked = plan.get("additional_linked_pages") or []
    if additional_linked and not args.allow_linked_pages:
        errors.append("Page has additional hierarchy/reference links. Review plan and use --allow-linked-pages if intended.")
    if errors:
        print_payload({"success": False, "errors": errors, "plan": plan}, as_json=args.json)
        return 2

    data = delete_page(client, target_id, missing_ok=args.missing_ok)
    remaining_pages = list_pages(client, all_containers=True, include_inactive=True, exclude_fictitious=False)
    planned_ids = set(plan.get("cascade", {}).get("ids") or [])
    remaining_planned_pages = [page_summary(page) for page in remaining_pages if page_id(page) in planned_ids]
    print_payload({
        "success": bool(data.get("success", True)) and not remaining_planned_pages,
        "deleted": True,
        "plan": plan,
        "response": data,
        "verification": {
            "remaining_planned_pages": remaining_planned_pages,
            "remaining_planned_page_count": len(remaining_planned_pages),
        },
    }, as_json=args.json)
    return 0


def cmd_update_page(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload: dict[str, Any] = {}
    if args.name:
        payload["nome"] = args.name
    if args.file is not None:
        payload["arquivo"] = args.file
    if args.route is not None:
        payload["rota"] = args.route
    if args.icon:
        payload["icone"] = args.icon
    if args.description is not None:
        payload["descricao"] = args.description
    if args.parent is not None:
        payload["pai"] = args.parent
    if args.workspace:
        workspace = resolve_workspace(client, args.workspace)
        payload["container_id"] = workspace.get("id")
    if args.workspace_password:
        payload["container_password"] = args.workspace_password
    if args.active:
        payload["ativo"] = True
    if args.inactive:
        payload["ativo"] = False
    if args.rls:
        payload["rls"] = True
    if args.no_rls:
        payload["rls"] = False
    if not payload:
        raise RejoinBIError("No page changes provided.")
    data, _ = client.request("PUT", f"/plataforma/api/paginas/{quote(args.page_id, safe='')}", json=payload, timeout=60)
    print_payload(data, as_json=args.json)
    return 0


def cmd_resolve_page(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request(
        "GET",
        f"/plataforma/api/capture/resolve-page/{quote(args.page_ref, safe='/')}",
        timeout=60,
    )
    print_payload(data, as_json=args.json)
    return 0


def load_manifest(path: str) -> tuple[dict[str, Any], Path]:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise RejoinBIError(f"Manifest not found: {manifest_path}")
    payload = load_json_file(str(manifest_path))
    if not isinstance(payload, dict):
        raise RejoinBIError("Manifest must contain a JSON object.")
    return payload, manifest_path


def manifest_tenant_host(manifest: dict[str, Any]) -> str:
    tenant = manifest.get("tenant")
    if isinstance(tenant, str):
        return tenant.strip()
    if isinstance(tenant, dict):
        for key in ("host", "url", "base_url", "baseUrl"):
            value = str(tenant.get(key) or "").strip()
            if value:
                return value
    return ""


def bind_manifest_tenant(args: argparse.Namespace, manifest: dict[str, Any]) -> None:
    host = manifest_tenant_host(manifest)
    if not host:
        return
    manifest_base_url = clean_base_url(host)
    explicit_base_url = ""
    if str(getattr(args, "base_url", "") or "").strip():
        explicit_base_url = clean_base_url(str(getattr(args, "base_url")))
    else:
        cli_tenant = str(getattr(args, "tenant", "") or getattr(args, "subdomain", "") or "").strip()
        if cli_tenant:
            explicit_base_url = resolve_base_url(
                subdomain=cli_tenant,
                domain=getattr(args, "domain", DEFAULT_DOMAIN) or DEFAULT_DOMAIN,
                base_url="",
            )
    if explicit_base_url and tenant_host_from_base_url(explicit_base_url) != tenant_host_from_base_url(manifest_base_url):
        raise RejoinBIError(
            "Manifest tenant does not match the command tenant: "
            f"{tenant_host_from_base_url(manifest_base_url)} != {tenant_host_from_base_url(explicit_base_url)}"
        )
    if not explicit_base_url:
        args.base_url = manifest_base_url


def manifest_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def create_workspace_if_needed(
    client: RejoinBIClient,
    name: str,
    *,
    password: str = "",
    description: str = "",
    create: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    try:
        return resolve_workspace(client, name)
    except RejoinBIError:
        if not create:
            raise
    data, _ = client.request(
        "POST",
        "/plataforma/api/containers",
        json={"name": name, "password": password, "description": description},
        timeout=timeout,
    )
    payload = data if isinstance(data, dict) else {"raw": data}
    container = payload.get("container") if isinstance(payload.get("container"), dict) else None
    if container:
        return container
    return resolve_workspace(client, name)


def validate_workspace_if_password(client: RejoinBIClient, workspace: dict[str, Any], password: str = "") -> dict[str, Any] | None:
    if not password:
        return None
    data, _ = client.request(
        "POST",
        "/plataforma/api/validate-container-password",
        json={"container_id": workspace.get("id"), "password": password},
        timeout=60,
    )
    client.save_session()
    return data if isinstance(data, dict) else {"raw": data}


def upload_folder_with_options(
    client: RejoinBIClient,
    workspace: dict[str, Any],
    root: Path,
    *,
    startup_mode: str = "static",
    selected_file: str = "",
    startup_command: str = "",
    python_path: str = "auto",
    auto_start: bool = True,
    rpa_support: bool = False,
    timeout: int = 900,
    interval: float = 3.0,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    if not root.is_dir():
        raise RejoinBIError(f"Folder not found: {root}")
    exclude_names = set(exclude or [".git", "venv", ".venv", "__pycache__", "node_modules", ".pytest_cache"])
    with ExitStack() as stack:
        data_items: list[tuple[str, str]] = [("container_id", str(workspace.get("id")))]
        files = []
        for path in iter_folder_files(root, exclude_names):
            rel = str(path.relative_to(root)).replace("\\", "/")
            mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            data_items.append(("paths", rel))
            files.append(("files", (path.name, stack.enter_context(path.open("rb")), mime)))
        if not files:
            raise RejoinBIError("No files found to upload.")
        data, _ = client.request("POST", "/plataforma/api/upload-folder", data=data_items, files=files, timeout=timeout)
    files_payload = list((data or {}).get("files") or []) if isinstance(data, dict) else []
    options = argparse.Namespace(
        startup_mode=startup_mode,
        selected_file=selected_file,
        startup_command=startup_command,
        python_path=python_path,
        auto_start=auto_start,
        rpa_support=rpa_support,
        timeout=timeout,
        interval=interval,
    )
    return select_app_file(client, workspace, files_payload, options)


def page_payload_from_manifest(page: dict[str, Any], workspace: dict[str, Any], workspace_password: str = "") -> dict[str, Any]:
    name = page.get("name") or page.get("nome")
    if not name:
        raise RejoinBIError(f"Manifest page is missing name: {page}")
    payload = {
        "nome": name,
        "container_id": page.get("container_id") or workspace.get("id"),
        "arquivo": page.get("file") or page.get("arquivo") or "index.html",
        "rota": page.get("route") or page.get("rota") or "",
        "icone": page.get("icon") or page.get("icone") or "fas fa-chart-line",
        "descricao": page.get("description") or page.get("descricao") or "",
        "pai": page.get("parent") or page.get("pai") or "",
        "ativo": not manifest_bool(page, "inactive", False),
        "rls": manifest_bool(page, "rls", False),
    }
    if workspace_password:
        payload["container_password"] = workspace_password
    return payload


def manifest_page_id(page: dict[str, Any]) -> str:
    return str(page.get("id") or page.get("page_id") or "").strip()


def page_create_name(page: dict[str, Any], display_name: str, desired_id: str) -> str:
    explicit = str(page.get("create_name") or page.get("technical_name") or "").strip()
    if explicit:
        return explicit
    if desired_id and slugify_page_id(display_name) != desired_id:
        return desired_id
    return display_name


def page_ids_to_replace(page: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for value in (
        manifest_page_id(page),
        slugify_page_id(payload.get("nome")),
        slugify_page_id(page.get("name") or page.get("nome")),
    ):
        if value and value not in ids:
            ids.append(value)
    return ids


def manifest_page_ref(page: dict[str, Any]) -> str:
    return str(page.get("id") or page.get("page_id") or page.get("route") or page.get("rota") or page.get("name") or "").strip()


def flatten_page_tree(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        roots = payload
    elif isinstance(payload, dict):
        roots = payload.get("pages") or payload.get("data") or payload.get("accessible_pages") or []
    else:
        roots = []
    flat: list[dict[str, Any]] = []

    def walk(items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            flat.append(item)
            walk(item.get("subpaginas") or item.get("children") or [])

    walk(roots)
    return flat


def load_accessible_pages_flat(client: RejoinBIClient) -> list[dict[str, Any]]:
    payload, _ = client.request("GET", "/plataforma/api/accessible-pages", timeout=60)
    return flatten_page_tree(payload)


def refresh_menu_caches(client: RejoinBIClient) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, path in (("clear-cache", "/plataforma/api/clear-menu-cache"), ("reload", "/plataforma/api/reload-menu")):
        try:
            data, response = client.request("POST", path, json={}, timeout=120)
            results.append({"action": name, "success": True, "status_code": response.status_code, "response": data})
        except RejoinBIError as exc:
            results.append({"action": name, "success": False, "error": str(exc)})
    return results


def wait_manifest_pages_ready(
    client: RejoinBIClient,
    pages: list[Any],
    *,
    timeout: float = 45.0,
    interval: float = 1.5,
    refresh: bool = True,
) -> dict[str, Any]:
    valid_pages = [page for page in pages if isinstance(page, dict)]
    deadline = time.monotonic() + max(0.0, timeout)
    attempts = 0
    refresh_results: list[dict[str, Any]] = []
    last_results: list[dict[str, Any]] = []
    while True:
        attempts += 1
        try:
            accessible_pages = load_accessible_pages_flat(client)
            accessible_by_id = {
                str(item.get("id") or "").strip(): item
                for item in accessible_pages
                if str(item.get("id") or "").strip()
            }
            last_results = []
            all_ready = True
            for page in valid_pages:
                page_ref = manifest_page_ref(page)
                expected_name = str(page.get("name") or page.get("nome") or "").strip()
                requires_container_name = bool(str(page.get("file") or page.get("arquivo") or "").strip())
                resolved: dict[str, Any] = {}
                resolved_page_id = page_ref
                resolve_error = ""
                if page_ref:
                    try:
                        resolved_payload, _ = client.request(
                            "GET",
                            f"/plataforma/api/capture/resolve-page/{quote(page_ref, safe='-_/')}",
                            timeout=60,
                        )
                        if isinstance(resolved_payload, dict):
                            resolved = resolved_payload
                            resolved_page_id = str(resolved.get("resolved_page_id") or page_ref).strip()
                    except RejoinBIError as exc:
                        resolve_error = str(exc)
                accessible_page = accessible_by_id.get(resolved_page_id) or accessible_by_id.get(page_ref) or {}
                accessible_name = str(
                    accessible_page.get("nome") or accessible_page.get("name") or ""
                ).strip() if isinstance(accessible_page, dict) else ""
                accessible_container_name = str(accessible_page.get("container_name") or "").strip() if isinstance(accessible_page, dict) else ""
                accessible_container_id = str(accessible_page.get("container_id") or "").strip() if isinstance(accessible_page, dict) else ""
                name_ok = not expected_name or not accessible_name or expected_name == accessible_name
                menu_safe = (not requires_container_name) or bool(accessible_container_name)
                found = bool(accessible_page)
                ready = found and name_ok and menu_safe and not resolve_error
                if not ready:
                    all_ready = False
                last_results.append({
                    "page_ref": page_ref,
                    "resolved_page_id": resolved_page_id,
                    "found_in_accessible_pages": found,
                    "expected_name": expected_name,
                    "accessible_name": accessible_name,
                    "name_ok": name_ok,
                    "requires_container_name": requires_container_name,
                    "container_id": accessible_container_id,
                    "container_name": accessible_container_name,
                    "menu_safe": menu_safe,
                    "resolve_error": resolve_error,
                    "resolved": resolved,
                })
            if all_ready:
                return {
                    "success": True,
                    "attempts": attempts,
                    "results": last_results,
                    "refresh": refresh_results,
                }
        except RejoinBIError as exc:
            last_results = [{"success": False, "error": str(exc)}]
        if time.monotonic() >= deadline:
            return {
                "success": False,
                "attempts": attempts,
                "results": last_results,
                "refresh": refresh_results,
                "message": "Pages are not menu-safe yet. Every client page must appear in accessible-pages with container_name before production is considered ready.",
            }
        if refresh:
            refresh_results.extend(refresh_menu_caches(client))
        time.sleep(max(0.2, interval))


def create_page_from_manifest(
    client: RejoinBIClient,
    workspace: dict[str, Any],
    page: dict[str, Any],
    *,
    workspace_password: str = "",
    replace: bool = False,
) -> dict[str, Any]:
    payload = page_payload_from_manifest(page, workspace, workspace_password)
    display_name = str(payload.get("nome") or "").strip()
    desired_id = manifest_page_id(page)
    create_name = page_create_name(page, display_name, desired_id)
    payload["nome"] = create_name
    if replace:
        for candidate_id in page_ids_to_replace(page, payload):
            delete_page(client, candidate_id, missing_ok=True)
    data, _ = client.request("POST", "/plataforma/api/paginas", json=payload, timeout=60)
    result = data if isinstance(data, dict) else {"raw": data}
    created_page_id = str(result.get("page_id") or "").strip()
    result["display_name"] = display_name
    result["create_name"] = create_name
    if desired_id:
        result["desired_page_id"] = desired_id
    if desired_id and created_page_id and created_page_id != desired_id:
        result["page_id_mismatch"] = {
            "expected": desired_id,
            "actual": created_page_id,
            "note": "The platform generated the page id from the creation name.",
        }
    if created_page_id and display_name and display_name != create_name:
        update_payload = {
            "nome": display_name,
            "container_id": payload.get("container_id"),
            "arquivo": payload.get("arquivo") or "",
            "rota": payload.get("rota") or "",
            "icone": payload.get("icone") or "fas fa-chart-line",
            "descricao": payload.get("descricao") or "",
            "pai": payload.get("pai") or "",
            "ativo": payload.get("ativo", True),
            "rls": payload.get("rls", False),
        }
        if workspace_password:
            update_payload["container_password"] = workspace_password
        update_data, _ = client.request(
            "PUT",
            f"/plataforma/api/paginas/{quote(created_page_id, safe='')}",
            json=update_payload,
            timeout=60,
        )
        result["display_name_update"] = update_data if isinstance(update_data, dict) else {"raw": update_data}
    page_ref = created_page_id or desired_id or payload.get("rota") or display_name
    if page_ref:
        try:
            resolved, _ = client.request("GET", f"/plataforma/api/capture/resolve-page/{quote(str(page_ref), safe='-_/')}", timeout=60)
            result["resolved"] = resolved
        except RejoinBIError as exc:
            result["resolve_error"] = str(exc)
    return result


def cmd_deploy_manifest(args: argparse.Namespace) -> int:
    manifest, manifest_path = load_manifest(args.manifest)
    bind_manifest_tenant(args, manifest)
    text_errors = manifest_text_integrity_errors(manifest)
    if text_errors:
        raise RejoinBIError("Manifest text integrity check failed:\n- " + "\n- ".join(text_errors))
    client = make_client(args)
    app_root = Path(args.path).expanduser().resolve() if args.path else (manifest_path.parent / str(manifest.get("app_root") or ".")).resolve()
    workspace_cfg = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
    upload_cfg = manifest.get("upload") if isinstance(manifest.get("upload"), dict) else {}
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
    if not pages:
        raise RejoinBIError("Manifest must include a non-empty pages array.")

    workspace_name = args.workspace or workspace_cfg.get("name") or manifest.get("workspace_name")
    if not workspace_name:
        raise RejoinBIError("Workspace name not provided. Use --workspace or manifest.workspace.name.")
    workspace_password = args.workspace_password or os.environ.get("REJOINBI_WORKSPACE_PASSWORD") or ""
    create_workspace = args.create_workspace or manifest_bool(workspace_cfg, "create", False)
    replace_pages = args.replace_pages or manifest_bool(manifest, "replace_pages", False)

    workspace = create_workspace_if_needed(
        client,
        workspace_name,
        password=workspace_password,
        description=str(workspace_cfg.get("description") or ""),
        create=create_workspace,
        timeout=args.timeout,
    )
    validation = validate_workspace_if_password(client, workspace, workspace_password)

    upload_result = None
    if not args.skip_upload:
        upload_result = upload_folder_with_options(
            client,
            workspace,
            app_root,
            startup_mode=args.startup_mode or upload_cfg.get("startup_mode") or "static",
            selected_file=args.selected_file or upload_cfg.get("selected_file") or "",
            startup_command=args.startup_command or upload_cfg.get("startup_command") or "",
            python_path=args.python_path or upload_cfg.get("python_path") or "auto",
            auto_start=not args.no_auto_start and manifest_bool(upload_cfg, "auto_start", True),
            rpa_support=manifest_bool(upload_cfg, "rpa_support", False),
            timeout=args.timeout,
            interval=args.interval,
            exclude=list(upload_cfg.get("exclude") or [".git", "venv", ".venv", "__pycache__", "node_modules", ".pytest_cache"]),
        )

    page_results = []
    for page in pages:
        if not isinstance(page, dict):
            raise RejoinBIError(f"Invalid page entry in manifest: {page}")
        page_results.append(create_page_from_manifest(
            client,
            workspace,
            page,
            workspace_password=workspace_password,
            replace=replace_pages,
        ))

    menu_refresh = refresh_menu_caches(client)
    page_readiness = None
    if not args.no_page_readiness:
        page_readiness = wait_manifest_pages_ready(
            client,
            pages,
            timeout=args.readiness_timeout,
            interval=args.interval,
            refresh=True,
        )
    success = page_readiness is None or bool(page_readiness.get("success"))
    print_payload({
        "success": success,
        "manifest": str(manifest_path),
        "app_root": str(app_root),
        "tenant": tenant_host_from_base_url(client.base_url),
        "workspace": {"id": workspace.get("id"), "name": workspace.get("name"), "status": workspace.get("deploy_status")},
        "workspace_validation": validation,
        "upload": upload_result,
        "pages": page_results,
        "menu_refresh": menu_refresh,
        "page_readiness": page_readiness,
        "count": len(page_results),
    }, as_json=args.json)
    return 0 if success else 1


def cmd_smoke_pages(args: argparse.Namespace) -> int:
    manifest, manifest_path = load_manifest(args.manifest)
    bind_manifest_tenant(args, manifest)
    client = make_client(args)
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
    readiness = wait_manifest_pages_ready(
        client,
        pages,
        timeout=args.readiness_timeout,
        interval=args.interval,
        refresh=not args.no_refresh_menu,
    )
    try:
        accessible_payload, _ = client.request("GET", "/plataforma/api/accessible-pages", timeout=60)
    except RejoinBIError as exc:
        accessible_payload = {"success": False, "error": str(exc)}

    accessible_pages = flatten_page_tree(accessible_payload)
    accessible_by_id = {str(item.get("id") or "").strip(): item for item in accessible_pages if str(item.get("id") or "").strip()}
    results = []
    for page in pages:
        page_ref = page.get("id") or page.get("page_id") or page.get("route") or page.get("rota") or page.get("name")
        if not page_ref:
            continue
        resolved, _ = client.request("GET", f"/plataforma/api/capture/resolve-page/{quote(str(page_ref), safe='-_/')}", timeout=60)
        capture_path = resolved.get("capture_path") if isinstance(resolved, dict) else None
        html_ok = False
        status_code = None
        if capture_path:
            response = client.session.get(client.url(capture_path), timeout=args.timeout)
            prefer_utf8_response(response)
            status_code = response.status_code
            expected = page.get("expect_text") or page.get("name") or ""
            html_ok = response.ok and (not expected or str(expected) in response.text)
        resolved_page_id = str(resolved.get("resolved_page_id") or page_ref).strip() if isinstance(resolved, dict) else str(page_ref)
        accessible_page = accessible_by_id.get(resolved_page_id, {})
        resolved_container_name = str((resolved or {}).get("resolved_container_name") or "").strip() if isinstance(resolved, dict) else ""
        resolved_container_id = str((resolved or {}).get("resolved_container_id") or accessible_page.get("container_id") or "").strip() if isinstance(resolved, dict) else str(accessible_page.get("container_id") or "").strip()
        accessible_container_name = str(accessible_page.get("container_name") or "").strip() if isinstance(accessible_page, dict) else ""
        browser_route = str(accessible_page.get("rota") or (resolved or {}).get("resolved_client_path") or page.get("route") or page.get("rota") or "").strip("/") if isinstance(accessible_page, dict) else ""
        browser_status_code = None
        browser_route_ok = False
        if resolved_container_name:
            from urllib.parse import urlencode
            route_part = quote(browser_route, safe="/") if browser_route else ""
            browser_path = f"/plataforma/{quote(resolved_container_name, safe='')}/client/{route_part}"
            if not browser_path.endswith("/client/") and not route_part:
                browser_path += "/"
            browser_path = f"{browser_path}?{urlencode({'pagina_id': resolved_page_id, 'capture_strict': '1'})}"
            browser_response = client.session.get(client.url(browser_path), timeout=args.timeout)
            prefer_utf8_response(browser_response)
            browser_status_code = browser_response.status_code
            expected = page.get("expect_text") or page.get("name") or ""
            browser_route_ok = browser_response.ok and (not expected or str(expected) in browser_response.text)
        fallback_container = f"container_{resolved_container_id}" if resolved_container_id else ""
        menu_safe = bool(accessible_container_name) or not fallback_container
        menu_warning = ""
        if fallback_container and not accessible_container_name:
            menu_warning = (
                "accessible-pages did not include container_name; older browser menu code can fall back "
                f"to {fallback_container} and open a 404 URL before window.containers is ready."
            )
        results.append({
            "page_ref": page_ref,
            "resolved": resolved,
            "status_code": status_code,
            "html_ok": html_ok,
            "browser_status_code": browser_status_code,
            "browser_route_ok": browser_route_ok,
            "menu_safe": menu_safe,
            "menu_warning": menu_warning,
            "accessible_page": {
                "id": accessible_page.get("id") if isinstance(accessible_page, dict) else None,
                "name": accessible_page.get("nome") if isinstance(accessible_page, dict) else None,
                "route": accessible_page.get("rota") if isinstance(accessible_page, dict) else None,
                "file": accessible_page.get("arquivo") if isinstance(accessible_page, dict) else None,
                "container_id": accessible_page.get("container_id") if isinstance(accessible_page, dict) else None,
                "container_name": accessible_page.get("container_name") if isinstance(accessible_page, dict) else None,
            },
        })
    success = all(item.get("html_ok") and item.get("browser_route_ok") and item.get("menu_safe") for item in results) and bool(readiness.get("success"))
    print_payload({
        "success": success,
        "manifest": str(manifest_path),
        "tenant": tenant_host_from_base_url(client.base_url),
        "readiness": readiness,
        "results": results,
        "count": len(results),
    }, as_json=args.json)
    return 0 if success else 1


def cmd_smoke_admin(args: argparse.Namespace) -> int:
    client = make_client(args)
    checks: list[dict[str, Any]] = [
        {"name": "session-status", "method": "GET", "path": "/plataforma/api/session-status", "required": True},
        {"name": "check-session", "method": "GET", "path": "/plataforma/api/check-session", "required": True},
        {"name": "workspaces", "method": "GET", "path": "/plataforma/api/containers", "required": True},
        {"name": "users", "method": "GET", "path": "/plataforma/api/users", "required": True},
        {"name": "sectors", "method": "GET", "path": "/plataforma/api/setores", "required": True},
        {"name": "permissive-pages", "method": "GET", "path": "/plataforma/api/permissive-pages", "required": True},
        {"name": "user-presence", "method": "GET", "path": "/plataforma/api/users-presence", "required": False},
        {"name": "groups", "method": "GET", "path": "/plataforma/api/grupos", "required": False},
        {"name": "announcements", "method": "GET", "path": "/plataforma/api/anuncios/historico", "required": False},
        {"name": "platform-config", "method": "GET", "path": "/plataforma/api/platform-config", "required": True},
        {"name": "colors-config", "method": "GET", "path": "/plataforma/api/cores-config", "required": True},
        {"name": "menu", "method": "GET", "path": "/plataforma/api/menu", "required": True},
        {"name": "menu-duplicates", "method": "GET", "path": "/plataforma/api/check-menu-duplicates", "required": False},
        {
            "name": "pages-all",
            "method": "GET",
            "path": "/plataforma/api/paginas",
            "params": {"all_containers": "true", "include_inactive": "true", "exclude_fictitious": "false"},
            "required": True,
        },
        {"name": "accessible-pages", "method": "GET", "path": "/plataforma/api/accessible-pages", "required": True},
        {"name": "page-hierarchy", "method": "GET", "path": "/plataforma/api/paginas/verificar-hierarquia", "required": False},
        {"name": "page-orphan-permissions", "method": "GET", "path": "/plataforma/api/paginas/verificar-permissoes-orfas", "required": False},
        {"name": "rls-pages", "method": "GET", "path": "/plataforma/api/rls-pages", "required": False},
        {"name": "audit-dashboard", "method": "GET", "path": "/plataforma/api/audit/dashboard", "required": False},
        {"name": "sleep-manager-status", "method": "GET", "path": "/plataforma/api/sleep-manager/status", "required": False},
        {"name": "email-sessions", "method": "GET", "path": "/plataforma/api/email/sessions", "required": False},
        {"name": "whatsapp-sessions", "method": "GET", "path": "/plataforma/api/whatsapp/sessions", "required": False},
        {"name": "upload-capabilities", "method": "GET", "path": "/plataforma/api/upload-capabilities", "required": False},
        {"name": "python-versions", "method": "GET", "path": "/plataforma/api/python-versions", "required": False},
        {"name": "gateway-pairings", "method": "GET", "path": "/plataforma/api/gateway/pairings", "required": False},
        {"name": "route-map-routes", "method": "GET", "path": "/plataforma/api/route-mapping/routes", "required": False},
        {"name": "codex-keys-stats", "method": "GET", "path": "/plataforma/api/codex/keys/stats", "required": False},
        {"name": "data-engine-status", "method": "GET", "path": "/plataforma/data-engine/api/status", "required": False},
        {"name": "system-database-status", "method": "GET", "path": "/plataforma/api/database/status", "required": False},
        {"name": "system-runtime-readiness", "method": "GET", "path": "/plataforma/api/runtime-readiness", "required": False},
    ]
    results: list[dict[str, Any]] = []
    for check in checks:
        path = path_with_query(check["path"], check.get("params"))
        try:
            payload, response = client.request(check["method"], path, timeout=args.timeout)
            result = {
                "name": check["name"],
                "required": bool(check.get("required")),
                "status": "ok",
                "http_status": response.status_code,
                "summary": payload_summary(payload),
            }
        except RejoinBIError as exc:
            error = str(exc)
            result = {
                "name": check["name"],
                "required": bool(check.get("required")),
                "status": classify_smoke_error(error),
                "error": error,
            }
        results.append(result)

    required_failures = [item for item in results if item.get("required") and item.get("status") != "ok"]
    optional_issues = [item for item in results if not item.get("required") and item.get("status") != "ok"]
    success = not required_failures and (not args.strict or not optional_issues)
    report = {
        "success": success,
        "base_url": client.base_url,
        "strict": bool(args.strict),
        "counts": {
            "total": len(results),
            "ok": sum(1 for item in results if item.get("status") == "ok"),
            "required_failures": len(required_failures),
            "optional_issues": len(optional_issues),
        },
        "results": results,
    }
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "smoke-admin.json", report)
        report["output"] = str(output_dir / "smoke-admin.json")
    print_payload(report, as_json=args.json)
    return 0 if success else 1


def find_html_links_to_local_pages(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    findings = []
    patterns = [
        r"data-route\s*=",
        r"history\.pushState\s*\(",
        r"location\.hash",
        r"class\s*=\s*['\"][^'\"]*(?:nav|rail|sidebar)[^'\"]*['\"]",
    ]
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            findings.append(pattern)
    hrefs = re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.I)
    for href in hrefs:
        if href.startswith(("#", "http://", "https://", "mailto:", "tel:", "./assets/", "assets/", "/static/")):
            continue
        if href.endswith((".html", "/")) or not Path(href).suffix:
            findings.append(f"href={href}")
    return findings


def scan_flask_routes(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    routes = []
    for match in re.finditer(r"@app\.route\(\s*['\"]([^'\"]+)['\"]", text):
        route = match.group(1)
        if route.startswith("/api/") or route.startswith("/static/") or route in {"/", "/health", "/status"}:
            level = "ok"
            message = "compatible"
        else:
            level = "warning"
            message = "data/backend routes should normally use /api/ to avoid platform proxy conflicts"
        routes.append({"route": route, "level": level, "message": message})
    return routes


def cmd_validate_app(args: argparse.Namespace) -> int:
    manifest = {}
    manifest_path = None
    if args.manifest:
        manifest, manifest_path = load_manifest(args.manifest)
    app_root = Path(args.path).expanduser().resolve() if args.path else None
    if not app_root and manifest_path:
        app_root = (manifest_path.parent / str(manifest.get("app_root") or ".")).resolve()
    if not app_root:
        raise RejoinBIError("Pass --path or --manifest.")
    if not app_root.is_dir():
        raise RejoinBIError(f"Folder not found: {app_root}")

    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
    upload_cfg = manifest.get("upload") if isinstance(manifest.get("upload"), dict) else {}
    startup_mode = str(args.startup_mode or upload_cfg.get("startup_mode") or "static").strip().lower()
    manifest_language = detect_manifest_language(manifest)
    errors.extend(manifest_text_integrity_errors(manifest))

    if pages:
        files_by_page = []
        seen_routes = set()
        seen_ids = set()
        workspace_cfg = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
        workspace_name_for_pages = str(workspace_cfg.get("name") or manifest.get("workspace_name") or "").strip()
        workspace_name_key = normalize_text(workspace_name_for_pages)
        for page in pages:
            if not isinstance(page, dict):
                errors.append(f"Invalid manifest page entry: {page}")
                continue
            page_id = str(page.get("id") or page.get("page_id") or "").strip()
            page_display_name = str(page.get("name") or page.get("nome") or "").strip()
            route = str(page.get("route") or page.get("rota") or "").strip()
            file_name = str(page.get("file") or page.get("arquivo") or "").strip()
            if not page_id:
                errors.append(f"Page missing id/page_id: {page}")
            elif page_id in seen_ids:
                errors.append(f"Duplicate page id: {page_id}")
            elif not re.match(r"^[a-z0-9][a-z0-9_-]*$", page_id):
                errors.append(f"Page id must be ASCII slug with letters, numbers, hyphen, or underscore: {page_id}")
            elif page_display_name and slugify_page_id(page_display_name) != page_id:
                checks.append({
                    "name": "page_id_display_name_decoupled",
                    "page_id": page_id,
                    "display_name": page_display_name,
                    "create_name": page.get("create_name") or page.get("technical_name") or page_id,
                    "message": "deploy-manifest will create using the technical id and then restore the clean display name.",
                })
            seen_ids.add(page_id)
            if workspace_name_key and page_display_name:
                page_name_key = normalize_text(page_display_name)
                if page_name_key == workspace_name_key or page_name_key.startswith(f"{workspace_name_key} -") or page_name_key.startswith(f"{workspace_name_key} "):
                    warnings.append(
                        f"Page '{page_display_name}' includes the workspace prefix. Keep visible page names clean and put the prefix only in id/page_id."
                    )
            if manifest_language.lower().startswith("pt"):
                suggested_name = suggest_pt_br_display_name(page_display_name)
                if suggested_name and suggested_name != page_display_name:
                    warnings.append(
                        f"Page '{page_display_name}' looks like pt-BR text without accents. Suggested display name: '{suggested_name}'."
                    )
            if not route:
                warnings.append(f"Page {page_id or page.get('name')} has no custom route; Gerenciar Paginas will fall back to file route.")
            elif route in seen_routes:
                errors.append(f"Duplicate page route: {route}")
            elif not re.match(r"^[A-Za-z0-9_/-]+$", route) or route.endswith(".html") or ".." in route:
                errors.append(f"Page route must be a clean ASCII route without .html or traversal: {route}")
            seen_routes.add(route)
            if not file_name:
                errors.append(f"Page {page_id or route} has no HTML file.")
                continue
            file_route = file_name.replace("\\", "/")
            if file_route.lower().endswith(".html"):
                file_route = file_route[:-5].strip("/")
            if route and file_route and route.strip("/") != file_route and not manifest_bool(page, "allow_custom_route", False):
                warnings.append(
                    f"Page {page_id or page_display_name} uses route '{route}' but file route is '{file_route}'. "
                    "For static dashboards, prefer route equal to the HTML file path without .html."
                )
            page_file = (app_root / file_name).resolve()
            if not str(page_file).startswith(str(app_root)):
                errors.append(f"Page file escapes app root: {file_name}")
                continue
            if not page_file.exists():
                errors.append(f"Page file not found: {file_name}")
            elif page_file.suffix.lower() != ".html":
                if startup_mode == "static":
                    errors.append(f"Static page {page_id or route} must point to an .html file: {file_name}")
                else:
                    warnings.append(f"Page {page_id or route} points to non-HTML file: {file_name}")
            else:
                internal_nav = find_html_links_to_local_pages(page_file)
                if internal_nav:
                    warnings.append(f"{file_name} appears to include internal navigation/router markers: {', '.join(internal_nav[:4])}")
            files_by_page.append(file_name)
        if len(set(files_by_page)) == 1 and len(files_by_page) > 1:
            warnings.append("Multiple pages point to the same HTML file. Prefer one standalone HTML file per Rejoin BI page.")
    else:
        warnings.append("No manifest pages found. Gerenciar Paginas compatibility cannot be fully checked.")

    if startup_mode == "static":
        html_files = sorted(p.relative_to(app_root).as_posix() for p in app_root.rglob("*.html"))
        if not html_files:
            errors.append("Static mode requires at least one HTML file.")
        checks.append({"name": "static_html_files", "count": len(html_files), "files": html_files[:20]})
    elif startup_mode == "file":
        selected = str(args.selected_file or upload_cfg.get("selected_file") or "").strip()
        candidates = [selected] if selected else ["app.py", "main.py"]
        if not any((app_root / candidate).exists() for candidate in candidates if candidate):
            errors.append("File startup mode requires selected_file, app.py, or main.py.")
    elif startup_mode == "command":
        command = str(args.startup_command or upload_cfg.get("startup_command") or "").strip()
        if not command:
            errors.append("Command startup mode requires startup_command.")
        if len(command) > 500:
            errors.append("startup_command exceeds the platform limit of 500 characters.")
    else:
        errors.append(f"Invalid startup_mode: {startup_mode}")

    for py_file in [app_root / "app.py", app_root / "main.py"]:
        if py_file.exists():
            try:
                compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")
                checks.append({"name": f"python_syntax:{py_file.name}", "ok": True})
            except SyntaxError as exc:
                errors.append(f"{py_file.name} has Python syntax error at line {exc.lineno}: {exc.msg}")
                checks.append({"name": f"python_syntax:{py_file.name}", "ok": False, "line": exc.lineno, "message": exc.msg})
            except UnicodeDecodeError:
                errors.append(f"{py_file.name} is not valid UTF-8.")
                checks.append({"name": f"python_syntax:{py_file.name}", "ok": False, "message": "invalid_utf8"})
            route_scan = scan_flask_routes(py_file)
            checks.append({"name": f"flask_routes:{py_file.name}", "routes": route_scan})
            for item in route_scan:
                if item.get("level") == "warning":
                    warnings.append(f"{py_file.name} route {item.get('route')}: {item.get('message')}")

    noisy_dirs = [name for name in (".git", "venv", ".venv", "node_modules", "__pycache__", ".pytest_cache") if (app_root / name).exists()]
    if noisy_dirs:
        warnings.append(f"Folder contains upload-noise directories that should be excluded: {', '.join(noisy_dirs)}")

    workspace_cfg = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
    workspace_name = str(workspace_cfg.get("name") or "").strip()
    if workspace_name and not re.match(r"^[A-Za-z0-9_-]+$", workspace_name):
        warnings.append("Workspace name contains characters outside letters, numbers, underscore, or hyphen.")
    if workspace_name and len(workspace_name) > 40:
        warnings.append("Workspace name is long; keep it short for UI readability.")

    success = not errors and (not args.strict or not warnings)
    print_payload({
        "success": success,
        "app_root": str(app_root),
        "manifest": str(manifest_path) if manifest_path else None,
        "startup_mode": startup_mode,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "workspace_rules": [
            "For platform dashboards, create one standalone HTML file per Rejoin BI page.",
            "Do not create internal page menus, sidebars, or SPA route switchers inside dashboard files.",
            "Use Gerenciar Paginas for menu hierarchy, icon, permission, route, parent page, and active status.",
            "For Flask data endpoints, use /api/ routes to avoid platform proxy conflicts.",
            "Upload the project root and exclude virtualenv/cache/node_modules/temp folders.",
            "Use static startup mode for HTML/ECharts-only dashboards.",
        ],
    }, as_json=args.json)
    return 0 if success else 2


def parse_json_payload(args: argparse.Namespace) -> Any:
    if getattr(args, "data_file", None):
        return load_json_file(args.data_file)
    raw = getattr(args, "data_json", None)
    if raw:
        return json.loads(raw)
    return {}


def cmd_api_get(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", args.path, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def cmd_api_post(args: argparse.Namespace) -> int:
    require_yes(args, "api-send can mutate tenant state and requires --yes after reviewing the target path and payload.")
    client = make_client(args)
    payload = parse_json_payload(args)
    data, _ = client.request(args.method.upper(), args.path, json=payload, timeout=args.timeout)
    print_payload(scrub_sensitive(data), as_json=args.json)
    return 0


def should_ignore_export(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    ignored_names = {
        ".codex",
        ".env",
        ".git",
        ".rejoinbi-platform",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".ssh",
        "__pycache__",
        "artifacts",
        "branding-backups",
        "smoke-admin",
        "test-runs",
    }
    for name in names:
        lower = name.lower()
        if (
            lower in ignored_names
            or lower.endswith((".pyc", ".pyo", ".zip"))
            or any(fnmatch.fnmatch(lower, pattern) for pattern in SENSITIVE_PATH_PATTERNS)
        ):
            ignored.add(name)
    return ignored


def write_install_notes(target: Path, package_zip: Path | None) -> None:
    zip_line = f"- Zip package: `{package_zip.name}`\n" if package_zip else ""
    notes = f"""# Rejoin BI Platform Plugin

This folder is a shareable Codex plugin package generated from:

`{PLUGIN_ROOT}`

## Install

Copy the `rejoinbi-platform` folder into the recipient Codex plugins folder, or import/use the zip package if their Codex setup supports plugin zip import.

Typical local path:

```powershell
$HOME\\plugins\\rejoinbi-platform
```

## Configure A Tenant

```powershell
python .\\rejoinbi-platform\\scripts\\rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure
python .\\rejoinbi-platform\\scripts\\rejoinbi.py workspaceall
```

The `ensure` command checks for a saved tenant session first. If needed, it opens a local browser login wizard. Passwords and PINs are never saved in the package and do not need to be pasted into chat.

## Dashboard Pattern

Dashboards must be standalone pages. Do not build an internal menu or SPA page switcher inside the dashboard, because Rejoin BI manages page hierarchy, icon, permission, route, and menu placement through Gerenciar Paginas.

Use `examples\\codex-advanced-suite\\rejoinbi-app.json` as the model: one HTML file per platform page, each with its own `file` and `route`.

## Safe Cleanup

Workspace and page deletion commands are dry-run by default and print the affected page tree before deleting:

```powershell
python .\\rejoinbi-platform\\scripts\\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-workspace --workspace codex-suite
python .\\rejoinbi-platform\\scripts\\rejoinbi.py --tenant subdomain.rejoinbi.com.br delete-page --page-id codex-suite-overview
```

Actual deletion requires exact confirmation flags such as `--confirm-name`, `--confirm-id`, or `--confirm-page-id`.

## Package Contents

- Plugin manifest: `rejoinbi-platform\\.codex-plugin\\plugin.json`
- Skill instructions: `rejoinbi-platform\\skills\\rejoinbi-platform\\SKILL.md`
- CLI: `rejoinbi-platform\\scripts\\rejoinbi.py`
- Example dashboards: `rejoinbi-platform\\examples`
{zip_line}"""
    (target / "INSTALL.md").write_text(notes, encoding="utf-8")


def cmd_export_package(args: argparse.Namespace) -> int:
    destination = Path(args.destination or (Path.home() / "Downloads" / "plugin")).expanduser().resolve()
    package_dir = destination / "rejoinbi-platform"
    destination.mkdir(parents=True, exist_ok=True)

    if args.clean and package_dir.exists():
        dest_text = str(destination)
        pkg_text = str(package_dir.resolve())
        if not (pkg_text == dest_text or pkg_text.startswith(dest_text + os.sep)):
            raise RejoinBIError(f"Refusing to clean outside destination: {package_dir}")
        shutil.rmtree(package_dir)

    shutil.copytree(PLUGIN_ROOT, package_dir, ignore=should_ignore_export, dirs_exist_ok=True)

    package_zip = None
    if not args.no_zip:
        zip_base = destination / "rejoinbi-platform"
        zip_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=destination, base_dir="rejoinbi-platform"))
        package_zip = zip_path

    write_install_notes(destination, package_zip)
    print_payload({
        "success": True,
        "destination": str(destination),
        "package_dir": str(package_dir),
        "zip": str(package_zip) if package_zip else None,
        "install_notes": str(destination / "INSTALL.md"),
    }, as_json=args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rejoin BI Platform helper CLI")
    parser.add_argument("--tenant", help="Full tenant host or URL, e.g. subdomain.rejoinbi.com.br")
    parser.add_argument("--subdomain", help="Legacy tenant shorthand or host. Prefer --tenant subdomain.rejoinbi.com.br")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Base domain used only for legacy short subdomains")
    parser.add_argument("--base-url", help="Exact tenant base URL")
    parser.add_argument("--use-active-tenant", action="store_true", help="Allow mutating commands to use the last saved active tenant")
    parser.add_argument("--json", action="store_true", default=True, help="Print JSON output")
    parser.add_argument(
        "--allow-standard",
        action="store_true",
        help="Allow non-admin profiles for negative tests. By default only admin/principal/master sessions are accepted.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_payload_args(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--data-json", help="Raw JSON payload for POST/PUT/PATCH/DELETE actions")
        command_parser.add_argument("--data-file", help="JSON payload file for POST/PUT/PATCH/DELETE actions")

    for name in ("connect", "login"):
        p = sub.add_parser(name, help="Authenticate and save tenant session cookies. Opens a browser wizard if no password is provided.")
        p.add_argument("--email")
        p.add_argument("--password")
        p.add_argument("--pin")
        p.add_argument("--lang", default="pt-BR")
        p.add_argument("--terminal", action="store_true", help="Use terminal/env password flow instead of the browser auth wizard")
        p.add_argument("--auth-port", type=int, default=0, help="Local browser auth port. Default: random free port")
        p.add_argument("--auth-timeout", type=int, default=600, help="Seconds to wait for browser auth")
        p.add_argument("--no-open-browser", action="store_true", help="Print/use the local auth URL without opening the browser automatically")
        p.set_defaults(func=cmd_connect)

    for name in ("ensure", "ensure-connected", "tenant"):
        p = sub.add_parser(name, help="Check saved tenant session and open browser auth only if needed")
        p.add_argument("--email", help="Optional email to prefill if browser auth is needed")
        p.add_argument("--lang", default="pt-BR")
        p.add_argument("--auth-port", type=int, default=0, help="Local browser auth port. Default: random free port")
        p.add_argument("--auth-timeout", type=int, default=600, help="Seconds to wait for browser auth")
        p.add_argument("--no-open-browser", action="store_true", help="Print/use the local auth URL without opening the browser automatically")
        p.set_defaults(func=cmd_ensure_connected, password=None, pin=None, terminal=False)

    for name in ("auth", "browser-login"):
        p = sub.add_parser(name, help="Open a local browser login wizard and save tenant session cookies")
        p.add_argument("--email", help="Optional email to prefill in the browser wizard")
        p.add_argument("--lang", default="pt-BR")
        p.add_argument("--auth-port", type=int, default=0, help="Local browser auth port. Default: random free port")
        p.add_argument("--auth-timeout", type=int, default=600, help="Seconds to wait for browser auth")
        p.add_argument("--no-open-browser", action="store_true", help="Print/use the local auth URL without opening the browser automatically")
        p.set_defaults(func=cmd_browser_login, password=None, pin=None, terminal=False)

    p = sub.add_parser("status", help="Check current session")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("workspaceall", help="List all workspaces/containers")
    p.set_defaults(func=cmd_workspaceall)

    p = sub.add_parser("validate-workspace", help="Validate and unlock a protected workspace")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--password")
    p.set_defaults(func=cmd_validate_workspace)

    p = sub.add_parser("workspace-content", help="List workspace repository content")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--folder", default="")
    p.set_defaults(func=cmd_workspace_content)

    p = sub.add_parser("create-workspace", help="Create a workspace/container")
    p.add_argument("--name", required=True)
    p.add_argument("--password")
    p.add_argument("--description", default="")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_create_workspace)

    p = sub.add_parser("update-workspace", help="Update workspace/container metadata")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--name")
    p.add_argument("--password")
    p.add_argument("--active", action="store_true")
    p.add_argument("--inactive", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_update_workspace)

    p = sub.add_parser("delete-workspace", aliases=["workspace-delete"], help="Preview and safely delete one workspace/container")
    p.add_argument("--workspace", required=True, help="Workspace id or exact name")
    p.add_argument("--confirm-name", help="Required with --yes. Must exactly match the resolved workspace name.")
    p.add_argument("--confirm-id", help="Optional extra guard. Must exactly match the resolved workspace id.")
    p.add_argument("--yes", action="store_true", help="Actually delete after all guards pass")
    p.add_argument("--dry-run", action="store_true", help="Only show the deletion plan")
    p.add_argument("--workspace-password", help="Required to delete a password-protected workspace")
    p.add_argument("--allow-linked-pages", action="store_true", help="Allow deletion when linked pages outside the workspace are in the cascade")
    p.add_argument("--force-reserved", action="store_true", help="Allow reserved/protected workspace names after manual review")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_delete_workspace)

    p = sub.add_parser("set-workspace-password", help="Set or clear a workspace password")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--password")
    p.set_defaults(func=cmd_set_workspace_password)

    for action in ("start", "stop", "restart", "status"):
        p = sub.add_parser(f"workspace-{action}", help=f"{action.title()} a workspace/container")
        p.add_argument("--workspace", required=True, help="Workspace id or name")
        p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
        p.set_defaults(func=cmd_workspace_action, action=action)

    p = sub.add_parser("workspace-logs", help="Read workspace runtime/deploy logs")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--deploy-id")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_workspace_logs)

    p = sub.add_parser("workspace-versions", help="List workspace upload/version history")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_workspace_versions)

    for name, version_action, help_text in (
        ("workspace-version-export", "export", "Export one workspace version"),
        ("workspace-version-restore", "restore", "Restore one workspace version"),
        ("workspace-version-delete", "delete", "Delete one workspace version"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--workspace", required=True, help="Workspace id or name")
        p.add_argument("--sha", required=True, help="Version SHA")
        p.add_argument("--output", default="workspace-version.zip")
        p.add_argument("--yes", action="store_true")
        p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
        p.set_defaults(func=cmd_workspace_version_action, action=version_action)

    p = sub.add_parser("workspace-schedule", help="Read, set, or delete workspace schedules")
    p.add_argument("action", choices=["get", "set", "delete"])
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--schedule-id")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_workspace_schedule)

    p = sub.add_parser("workspace-notification", help="Manage workspace notification settings")
    p.add_argument("action", choices=["config", "set-config", "history", "users", "email-sessions", "email-groups", "whatsapp-sessions", "whatsapp-groups"])
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_workspace_notification)

    p = sub.add_parser("workspace-input", help="Send terminal input to a running workspace")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--input", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_workspace_terminal_input)

    p = sub.add_parser("workspace-build", help="Trigger a workspace container build")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_workspace_build)

    p = sub.add_parser("workspace-stop-all", help="Stop all workspaces/containers")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_workspace_stop_all)

    p = sub.add_parser("upload-files", help="Upload individual files directly into a workspace app folder")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--folder", default="")
    p.add_argument("--message")
    p.add_argument("--map", action="append", help="filename=target/folder mapping")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--workspace-password")
    p.add_argument("--allow-sensitive-files", action="store_true", help="Allow uploading files that look like secrets after manual review")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_upload_files)

    for name, help_text, func in (
        ("upload-zip-select", "Upload a ZIP then choose startup options like the UI", cmd_upload_zip_select),
        ("upload-folder-select", "Upload a folder then choose startup options like the UI", cmd_upload_folder_select),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--workspace", required=True, help="Workspace id or name")
        if name == "upload-zip-select":
            p.add_argument("--zip", required=True)
        else:
            p.add_argument("--path", required=True)
            p.add_argument("--exclude", action="append", default=[".git", "venv", ".venv", "__pycache__", "node_modules", ".pytest_cache"])
        p.add_argument("--allow-sensitive-files", action="store_true", help="Allow uploading files that look like secrets after manual review")
        p.add_argument("--selected-file", default="")
        p.add_argument("--startup-mode", choices=["file", "command", "static"], default="file")
        p.add_argument("--startup-command", default="")
        p.add_argument("--python-path", default="auto")
        p.add_argument("--auto-start", action="store_true", default=True)
        p.add_argument("--no-auto-start", dest="auto_start", action="store_false")
        p.add_argument("--rpa-support", action="store_true")
        p.add_argument("--workspace-password")
        p.add_argument("--timeout", type=int, default=900)
        p.add_argument("--interval", type=float, default=3.0)
        p.set_defaults(func=func)

    p = sub.add_parser("bi-projects", help="List BI Studio projects")
    p.set_defaults(func=cmd_bi_projects)

    p = sub.add_parser(
        "studio-inventory",
        aliases=["bi-inventory", "bi-data-inventory"],
        help="Read-only inventory of BI Studio projects and linked Data Engine resources",
    )
    p.add_argument("--project-id", help="Limit inventory to one BI/Data Engine project id")
    p.add_argument("--project-uid", help="Limit inventory to one BI/Data Engine project uid")
    p.add_argument("--limit", type=int, default=25, help="Maximum summarized items per endpoint")
    p.add_argument("--include-raw", action="store_true", help="Include sanitized raw endpoint payloads")
    p.add_argument("--include-global-context", action="store_true", default=True)
    p.add_argument("--no-global-context", dest="include_global_context", action="store_false")
    p.add_argument("--include-sessions", action="store_true", default=True)
    p.add_argument("--no-sessions", dest="include_sessions", action="store_false")
    p.add_argument("--include-files", action="store_true", default=True)
    p.add_argument("--no-files", dest="include_files", action="store_false")
    p.add_argument("--output", help="Optional JSON report path")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_studio_inventory)

    p = sub.add_parser("bi-create-project", help="Create a BI Studio project")
    p.add_argument("--name", required=True)
    p.add_argument("--password")
    p.set_defaults(func=cmd_bi_create_project)

    p = sub.add_parser("bi-init-canvas", help="Initialize BI Studio canvas files for a project")
    p.add_argument("--project-id", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_init_canvas)

    p = sub.add_parser("bi-tabs", help="List BI Studio tabs")
    p.add_argument("--project-id", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_tabs)

    p = sub.add_parser("bi-tab-content", help="Read BI Studio tab HTML content")
    p.add_argument("--project-id", required=True)
    p.add_argument("--tab", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_tab_content)

    p = sub.add_parser("bi-create-tab", help="Create a BI Studio tab")
    p.add_argument("--project-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_create_tab)

    p = sub.add_parser("bi-duplicate-tab", help="Duplicate a BI Studio tab")
    p.add_argument("--project-id", required=True)
    p.add_argument("--source-name")
    p.add_argument("--source-slug")
    p.add_argument("--new-name", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_duplicate_tab)

    p = sub.add_parser("bi-rename-tab", help="Rename a BI Studio tab and sync project references")
    p.add_argument("--project-id", required=True)
    p.add_argument("--old-name")
    p.add_argument("--old-slug")
    p.add_argument("--new-name", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_rename_tab)

    p = sub.add_parser("bi-delete-tab", help="Delete a BI Studio tab")
    p.add_argument("--project-id", required=True)
    p.add_argument("--name")
    p.add_argument("--slug")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_delete_tab)

    p = sub.add_parser("bi-reorder-tabs", help="Reorder BI Studio tabs")
    p.add_argument("--project-id", required=True)
    p.add_argument("--order", required=True, help="Comma-separated tab names/slugs or JSON array")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_reorder_tabs)

    p = sub.add_parser("bi-load-layout", help="Load BI Studio canvas layout for a tab")
    p.add_argument("--project-id", required=True)
    p.add_argument("--tab", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_load_layout)

    p = sub.add_parser("bi-save-layout", help="Save BI Studio canvas layout/page size/theme/components for a tab")
    p.add_argument("--project-id", required=True)
    p.add_argument("--tab")
    p.add_argument("--data-file", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_save_layout)

    p = sub.add_parser("bi-themes", help="List BI Studio project themes")
    p.add_argument("--project-id", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_themes)

    p = sub.add_parser("bi-save-theme", help="Save/update a BI Studio project theme")
    p.add_argument("--project-id", required=True)
    p.add_argument("--data-file", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_save_theme)

    p = sub.add_parser("bi-delete-theme", help="Delete a BI Studio project theme")
    p.add_argument("--project-id", required=True)
    p.add_argument("--theme-id", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_delete_theme)

    p = sub.add_parser("bi-export", help="Export a BI Studio project ZIP")
    p.add_argument("--project-id", required=True)
    p.add_argument("--output")
    p.add_argument("--project-password")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_export)

    p = sub.add_parser("bi-normalize-export", help="Normalize a BI Studio export folder for Rejoin BI workspace routes")
    p.add_argument("--path", required=True, help="Extracted BI Studio export folder")
    p.add_argument("--remove-old", action="store_true", help="Remove accent/non-ASCII technical duplicate files after copying normalized files")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_bi_normalize_export)

    p = sub.add_parser("publish-bi", help="Publish a BI Studio project to a workspace")
    p.add_argument("--project-id", required=True)
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--workspace-password")
    p.add_argument("--python-version", default="auto")
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--interval", type=float, default=4.0)
    p.add_argument("--post-publish-timeout", type=float, default=180.0, help="Seconds to wait for the published workspace runtime to start cleanly")
    p.add_argument("--no-post-publish-check", action="store_true", help="Skip runtime/log validation after BI publish")
    p.add_argument("--allow-non-ascii-routes", action="store_true", help="Allow direct publish even when BI tab slugs contain accents/non-ASCII characters")
    p.set_defaults(func=cmd_publish_bi)

    p = sub.add_parser("echarts-template", help="Fetch an ECharts template from the tenant")
    p.add_argument("--template-id", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_echarts_template)

    p = sub.add_parser("users", help="List users")
    p.add_argument("--profile", help="Filter by profile")
    p.set_defaults(func=cmd_users)

    p = sub.add_parser("sectors", aliases=["setores"], help="List unique user sectors")
    p.set_defaults(func=cmd_sectors)

    p = sub.add_parser("permission-pages", help="List system/permissive pages used by permission screens")
    p.add_argument("--permissive", action="store_true", help="Use /permissive-pages instead of /pages")
    p.set_defaults(func=cmd_permission_pages)

    p = sub.add_parser("user-presence", help="List currently online users from the edit-users screen")
    p.set_defaults(func=cmd_user_presence)

    p = sub.add_parser("download-users", help="Download users report")
    p.add_argument("--output", required=True)
    p.add_argument("--profile")
    p.add_argument("--setor")
    p.add_argument("--search")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_download_users)

    p = sub.add_parser("download-permissions", help="Download permissions report")
    p.add_argument("--output", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_download_permissions)

    p = sub.add_parser("menu", help="Read current authenticated menu")
    p.set_defaults(func=cmd_menu)

    p = sub.add_parser("menu-maintenance", help="Check/reload/clear platform menu cache")
    p.add_argument("action", choices=["check-duplicates", "reload", "clear-cache"])
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_menu_maintenance)

    p = sub.add_parser("create-user", help="Create a user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--perfil", choices=["Administrador Principal", "Master", "Administrador", "Usuario", "Usuário", "Gestor"], default="Usuario")
    p.add_argument("--setor", default="Codex")
    p.add_argument("--matricula", default="")
    p.add_argument("--contato", default="")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("update-user", help="Edit a user profile")
    p.add_argument("--user", required=True, help="User id or email")
    p.add_argument("--name")
    p.add_argument("--perfil", choices=["Administrador Principal", "Master", "Administrador", "Usuario", "Usuário", "Gestor"])
    p.add_argument("--setor")
    p.add_argument("--matricula")
    p.add_argument("--contato")
    p.set_defaults(func=cmd_update_user)

    p = sub.add_parser("set-user-password", help="Set a user's password through the admin endpoint")
    p.add_argument("--user", required=True, help="User id or email")
    p.add_argument("--password")
    p.set_defaults(func=cmd_set_user_password)

    p = sub.add_parser("delete-user", help="Delete a user")
    p.add_argument("--user", required=True, help="User id or email")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_user)

    p = sub.add_parser("user-permissions", help="Read permissions for a user")
    p.add_argument("--user", required=True, help="User id or email")
    p.set_defaults(func=cmd_user_permissions)

    p = sub.add_parser("set-user-permissions", help="Replace direct/denied permissions for a user")
    p.add_argument("--user", required=True, help="User id or email")
    p.add_argument("--permissions", help="Comma-separated or JSON array permissions to allow")
    p.add_argument("--denied-permissions", help="Comma-separated or JSON array permissions to deny")
    p.add_argument("--permissions-file", help="JSON file with permissions and denied_permissions arrays")
    p.set_defaults(func=cmd_set_user_permissions)

    p = sub.add_parser("recalculate-permissions", help="Recalculate permissions for all users")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_recalculate_permissions)

    p = sub.add_parser("groups", help="List permission groups")
    p.set_defaults(func=cmd_groups)

    p = sub.add_parser("create-group", help="Create a permission group")
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--permissions", default="")
    p.add_argument("--color", default="#6c757d")
    p.set_defaults(func=cmd_create_group)

    p = sub.add_parser("update-group", help="Update a permission group")
    p.add_argument("--group", required=True, help="Group id or exact name")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--permissions")
    p.add_argument("--color")
    p.set_defaults(func=cmd_update_group)

    p = sub.add_parser("delete-group", help="Delete a permission group")
    p.add_argument("--group", required=True, help="Group id or exact name")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_group)

    p = sub.add_parser("assign-user-group", help="Add or remove a user from a permission group")
    p.add_argument("--user", required=True, help="User id or email")
    p.add_argument("--group", required=True, help="Group id or exact name")
    p.add_argument("--action", choices=["add", "remove"], default="add")
    p.set_defaults(func=cmd_assign_user_group)

    p = sub.add_parser("users-for-groups", help="List users for group management")
    p.set_defaults(func=cmd_users_for_groups)

    p = sub.add_parser("announcements", help="List internal announcements")
    p.add_argument("--active", action="store_true", help="List only active announcements")
    p.set_defaults(func=cmd_announcements)

    p = sub.add_parser("announcement-groups", help="List announcement target groups")
    p.set_defaults(func=cmd_announcement_groups)

    p = sub.add_parser("create-announcement", help="Create an internal announcement")
    p.add_argument("--title", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--priority", choices=["normal", "importante", "urgente"], default="normal")
    p.add_argument("--all", action="store_true", help="Send to all users")
    p.add_argument("--groups", default="", help="Comma-separated group ids/names when not sending to all")
    p.add_argument("--expires", help="Expiration datetime in ISO format")
    p.add_argument("--color")
    p.add_argument("--icon", default="fa-bullhorn")
    p.add_argument("--file", help="Optional attachment")
    p.set_defaults(func=cmd_create_announcement)

    p = sub.add_parser("delete-announcement", help="Delete an internal announcement")
    p.add_argument("--announcement-id", required=True)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_announcement)

    p = sub.add_parser("platform-config", help="Read platform branding/configuration")
    p.set_defaults(func=cmd_platform_config)

    p = sub.add_parser("colors-config", help="Read merged platform color configuration")
    p.set_defaults(func=cmd_colors_config)

    p = sub.add_parser("set-platform-config", help="Update platform branding/configuration")
    p.add_argument("--data-file", help="JSON file with platform config fields")
    p.add_argument("--browser-title")
    p.add_argument("--logo-width", type=int)
    p.add_argument("--logo-menu-width", type=int)
    p.add_argument("--colors-file", help="JSON file with colors payload")
    p.add_argument("--logo-image-file")
    p.add_argument("--icon-image-file")
    p.add_argument("--logo-menu-image-file")
    p.add_argument("--remove-logo", action="store_true")
    p.add_argument("--remove-icon", action="store_true")
    p.add_argument("--remove-logo-menu", action="store_true")
    p.set_defaults(func=cmd_set_platform_config)

    p = sub.add_parser("export-platform-config", help="Export platform branding/configuration to JSON")
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_platform_config)

    p = sub.add_parser("backup-platform-branding", help="Backup current platform title, logos, favicon, and colors")
    p.add_argument("--output", help="Backup JSON output. Defaults to Downloads\\plugin\\branding-backups")
    p.set_defaults(func=cmd_backup_platform_branding)

    p = sub.add_parser("platform-title", help="Read or update the Rejoin BI platform browser title")
    p.add_argument("--title", help="New browser title. Omit to read the current title.")
    p.add_argument("--backup-output", help="Where to save the automatic pre-change backup")
    p.set_defaults(func=cmd_platform_title)

    p = sub.add_parser("set-platform-branding", help="Update platform title, logos, favicon, and colors with automatic backup")
    p.add_argument("--backup-output", help="Where to save the automatic pre-change backup")
    p.add_argument("--data-file", help="JSON file with platform branding/config fields")
    p.add_argument("--browser-title")
    p.add_argument("--logo-width", type=int)
    p.add_argument("--logo-menu-width", type=int)
    p.add_argument("--colors-file", help="JSON file with colors payload")
    p.add_argument("--logo-image-file")
    p.add_argument("--logo-menu-image-file")
    p.add_argument("--favicon-image-file", help="Favicon/image file. Alias for icon_image.")
    p.add_argument("--icon-image-file", help="Icon/favicon image file.")
    p.add_argument("--remove-logo", action="store_true")
    p.add_argument("--remove-logo-menu", action="store_true")
    p.add_argument("--remove-favicon", action="store_true")
    p.add_argument("--remove-icon", action="store_true")
    p.set_defaults(func=cmd_set_platform_branding)

    p = sub.add_parser("restore-platform-branding", help="Restore title, logos, favicon, and colors from a backup")
    p.add_argument("--backup", required=True, help="Backup JSON from backup-platform-branding, set-platform-branding, or export-platform-config")
    p.add_argument("--backup-output", help="Where to save the current config before restoring")
    p.add_argument("--no-pre-restore-backup", action="store_true", help="Do not save current config before restoring")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_restore_platform_branding)

    p = sub.add_parser("restore-platform-config-defaults", help="Restore default platform colors")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_restore_platform_config_defaults)

    p = sub.add_parser("ai-config", help="Read AI page configuration")
    p.add_argument("--page-id", required=True)
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--container-id")
    p.add_argument("--config-id")
    p.set_defaults(func=cmd_ai_config_get)

    p = sub.add_parser("set-ai-config", help="Create or update AI page configuration")
    p.add_argument("--data-file", help="JSON file with AI config fields")
    p.add_argument("--page-id")
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--container-id")
    p.add_argument("--business-context")
    p.add_argument("--title")
    p.add_argument("--metrics")
    p.add_argument("--objectives")
    p.add_argument("--glossary")
    p.add_argument("--alerts")
    p.add_argument("--benchmarks")
    p.add_argument("--historical-insights")
    p.add_argument("--analysis-priority", choices=["rapida", "balanceada", "profunda"])
    p.add_argument("--detail-level", choices=["operacional", "executivo", "tecnico"])
    p.add_argument("--recommendation-focus", choices=["curto_prazo", "medio_prazo", "longo_prazo"])
    p.add_argument("--forced-key-id")
    p.add_argument("--forced-key-name")
    p.add_argument("--forced-key-model")
    p.add_argument("--forced-reasoning-effort")
    p.add_argument("--forced-service-tier")
    p.add_argument("--page-name")
    p.add_argument("--full-path")
    p.add_argument("--active", dest="active", action="store_true")
    p.add_argument("--inactive", dest="active", action="store_false")
    p.set_defaults(func=cmd_ai_config_set, active=None)

    p = sub.add_parser("delete-ai-config", help="Delete AI page configuration")
    p.add_argument("--page-id", required=True)
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--container-id")
    p.add_argument("--config-id")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_ai_config_delete)

    p = sub.add_parser("cleanup-ai-config", help="Remove orphan AI configs")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_ai_config_cleanup)

    p = sub.add_parser("storage-path", help="Read or update platform storage path")
    p.add_argument("--path", help="New storage path. Omit to read current value")
    p.set_defaults(func=cmd_storage_path)

    p = sub.add_parser("audit", help="Read audit logs, dashboard, health, detail, or clean old logs")
    p.add_argument("action", choices=["logs", "dashboard", "health", "log", "cleanup"])
    p.add_argument("--log-id")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--per-page", type=int, default=20)
    p.add_argument("--date-from")
    p.add_argument("--date-to")
    p.add_argument("--action-type")
    p.add_argument("--user-email")
    p.add_argument("--level")
    p.add_argument("--days-to-keep", type=int, default=90)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("audit-export", help="Download audit logs")
    p.add_argument("--output", required=True)
    p.add_argument("--format", choices=["xlsx", "csv", "json"], default="xlsx")
    p.add_argument("--date-from")
    p.add_argument("--date-to")
    p.add_argument("--action-type")
    p.add_argument("--user-email")
    p.add_argument("--level")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_audit_export)

    p = sub.add_parser("sleep-manager", help="Manage system sleep/shutdown configuration")
    p.add_argument("action", choices=[
        "status", "config", "configs", "metrics", "history", "users-online", "shutdown-warning",
        "create-config", "set-config", "update-config", "activate", "toggle", "delete-config",
        "force-sleep", "force-active", "force-logout-all",
    ])
    p.add_argument("--config-id")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_sleep_manager)

    p = sub.add_parser("email", help="Manage e-mail sessions, groups, contacts, schedules, and sends")
    p.add_argument("action", choices=[
        "history", "queue-status", "sessions", "create-session", "test-session", "update-session", "delete-session",
        "groups", "create-group", "update-group", "delete-group", "recipients", "add-recipient", "delete-recipient",
        "external-contacts", "create-external-contact", "delete-external-contact",
        "schedules", "create-schedule", "delete-schedule", "broadcast", "cancel-history",
    ])
    p.add_argument("--session-id")
    p.add_argument("--group-id")
    p.add_argument("--recipient-id")
    p.add_argument("--contact-id")
    p.add_argument("--schedule-id")
    p.add_argument("--history-id")
    p.add_argument("--page-id")
    p.add_argument("--limit", type=int)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_email_manager)

    p = sub.add_parser("whatsapp", help="Manage WhatsApp sessions, groups, contacts, schedules, and sends")
    p.add_argument("action", choices=[
        "history", "queue-status", "diagnostics", "sessions", "start-session", "stop-session", "session-groups",
        "groups", "create-group", "update-group", "delete-group", "recipients", "add-recipient", "delete-recipient",
        "external-contacts", "create-external-contact", "delete-external-contact",
        "schedules", "create-schedule", "delete-schedule", "broadcast", "cancel-history", "restart-service",
    ])
    p.add_argument("--session-name")
    p.add_argument("--group-id")
    p.add_argument("--recipient-id")
    p.add_argument("--contact-id")
    p.add_argument("--schedule-id")
    p.add_argument("--history-id")
    p.add_argument("--limit", type=int)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_whatsapp_manager)

    p = sub.add_parser("codex-keys", help="Manage Codex/AI provider connections and usage")
    p.add_argument("action", choices=[
        "stats", "active", "list", "auth-status", "auth-login",
        "create", "get", "unlock", "update", "delete", "user-delete",
        "usage", "users",
    ])
    p.add_argument("--key-id")
    p.add_argument("--provider-id")
    p.add_argument("--page", type=int)
    p.add_argument("--limit", type=int)
    p.add_argument("--days", type=int)
    p.add_argument("--user-email")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_codex_keys)

    p = sub.add_parser("route-map", help="Inspect or refresh dynamic route mapping")
    p.add_argument("action", choices=["routes", "route", "uploads", "scan", "clear"])
    p.add_argument("--route-name")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_route_map)

    p = sub.add_parser("system-admin", help="Inspect or operate platform runtime/system endpoints")
    p.add_argument("action", choices=[
        "auto-stress-start", "auto-stress-results", "database-status", "subscription-status",
        "clear-dynamic-cache", "dynamic-apps-monitoring", "check-work-status", "dynamic-pages",
        "init-status", "restart-dynamics", "dynamic-status", "public-ready", "runtime-readiness",
        "runtime-build-info", "file-recognition", "test-url-rewriting", "active-container",
        "force-reload", "clear-all-caches", "middleware-status", "middleware-cleanup",
    ])
    p.add_argument("--query", action="append", help="Query parameter as key=value; can be repeated")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_system_admin)

    p = sub.add_parser("upload-admin", help="Inspect upload capabilities, gateway pairing, and upload state")
    p.add_argument("action", choices=[
        "python-versions", "capabilities", "gateway-download-client", "gateway-pairings",
        "gateway-generate-pairing-code", "gateway-delete-pairing", "gateway-pause-pairing",
        "gateway-confirm-access", "gateway-confirm-link", "gateway-bootstrap",
        "gateway-delete-item", "upload-status", "clear-dynamic-data",
    ])
    p.add_argument("--pairing-id")
    p.add_argument("--process-id")
    p.add_argument("--output")
    p.add_argument("--query", action="append", help="Query parameter as key=value; can be repeated")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_upload_admin)

    p = sub.add_parser("data-engine", help="Manage Data Engine DB connections, repository, datasets, notebook, and terminal")
    p.add_argument("action", choices=[
        "inventory", "status", "session-status", "db-connections", "create-db-connection", "db-connection",
        "update-db-connection", "delete-db-connection", "test-db-connection", "sqlserver-drivers",
        "db-objects", "query", "query-preview", "query-materialize", "query-materialize-saved",
        "query-run", "ai-sql-query", "repository-list", "repository-content",
        "repository-inspect-sheets", "repository-upload",
        "repository-global-context", "repository-execute-global-context",
        "repository-manual-table", "create-manual-table", "create-folder", "move", "order",
        "delete", "datasets-list", "create-dataset", "duplicate-dataset", "delete-dataset",
        "link-dataset", "unlink-dataset", "list-files", "preview-file", "dataset-get",
        "save-column-types", "save-notebook-state", "finalize-dataset", "toggle-visibility",
        "execute-code", "agent-mine", "chat", "load-chat", "cancel-execution",
        "reset-session", "remove-variable", "terminal-command", "terminal-auto-install",
    ])
    p.add_argument("--connection-id")
    p.add_argument("--query-id")
    p.add_argument("--run-id")
    p.add_argument("--project-id", help="Data Engine project id for project-scoped endpoints")
    p.add_argument("--project-uid", help="Data Engine project uid for project-scoped endpoints")
    p.add_argument("--file", help="Data Engine repository upload/inspect file path")
    p.add_argument("--folder", help="Data Engine repository target folder")
    p.add_argument("--selected-sheet", action="append", help="Excel sheet to upload; repeat for multiple sheets")
    p.add_argument("--sheet-states", help="JSON file with Data Engine sheet state metadata")
    p.add_argument("--csv-separator", help="CSV separator hint, for example ',' or ';'")
    p.add_argument("--allow-sensitive-files", action="store_true", help="Allow Data Engine upload/inspect of sensitive-looking files after manual review")
    p.add_argument("--limit", type=int, default=25, help="Inventory summary item limit")
    p.add_argument("--include-raw", action="store_true", help="Inventory only: include sanitized raw endpoint payloads")
    p.add_argument("--include-global-context", action="store_true", default=True)
    p.add_argument("--no-global-context", dest="include_global_context", action="store_false")
    p.add_argument("--include-sessions", action="store_true", default=True)
    p.add_argument("--no-sessions", dest="include_sessions", action="store_false")
    p.add_argument("--include-files", action="store_true", default=True)
    p.add_argument("--no-files", dest="include_files", action="store_false")
    p.add_argument("--output", help="Inventory only: optional JSON report path")
    p.add_argument("--query", action="append", help="Query parameter as key=value; can be repeated")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_data_engine)

    p = sub.add_parser("pages", help="List platform pages")
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--all-containers", action="store_true")
    p.add_argument("--include-inactive", action="store_true")
    p.add_argument("--exclude-fictitious", action="store_true")
    p.set_defaults(func=cmd_pages)

    p = sub.add_parser("page-files", help="List files available for page binding")
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--container-id")
    p.set_defaults(func=cmd_page_files)

    p = sub.add_parser("page-maintenance", help="Check or repair page configuration integrity")
    p.add_argument("action", choices=[
        "verify-orphan-permissions", "clear-orphan-permissions",
        "verify-conflicts", "fix-conflicts",
        "verify-hierarchy", "fix-hierarchy",
        "clear-fictitious-orphans", "clear-rls-cache",
    ])
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_page_maintenance)

    p = sub.add_parser("set-page-order", help="Update page order/parent placement")
    p.add_argument("--page-id", required=True)
    p.add_argument("--position", type=int)
    p.add_argument("--parent")
    p.add_argument("--before")
    p.add_argument("--after")
    add_payload_args(p)
    p.set_defaults(func=cmd_set_page_order)

    p = sub.add_parser("accessible-pages", help="List pages visible to the current session")
    p.set_defaults(func=cmd_accessible_pages)

    p = sub.add_parser("create-page", help="Create a page linked to a workspace")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--name", required=True)
    p.add_argument("--file", default="")
    p.add_argument("--route", default="")
    p.add_argument("--icon", default="fas fa-chart-line")
    p.add_argument("--description", default="")
    p.add_argument("--parent", default="")
    p.add_argument("--inactive", action="store_true")
    p.add_argument("--rls", action="store_true")
    p.add_argument("--workspace-password")
    p.set_defaults(func=cmd_create_page)

    p = sub.add_parser("update-page", help="Update a platform page")
    p.add_argument("--page-id", required=True)
    p.add_argument("--workspace", help="Move/rebind to workspace id or name")
    p.add_argument("--name")
    p.add_argument("--file")
    p.add_argument("--route")
    p.add_argument("--icon")
    p.add_argument("--description")
    p.add_argument("--parent")
    p.add_argument("--active", action="store_true")
    p.add_argument("--inactive", action="store_true")
    p.add_argument("--rls", action="store_true")
    p.add_argument("--no-rls", action="store_true")
    p.add_argument("--workspace-password")
    p.set_defaults(func=cmd_update_page)

    p = sub.add_parser("delete-page", help="Delete a platform page")
    p.add_argument("--page-id", required=True)
    p.add_argument("--confirm-page-id", help="Required with --yes. Must exactly match the resolved page id.")
    p.add_argument("--cascade", action="store_true", help="Allow deleting descendants shown in the plan")
    p.add_argument("--allow-linked-pages", action="store_true", help="Allow deletion when extra hierarchy/reference links are present")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--missing-ok", action="store_true")
    p.set_defaults(func=cmd_delete_page)

    p = sub.add_parser("resolve-page", help="Resolve a page id or route to a tenant URL")
    p.add_argument("--page-ref", required=True)
    p.set_defaults(func=cmd_resolve_page)

    p = sub.add_parser("rls", help="Manage RLS pages, configs, data, dimensions, and validation")
    p.add_argument("action", choices=[
        "pages", "page-config", "page-info", "config", "data", "dimensions", "values", "validate",
        "set-config", "set-page-mapping", "delete-config", "create-data", "update-data", "delete-data",
        "create-dimension", "update-dimension", "delete-dimension",
        "scan-columns", "fetch-columns", "test-config",
    ])
    p.add_argument("--page-id")
    p.add_argument("--page-rls-id")
    p.add_argument("--container-id")
    p.add_argument("--user-id")
    p.add_argument("--rls-id")
    p.add_argument("--dimension-id")
    p.add_argument("--column")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    add_payload_args(p)
    p.set_defaults(func=cmd_rls)

    p = sub.add_parser("rls-export", help="Download RLS export")
    p.add_argument("--output", required=True)
    p.add_argument("--format", default="xlsx")
    p.add_argument("--page-id")
    p.add_argument("--user-id")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_rls_export)

    p = sub.add_parser("deploy-manifest", help="Create/validate workspace, upload an app folder, and create all pages from a manifest")
    p.add_argument("--manifest", required=True)
    p.add_argument("--path", help="App root folder. Defaults to manifest folder or manifest.app_root.")
    p.add_argument("--workspace", help="Workspace id/name override")
    p.add_argument("--workspace-password")
    p.add_argument("--create-workspace", action="store_true")
    p.add_argument("--replace-pages", action="store_true")
    p.add_argument("--skip-upload", action="store_true")
    p.add_argument("--startup-mode", choices=["file", "command", "static"])
    p.add_argument("--selected-file", default="")
    p.add_argument("--startup-command", default="")
    p.add_argument("--python-path", default="auto")
    p.add_argument("--no-auto-start", action="store_true")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--readiness-timeout", type=float, default=300.0, help="Seconds to wait for accessible-pages to expose container_name for every page")
    p.add_argument("--no-page-readiness", action="store_true", help="Skip post-deploy accessible-pages/menu safety verification")
    p.set_defaults(func=cmd_deploy_manifest)

    p = sub.add_parser("smoke-pages", help="Resolve and request every page in a manifest using the authenticated session")
    p.add_argument("--manifest", required=True)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--readiness-timeout", type=float, default=120.0, help="Seconds to wait for accessible-pages container_name readiness")
    p.add_argument("--interval", type=float, default=1.5)
    p.add_argument("--no-refresh-menu", action="store_true", help="Do not clear/reload menu cache while waiting")
    p.set_defaults(func=cmd_smoke_pages)

    p = sub.add_parser("smoke-admin", help="Run a read-only admin API smoke test across tenant configuration areas")
    p.add_argument("--output-dir", help="Optional folder to write smoke-admin.json")
    p.add_argument("--strict", action="store_true", help="Fail when optional diagnostics are blocked or unavailable")
    p.add_argument("--timeout", type=int, default=60)
    p.set_defaults(func=cmd_smoke_admin)

    p = sub.add_parser("validate-app", help="Check a dashboard folder/manifest against Rejoin BI workspace compatibility rules")
    p.add_argument("--manifest")
    p.add_argument("--path")
    p.add_argument("--startup-mode", choices=["file", "command", "static"])
    p.add_argument("--selected-file", default="")
    p.add_argument("--startup-command", default="")
    p.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    p.set_defaults(func=cmd_validate_app)

    p = sub.add_parser("export-package", help="Copy this plugin to Downloads\\plugin for sharing and create a zip package")
    p.add_argument("--destination", help="Destination folder. Defaults to %%USERPROFILE%%\\Downloads\\plugin")
    p.add_argument("--clean", action="store_true", help="Remove the existing destination package folder before copying")
    p.add_argument("--no-zip", action="store_true", help="Do not create rejoinbi-platform.zip")
    p.set_defaults(func=cmd_export_package)

    p = sub.add_parser("api-get", help="Run an authenticated GET against a platform API path")
    p.add_argument("--path", required=True)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_api_get)

    p = sub.add_parser("api-send", help="Run an authenticated JSON request against a platform API path")
    p.add_argument("--path", required=True)
    p.add_argument("--method", choices=["POST", "PUT", "PATCH", "DELETE"], default="POST")
    p.add_argument("--data-json")
    p.add_argument("--data-file")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--yes", action="store_true", help="Confirm the raw API mutation after manual review")
    p.set_defaults(func=cmd_api_post)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except RejoinBIError as exc:
        error = str(exc)
        payload: dict[str, Any] = {"success": False, "error": error}
        lower_error = error.lower()
        if (
            "401" in error
            or "sessao" in lower_error
            or "sessão" in lower_error
            or "session expired" in lower_error
            or "no saved session" in lower_error
            or "login required" in lower_error
        ):
            try:
                base_url = resolve_base_url(
                    subdomain=getattr(args, "tenant", "") or getattr(args, "subdomain", "") or "",
                    domain=getattr(args, "domain", DEFAULT_DOMAIN) or DEFAULT_DOMAIN,
                    base_url=getattr(args, "base_url", "") or "",
                )
                payload["reauth_command"] = f"python scripts/rejoinbi.py --tenant {tenant_host_from_base_url(base_url)} ensure"
            except Exception:
                payload["reauth_command"] = "python scripts/rejoinbi.py --tenant subdomain.rejoinbi.com.br ensure"
            payload["reauth_note"] = "Run ensure with the full tenant host to verify the session or open the browser auth wizard."
        print_payload(payload)
        return 1
    except KeyboardInterrupt:
        print_payload({"success": False, "error": "Interrupted"})
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
