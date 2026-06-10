# Windows Marketplace Install

Use this when Codex shows:

```text
failed to run git clone https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin.git ...: program not found
```

That message happens before the Rejoin BI plugin runs. Codex is trying to clone the marketplace from GitHub, but Windows cannot find the local `git` executable.

This is not a Rejoin BI login problem, not a password or PIN problem, and not a different-user permission problem inside the platform. The marketplace install step depends on Git being available on the user's computer.

## Recommended Fix

Install Git for Windows, fully restart Codex, and add the marketplace again.

```powershell
winget install --id Git.Git -e --source winget
git --version
```

Use these Codex marketplace fields:

- Origem: `https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin.git`
- Referencia do Git: `main`
- Caminhos esparsos: leave empty

## Fallback Without Git

If that user cannot install Git:

1. Open `https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin`.
2. Download the repository ZIP.
3. Extract the ZIP to a normal folder, for example `C:\Users\<user>\Downloads\rejoinbi-platform-plugin`.
4. In Codex, add a marketplace and set `Origem` to that extracted local folder.
5. Leave `Referencia do Git` and `Caminhos esparsos` empty.

The marketplace manifest is at `.agents/plugins/marketplace.json`, and the plugin lives at `plugins/rejoinbi`.

## Quick Diagnostic

Ask the user to run this in PowerShell:

```powershell
git --version
```

If PowerShell says that `git` is not recognized, install Git for Windows and restart Codex before adding the marketplace again.
