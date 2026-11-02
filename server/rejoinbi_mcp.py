#!/usr/bin/env python3
"""Rejoin BI MCP server (stdio, standard library only).

Speaks newline-delimited JSON-RPC on stdin/stdout. Every tool delegates to the
bundled scripts/rejoinbi.py CLI, so operation scopes, identity confirmations and
confirmation flags keep a single implementation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

SERVER_NAME = "rejoinbi"
SERVER_VERSION = "0.5.2"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL = "2024-11-05"

PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1]).resolve()
CLI = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
DEFAULT_TIMEOUT = 900
MAX_TIMEOUT = 3600
MAX_OUTPUT_CHARS = 200_000

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

LOG = sys.stderr


def _log(message: str) -> None:
    LOG.write(f"[rejoinbi-mcp] {message}\n")
    LOG.flush()


_PYTHON_CACHE: list[str] | None = None


def _python_candidates() -> list[list[str]]:
    # Interpreters to probe, most specific first.
    out: list[list[str]] = []
    override = os.environ.get("REJOINBI_PYTHON")
    if override:
        out.append([override])
    out.append([sys.executable])
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            out.append([found])
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            out.append([launcher, "-3"])
    return out


def _resolve_python() -> list[str]:
    # First interpreter that can import requests, cached per process.
    global _PYTHON_CACHE
    if _PYTHON_CACHE:
        return _PYTHON_CACHE
    for cmd in _python_candidates():
        try:
            probe = subprocess.run(
                [*cmd, "-B", "-c", "import requests"],
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            _PYTHON_CACHE = cmd
            return cmd
    raise RuntimeError(
        "no Python interpreter with the 'requests' package was found; "
        "install it with 'pip install -r requirements.txt' or set REJOINBI_PYTHON"
    )


def _invoke(argv: list[str], timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run the bundled CLI and return exit code plus output."""
    if not CLI.is_file():
        return f"error: Rejoin BI CLI not found at {CLI}"

    timeout = max(1, min(int(timeout), MAX_TIMEOUT))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        python_cmd = _resolve_python()
    except RuntimeError as exc:
        return f"error: {exc}"

    try:
        proc = subprocess.run(
            [*python_cmd, "-B", str(CLI), *argv],
            cwd=str(PLUGIN_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s: {argv}"
    except OSError as exc:
        return f"error: could not start the Rejoin BI CLI: {exc}"

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    body = stdout or stderr
    if len(body) > MAX_OUTPUT_CHARS:
        body = body[:MAX_OUTPUT_CHARS] + "\n...[output truncated]"

    header = f"exit_code: {proc.returncode}"
    if not stdout and stderr:
        header += "\n(output came from stderr only)"
    return f"{header}\n\n{body}" if body else header


def _require_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required and must be a non-empty string")
    return value.strip()


def _optional_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string")
    return value.strip()


def _str_list(args: dict[str, Any], key: str, required: bool = True) -> list[str]:
    value = args.get(key)
    if value is None:
        if required:
            raise ValueError(f"'{key}' is required and must be a non-empty array of strings")
        return []
    if not isinstance(value, list) or not value:
        raise ValueError(f"'{key}' must be a non-empty array of strings")
    items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"'{key}' must contain only non-empty strings")
        items.append(item.strip())
    return items


def _timeout(args: dict[str, Any]) -> int:
    value = args.get("timeout_seconds", DEFAULT_TIMEOUT)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("'timeout_seconds' must be an integer")
    return max(1, min(value, MAX_TIMEOUT))


def _tenant_argv(args: dict[str, Any]) -> list[str]:
    tenant = _require_str(args, "tenant")
    return ["--tenant", tenant]


def _tool_doctor(_args: dict[str, Any]) -> str:
    lines = [
        f"plugin_root: {PLUGIN_ROOT}",
        f"cli: {'ok' if CLI.is_file() else 'missing'}",
        f"server_python: {sys.version.split()[0]}",
        f"server_version: {SERVER_VERSION}",
    ]
    try:
        python_cmd = _resolve_python()
        lines.append(f"cli_python: {' '.join(python_cmd)}")
    except RuntimeError as exc:
        lines.append(f"cli_python: unavailable ({exc})")
        return "exit_code: 1\n\n" + "\n".join(lines)
    try:
        probe = subprocess.run(
            [*python_cmd, "-B", "-c", "import requests;print(requests.__version__)"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        version = (probe.stdout or "").strip()
        lines.append(f"requests: {version}" if version else "requests: missing (python -m pip install requests)")
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"requests: probe failed ({exc})")
    return "exit_code: 0\n\n" + "\n".join(lines)


def _tool_run(args: dict[str, Any]) -> str:
    command = _require_str(args, "command")
    if command.startswith("-") or any(char.isspace() for char in command):
        raise ValueError("'command' must be a single CLI subcommand such as workspaceall")
    return _invoke([*_tenant_argv(args), command, *_str_list(args, "args", required=False)], _timeout(args))


def _tool_validate_app(args: dict[str, Any]) -> str:
    argv = ["validate-app", "--manifest", _require_str(args, "manifest_path")]
    if args.get("strict") is True:
        argv.append("--strict")
    return _invoke(argv, _timeout(args))


def _tool_workspace_list(args: dict[str, Any]) -> str:
    return _invoke([*_tenant_argv(args), "workspaceall", "--operation-scope", "workspace"], _timeout(args))


def _tool_read_file(args: dict[str, Any]) -> str:
    argv = [
        *_tenant_argv(args),
        "workspace-file",
        "read",
        "--workspace",
        _require_str(args, "workspace"),
        "--path",
        _require_str(args, "path"),
        "--operation-scope",
        "workspace",
    ]
    return _invoke(argv, _timeout(args))


def _tool_upload_plan(args: dict[str, Any]) -> str:
    plan_path = Path(tempfile.gettempdir()) / f"rejoinbi-upload-plan-{os.getpid()}.json"
    argv = [
        *_tenant_argv(args),
        "upload-files",
        "--workspace",
        _require_str(args, "workspace"),
        "--source-root",
        _require_str(args, "source_root"),
        "--files",
        *_str_list(args, "files"),
        "--dry-run",
        "--plan-output",
        str(plan_path),
        "--operation-scope",
        "upload",
    ]
    output = _invoke(argv, _timeout(args))
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError:
        plan_text = ""
    finally:
        try:
            plan_path.unlink()
        except OSError:
            pass
    if plan_text:
        output += "\n\nplan:\n" + plan_text
    return output


def _tool_deploy(args: dict[str, Any]) -> str:
    upload_mode = _require_str(args, "upload_mode")
    if upload_mode not in ("full", "changed-files"):
        raise ValueError("'upload_mode' must be 'full' or 'changed-files'")
    argv = [
        *_tenant_argv(args),
        "deploy-manifest",
        "--manifest",
        _require_str(args, "manifest_path"),
        "--upload-mode",
        upload_mode,
        "--operation-scope",
        "deployment",
    ]
    if args.get("dry_run", True) is not False:
        argv.append("--dry-run")
    return _invoke(argv, _timeout(args))


def _tool_smoke_pages(args: dict[str, Any]) -> str:
    argv = [
        *_tenant_argv(args),
        "smoke-pages",
        "--manifest",
        _require_str(args, "manifest_path"),
        "--operation-scope",
        "pages",
    ]
    return _invoke(argv, _timeout(args))


TOOLS: list[dict[str, Any]] = [
    {
        "name": "rejoinbi_doctor",
        "description": (
            "Check local prerequisites for this plugin: CLI presence, Python version, "
            "requests availability and server version. Run it first when another Rejoin BI "
            "tool fails."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "rejoinbi_run",
        "description": (
            "Run any Rejoin BI CLI command and return its JSON output. Use it for commands "
            "without a dedicated tool. Remote commands still require their exact "
            "--operation-scope, and identity writes still require --yes plus the applicable "
            "confirmations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "CLI subcommand, for example workspaceall, upload-files or users.",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional argv tokens, for example [\"--workspace\",\"12\",\"--operation-scope\",\"workspace\"].",
                },
                "tenant": {
                    "type": "string",
                    "description": "Platform subdomain such as acme.rejoinbi.com.br. Omit for local-only commands.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3600,
                    "description": "Command timeout in seconds. Defaults to 900.",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_validate_app",
        "description": (
            "Validate a local dashboard folder or manifest against Rejoin BI workspace "
            "compatibility rules before any upload. Local only; nothing is transferred."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest_path": {"type": "string", "description": "Absolute path to rejoinbi-app.json."},
                "strict": {"type": "boolean", "description": "Treat warnings as failures."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["manifest_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_workspace_list",
        "description": (
            "List the workspaces of one authenticated Rejoin BI platform. Runs with "
            "--operation-scope workspace and requires an existing login session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant": {"type": "string", "description": "Platform subdomain, for example acme.rejoinbi.com.br."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["tenant"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_read_file",
        "description": (
            "Read one workspace file's content directly from the platform without "
            "downloading it. Runs with --operation-scope workspace."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant": {"type": "string", "description": "Platform subdomain."},
                "workspace": {"type": "string", "description": "Workspace id or name."},
                "path": {"type": "string", "description": "Workspace-relative file path."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["tenant", "workspace", "path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_upload_plan",
        "description": (
            "Dry-run an upload and return the source to remote target plan with sizes and "
            "sha256 hashes. Nothing is transferred; review every target before uploading."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant": {"type": "string", "description": "Platform subdomain."},
                "workspace": {"type": "string", "description": "Workspace id or name."},
                "source_root": {"type": "string", "description": "Absolute project root used to preserve relative paths."},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Absolute paths of the selected files.",
                },
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["tenant", "workspace", "source_root", "files"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_deploy",
        "description": (
            "Deploy a manifest to a workspace with an explicit upload mode. Defaults to "
            "dry_run=true; only pass dry_run=false when this exact publication is authorized."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant": {"type": "string", "description": "Platform subdomain."},
                "manifest_path": {"type": "string", "description": "Absolute path to rejoinbi-app.json."},
                "upload_mode": {
                    "type": "string",
                    "enum": ["full", "changed-files"],
                    "description": "full publishes the whole project; changed-files uploads only explicitly listed files.",
                },
                "dry_run": {"type": "boolean", "description": "Defaults to true."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["tenant", "manifest_path", "upload_mode"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rejoinbi_smoke_pages",
        "description": (
            "Resolve and request every page of a published manifest with the authenticated "
            "session, reporting html_ok, browser_route_ok and menu_safe gates."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant": {"type": "string", "description": "Platform subdomain."},
                "manifest_path": {"type": "string", "description": "Absolute path to rejoinbi-app.json."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            },
            "required": ["tenant", "manifest_path"],
            "additionalProperties": False,
        },
    },
]

HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "rejoinbi_doctor": _tool_doctor,
    "rejoinbi_run": _tool_run,
    "rejoinbi_validate_app": _tool_validate_app,
    "rejoinbi_workspace_list": _tool_workspace_list,
    "rejoinbi_read_file": _tool_read_file,
    "rejoinbi_upload_plan": _tool_upload_plan,
    "rejoinbi_deploy": _tool_deploy,
    "rejoinbi_smoke_pages": _tool_smoke_pages,
}


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _result(msg_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": payload}


def _negotiate(requested: Any) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOLS:
        return requested
    return DEFAULT_PROTOCOL


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")

    if method == "initialize":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        return _result(
            msg_id,
            {
                "protocolVersion": _negotiate(params.get("protocolVersion")),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Rejoin BI tools drive the bundled local CLI. Remote commands require "
                    "their exact --operation-scope, identity writes require --yes plus the "
                    "applicable confirmations, and deploy defaults to dry_run."
                ),
            },
        )
    if isinstance(method, str) and method.startswith("notifications/"):
        return None
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict):
            return _error(msg_id, INVALID_PARAMS, "params must be an object")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(msg_id, INVALID_PARAMS, "arguments must be an object")
        handler = HANDLERS.get(params.get("name"))
        if handler is None:
            return _error(msg_id, INVALID_PARAMS, f"unknown tool: {params.get('name')}")
        try:
            text = handler(arguments)
        except ValueError as exc:
            return _result(msg_id, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
        except Exception as exc:  # tool boundary must never kill the server
            _log(f"tool {params.get('name')} failed: {exc!r}")
            return _result(msg_id, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
        is_error = text.startswith("error:") or not text.startswith("exit_code: 0")
        return _result(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
    if method == "resources/list":
        return _result(msg_id, {"resources": []})
    if method == "resources/templates/list":
        return _result(msg_id, {"resourceTemplates": []})
    if method == "prompts/list":
        return _result(msg_id, {"prompts": []})
    if "id" not in message:
        return None
    return _error(msg_id, METHOD_NOT_FOUND, f"method not found: {method}")


def main() -> int:
    _log(f"server {SERVER_VERSION} ready; plugin root {PLUGIN_ROOT}")
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            _write(_error(None, PARSE_ERROR, "invalid JSON"))
            continue

        messages = payload if isinstance(payload, list) else [payload]
        for message in messages:
            if not isinstance(message, dict):
                _write(_error(None, INVALID_REQUEST, "request must be an object"))
                continue
            try:
                response = _handle(message)
            except Exception as exc:
                _log(f"handler crashed: {exc!r}")
                response = _error(message.get("id"), INTERNAL_ERROR, "internal server error")
            if response is not None:
                _write(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
