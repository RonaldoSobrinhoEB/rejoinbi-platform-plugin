#!/usr/bin/env python3
"""Rejoin BI Platform helper CLI.

This client talks to the existing Flask API exposed by Rejoin BI tenants.
It stores cookies after login but never persists passwords or PIN values.
"""

from __future__ import annotations

import argparse
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
from contextlib import ExitStack
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse
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


class RejoinBIError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_base_url(value: str) -> str:
    raw = str(value or "").strip().strip('"').strip("'")
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise RejoinBIError(f"Invalid base URL: {value}")
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


def session_slug(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    return re.sub(r"[^a-z0-9_.-]+", "_", host).strip("_") or "default"


def print_payload(payload: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(str(payload))


def as_bool_flag(value: bool) -> str:
    return "yes" if value else "no"


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
            self.session.cookies.update(cookies)

    def save_session(self) -> None:
        payload = {
            "base_url": self.base_url,
            "cookies": requests.utils.dict_from_cookiejar(self.session.cookies),
            "saved_at": utc_now(),
        }
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
            return path
        return self.base_url + "/" + path.lstrip("/")

    def request(self, method: str, path: str, *, timeout: int = DEFAULT_TIMEOUT, **kwargs: Any) -> tuple[Any, requests.Response]:
        try:
            response = self.session.request(method, self.url(path), timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise RejoinBIError(f"{method} {path} failed before response: {exc}") from exc
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
    error_block = f'<div class="error">{html.escape(error)}</div>' if error else ""
    if require_pin:
        form = f"""
        <form method="post" action="/pin">
          <input type="hidden" name="state" value="{safe_state}">
          <label>PIN de seguranca</label>
          <input name="pin" inputmode="numeric" autocomplete="one-time-code" autofocus required>
          <button type="submit">Concluir conexao</button>
        </form>
        """
    else:
        form = f"""
        <form method="post" action="/login">
          <input type="hidden" name="state" value="{safe_state}">
          <label>Email</label>
          <input name="email" type="email" value="{safe_email}" autocomplete="username" autofocus required>
          <label>Senha</label>
          <input name="password" type="password" autocomplete="current-password" required>
          <button type="submit">Conectar Rejoin BI</button>
        </form>
        """
    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b1115;
      color: #eef6f4;
    }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, .22), transparent 32rem),
        linear-gradient(135deg, #0b1115 0%, #101820 58%, #151615 100%);
    }}
    main {{
      width: min(440px, calc(100vw - 32px));
      border: 1px solid rgba(255, 255, 255, .12);
      border-radius: 18px;
      background: rgba(16, 24, 32, .92);
      box-shadow: 0 24px 72px rgba(0, 0, 0, .38);
      padding: 28px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #90f2df;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .badge::before {{
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #22c55e;
      box-shadow: 0 0 20px rgba(34, 197, 94, .8);
    }}
    h1 {{
      margin: 18px 0 8px;
      font-size: 28px;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    p {{
      margin: 0 0 18px;
      color: #adc0bd;
      line-height: 1.55;
    }}
    .tenant {{
      margin: 18px 0;
      padding: 12px 14px;
      border-radius: 12px;
      background: rgba(255, 255, 255, .06);
      color: #d7fffa;
      overflow-wrap: anywhere;
      font-size: 14px;
    }}
    form {{
      display: grid;
      gap: 12px;
    }}
    label {{
      color: #d6e4e1;
      font-size: 13px;
      font-weight: 700;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      min-height: 46px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, .14);
      background: rgba(255, 255, 255, .08);
      color: #fff;
      padding: 0 13px;
      font: inherit;
      outline: none;
    }}
    input:focus {{
      border-color: #2dd4bf;
      box-shadow: 0 0 0 3px rgba(45, 212, 191, .16);
    }}
    button {{
      margin-top: 4px;
      min-height: 48px;
      border: 0;
      border-radius: 10px;
      background: #14b8a6;
      color: #03110f;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }}
    .error {{
      margin: 0 0 14px;
      padding: 12px;
      border-radius: 10px;
      background: rgba(239, 68, 68, .12);
      color: #fecaca;
    }}
    .success {{
      padding: 14px;
      border-radius: 12px;
      background: rgba(34, 197, 94, .12);
      color: #d9fbe8;
    }}
    a {{
      color: #67e8f9;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <div class="badge">Rejoin BI</div>
    <h1>{safe_title}</h1>
    <p>{html.escape(body)}</p>
    <div class="tenant">{safe_base_url}</div>
    {error_block}
    {form}
  </main>
</body>
</html>"""
    return page.encode("utf-8")


def success_html(base_url: str, email: str, profile: str) -> bytes:
    safe_base_url = html.escape(base_url)
    safe_email = html.escape(email)
    safe_profile = html.escape(profile or "perfil validado")
    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rejoin BI conectado</title>
  <style>
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      background: #0b1115;
      color: #eef6f4;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(460px, calc(100vw - 32px));
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, .12);
      background: #101820;
      padding: 28px;
      box-shadow: 0 24px 72px rgba(0, 0, 0, .38);
    }}
    h1 {{ margin: 0 0 10px; font-size: 28px; letter-spacing: 0; }}
    p {{ margin: 0 0 14px; color: #adc0bd; line-height: 1.55; }}
    .success {{
      margin-bottom: 16px;
      padding: 14px;
      border-radius: 12px;
      background: rgba(34, 197, 94, .12);
      color: #d9fbe8;
    }}
    a {{ color: #67e8f9; font-weight: 800; }}
  </style>
</head>
<body>
  <main>
    <div class="success">Sessao do plugin salva com seguranca.</div>
    <h1>Conectado</h1>
    <p>{safe_email} foi validado como {safe_profile}. Voce ja pode voltar ao Codex e pedir workspaces, paginas, uploads e dashboards.</p>
    <p>Tenant: <a href="{safe_base_url}/plataforma" target="_blank" rel="noreferrer">{safe_base_url}</a></p>
  </main>
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

        def finish_success(self, data: Any, email: str) -> None:
            try:
                identity = require_allowed_profile(client, args)
                client.save_session()
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
                    if isinstance(data, dict) and data.get("require_pin"):
                        pending.clear()
                        pending.update(payload)
                        self.render_pin(data.get("message") or "")
                        return
                    if isinstance(data, dict) and data.get("success"):
                        self.finish_success(data, email)
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
                        self.finish_success(data, pending.get("email", ""))
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


def extract_session_identity(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"email": "", "profile": "", "permissions": []}
    session_data = payload.get("session_data") if isinstance(payload.get("session_data"), dict) else {}
    permissions = payload.get("user_permissions") or session_data.get("user_permissions") or []
    if isinstance(permissions, str):
        permissions = [p.strip() for p in permissions.split(",") if p.strip()]
    if not isinstance(permissions, list):
        permissions = []
    profile = payload.get("user_perfil") or payload.get("perfil") or session_data.get("user_perfil") or session_data.get("perfil") or ""
    if not profile and ("*" in permissions or "admin_principal" in permissions):
        profile = "Administrador Principal"
    return {
        "email": payload.get("user_email") or session_data.get("user_email") or "",
        "profile": profile,
        "permissions": permissions,
        "logged_in": bool(payload.get("logged_in", True) or session_data.get("user_email")),
    }


def is_allowed_identity(identity: dict[str, Any]) -> bool:
    profile_key = normalize_text(identity.get("profile"))
    permissions = [normalize_text(item) for item in identity.get("permissions") or []]
    return profile_key in ALLOWED_PROFILE_KEYS or "*" in permissions or "admin_principal" in permissions


def require_allowed_profile(client: RejoinBIClient, args: argparse.Namespace) -> dict[str, Any]:
    data, _ = client.request("GET", "/plataforma/api/session-status", timeout=30)
    identity = extract_session_identity(data)
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

    if isinstance(data, dict) and data.get("require_pin"):
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
            identity = require_allowed_profile(client, args)
        except RejoinBIError:
            client.clear_session()
            raise
        client.save_session()
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
    identity = extract_session_identity(data)
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
            "locked": bool(workspace.get("has_password") or workspace.get("password")),
            "status": workspace.get("deploy_status") or "",
        },
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
                "locked": as_bool_flag(bool(item.get("has_password"))),
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


def open_upload_files(paths: list[str], stack: ExitStack) -> list[tuple[str, tuple[str, Any, str]]]:
    result = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise RejoinBIError(f"File not found: {path}")
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
        files = open_upload_files(args.files, stack)
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


def iter_folder_files(root: Path, exclude_names: set[str]) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts.intersection(exclude_names):
            continue
        files.append(path)
    return files


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
        for path in iter_folder_files(root, exclude):
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
    client.download(f"/plataforma/api/bi/projects/{args.project_id}/export{params}", output, timeout=args.timeout)
    print_payload({"success": True, "output": str(output)}, as_json=args.json)
    return 0


def poll_publish(client: RejoinBIClient, project_id: str, job_id: str, timeout: int, interval: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        time.sleep(interval)
        data, _ = client.request("GET", f"/plataforma/api/bi/projects/{project_id}/internal-publish/status/{job_id}", timeout=60)
        last = data if isinstance(data, dict) else {"raw": data}
        if last.get("done") or str(last.get("status") or "").lower() in {"success", "error", "cancelled"}:
            return last
    raise RejoinBIError(f"Publish polling timed out. Last status: {last}")


def cmd_publish_bi(args: argparse.Namespace) -> int:
    client = make_client(args)
    workspace = resolve_workspace(client, args.workspace)
    password = args.workspace_password or os.environ.get("REJOINBI_WORKSPACE_PASSWORD") or ""
    payload = {
        "container_id": workspace.get("id"),
        "password": password,
        "python_version": args.python_version or "auto",
    }
    data, _ = client.request(
        "POST",
        f"/plataforma/api/bi/projects/{args.project_id}/internal-publish/start",
        json=payload,
        timeout=60,
    )
    result = data if isinstance(data, dict) else {"raw": data}
    if result.get("job_id"):
        final = poll_publish(client, args.project_id, result["job_id"], args.timeout, args.interval)
        result = {"initial_response": result, "final_response": final, "success": bool(final.get("success"))}
    print_payload(result, as_json=args.json)
    return 0


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
    if args.dry_run or not args.yes:
        print_payload({
            "success": True,
            "dry_run": True,
            "message": "No deletion performed. Re-run with --yes, --confirm-name, and optional --confirm-id to delete.",
            "plan": plan,
        }, as_json=args.json)
        return 0

    errors: list[str] = []
    if safe_str(args.confirm_name) != workspace_name:
        errors.append(f"--confirm-name must exactly match resolved workspace name: {workspace_name}")
    if args.confirm_id and safe_str(args.confirm_id) != workspace_id:
        errors.append(f"--confirm-id must exactly match resolved workspace id: {workspace_id}")
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
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RejoinBIError("Manifest must contain a JSON object.")
    return payload, manifest_path


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


def create_page_from_manifest(
    client: RejoinBIClient,
    workspace: dict[str, Any],
    page: dict[str, Any],
    *,
    workspace_password: str = "",
    replace: bool = False,
) -> dict[str, Any]:
    payload = page_payload_from_manifest(page, workspace, workspace_password)
    page_id_hint = page.get("id") or page.get("page_id") or payload.get("rota") or payload.get("nome")
    if replace and page_id_hint:
        delete_page(client, str(page_id_hint), missing_ok=True)
    data, _ = client.request("POST", "/plataforma/api/paginas", json=payload, timeout=60)
    result = data if isinstance(data, dict) else {"raw": data}
    page_ref = result.get("page_id") or payload.get("rota") or page_id_hint
    if page_ref:
        try:
            resolved, _ = client.request("GET", f"/plataforma/api/capture/resolve-page/{quote(str(page_ref), safe='-_/')}", timeout=60)
            result["resolved"] = resolved
        except RejoinBIError as exc:
            result["resolve_error"] = str(exc)
    return result


def cmd_deploy_manifest(args: argparse.Namespace) -> int:
    client = make_client(args)
    manifest, manifest_path = load_manifest(args.manifest)
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

    print_payload({
        "success": True,
        "manifest": str(manifest_path),
        "app_root": str(app_root),
        "workspace": {"id": workspace.get("id"), "name": workspace.get("name"), "status": workspace.get("deploy_status")},
        "workspace_validation": validation,
        "upload": upload_result,
        "pages": page_results,
        "count": len(page_results),
    }, as_json=args.json)
    return 0


def cmd_smoke_pages(args: argparse.Namespace) -> int:
    client = make_client(args)
    manifest, manifest_path = load_manifest(args.manifest)
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
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
            status_code = response.status_code
            expected = page.get("expect_text") or page.get("name") or ""
            html_ok = response.ok and (not expected or str(expected) in response.text)
        results.append({
            "page_ref": page_ref,
            "resolved": resolved,
            "status_code": status_code,
            "html_ok": html_ok,
        })
    print_payload({
        "success": all(item.get("html_ok") for item in results),
        "manifest": str(manifest_path),
        "results": results,
        "count": len(results),
    }, as_json=args.json)
    return 0


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
        if route.startswith("/api/") or route in {"/", "/health", "/status"}:
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

    if pages:
        files_by_page = []
        seen_routes = set()
        seen_ids = set()
        for page in pages:
            if not isinstance(page, dict):
                errors.append(f"Invalid manifest page entry: {page}")
                continue
            page_id = str(page.get("id") or page.get("page_id") or "").strip()
            route = str(page.get("route") or page.get("rota") or "").strip()
            file_name = str(page.get("file") or page.get("arquivo") or "").strip()
            if not page_id:
                errors.append(f"Page missing id/page_id: {page}")
            elif page_id in seen_ids:
                errors.append(f"Duplicate page id: {page_id}")
            seen_ids.add(page_id)
            if not route:
                warnings.append(f"Page {page_id or page.get('name')} has no custom route; Gerenciar Paginas will fall back to file route.")
            elif route in seen_routes:
                errors.append(f"Duplicate page route: {route}")
            seen_routes.add(route)
            if not file_name:
                errors.append(f"Page {page_id or route} has no HTML file.")
                continue
            page_file = (app_root / file_name).resolve()
            if not str(page_file).startswith(str(app_root)):
                errors.append(f"Page file escapes app root: {file_name}")
                continue
            if not page_file.exists():
                errors.append(f"Page file not found: {file_name}")
            elif page_file.suffix.lower() != ".html":
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
        return json.loads(Path(args.data_file).expanduser().read_text(encoding="utf-8"))
    raw = getattr(args, "data_json", None)
    if raw:
        return json.loads(raw)
    return {}


def cmd_api_get(args: argparse.Namespace) -> int:
    client = make_client(args)
    data, _ = client.request("GET", args.path, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def cmd_api_post(args: argparse.Namespace) -> int:
    client = make_client(args)
    payload = parse_json_payload(args)
    data, _ = client.request(args.method.upper(), args.path, json=payload, timeout=args.timeout)
    print_payload(data, as_json=args.json)
    return 0


def should_ignore_export(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    ignored_names = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "__pycache__",
        "artifacts",
    }
    for name in names:
        lower = name.lower()
        if name in ignored_names or lower.endswith((".pyc", ".pyo", ".zip")):
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
python .\\rejoinbi-platform\\scripts\\rejoinbi.py delete-workspace --workspace codex-suite
python .\\rejoinbi-platform\\scripts\\rejoinbi.py delete-page --page-id codex-suite-overview
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
    parser.add_argument("--json", action="store_true", default=True, help="Print JSON output")
    parser.add_argument(
        "--allow-standard",
        action="store_true",
        help="Allow non-admin profiles for negative tests. By default only admin/principal/master sessions are accepted.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

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

    p = sub.add_parser("delete-workspace", aliases=["workspace-delete"], help="Preview and safely delete one workspace/container")
    p.add_argument("--workspace", required=True, help="Workspace id or exact name")
    p.add_argument("--confirm-name", help="Required with --yes. Must exactly match the resolved workspace name.")
    p.add_argument("--confirm-id", help="Optional extra guard. Must exactly match the resolved workspace id.")
    p.add_argument("--yes", action="store_true", help="Actually delete after all guards pass")
    p.add_argument("--dry-run", action="store_true", help="Only show the deletion plan")
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

    p = sub.add_parser("upload-files", help="Upload individual files directly into a workspace app folder")
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--folder", default="")
    p.add_argument("--message")
    p.add_argument("--map", action="append", help="filename=target/folder mapping")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--workspace-password")
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

    p = sub.add_parser("bi-create-project", help="Create a BI Studio project")
    p.add_argument("--name", required=True)
    p.add_argument("--password")
    p.set_defaults(func=cmd_bi_create_project)

    p = sub.add_parser("bi-export", help="Export a BI Studio project ZIP")
    p.add_argument("--project-id", required=True)
    p.add_argument("--output")
    p.add_argument("--project-password")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=cmd_bi_export)

    p = sub.add_parser("publish-bi", help="Publish a BI Studio project to a workspace")
    p.add_argument("--project-id", required=True)
    p.add_argument("--workspace", required=True, help="Workspace id or name")
    p.add_argument("--workspace-password")
    p.add_argument("--python-version", default="auto")
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--interval", type=float, default=4.0)
    p.set_defaults(func=cmd_publish_bi)

    p = sub.add_parser("echarts-template", help="Fetch an ECharts template from the tenant")
    p.add_argument("--template-id", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_echarts_template)

    p = sub.add_parser("users", help="List users")
    p.add_argument("--profile", help="Filter by profile")
    p.set_defaults(func=cmd_users)

    p = sub.add_parser("create-user", help="Create a user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--perfil", choices=["Administrador Principal", "Master", "Administrador", "Usuario", "Usuário", "Gestor"], default="Usuario")
    p.add_argument("--setor", default="Codex")
    p.add_argument("--matricula", default="")
    p.add_argument("--contato", default="")
    p.set_defaults(func=cmd_create_user)

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

    p = sub.add_parser("pages", help="List platform pages")
    p.add_argument("--workspace", help="Workspace id or name")
    p.add_argument("--all-containers", action="store_true")
    p.add_argument("--include-inactive", action="store_true")
    p.add_argument("--exclude-fictitious", action="store_true")
    p.set_defaults(func=cmd_pages)

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
    p.set_defaults(func=cmd_deploy_manifest)

    p = sub.add_parser("smoke-pages", help="Resolve and request every page in a manifest using the authenticated session")
    p.add_argument("--manifest", required=True)
    p.add_argument("--timeout", type=int, default=60)
    p.set_defaults(func=cmd_smoke_pages)

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
        if "401" in error or "Sess" in error or "session" in error.lower():
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
