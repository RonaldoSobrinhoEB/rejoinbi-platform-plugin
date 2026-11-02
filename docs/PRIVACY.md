# Privacy Policy

Rejoin BI is a Codex plugin that operates Rejoin BI platform addresses selected by the user. This policy states what the plugin handles, why, where it goes, how long it stays, and what controls the user has.

## Data handled by the plugin

- Platform addresses provided by the user, such as `subdomain.rejoinbi.com.br`.
- Rejoin BI session cookies and session metadata created after the user completes login.
- Local files the user explicitly selects for upload to a Rejoin BI workspace.
- Command arguments, including the operation scope declared for each remote command.
- Responses returned by the selected Rejoin BI platform, including workspace, page, and database metadata.

## Purposes of use

- Authenticate the user against the selected Rejoin BI platform.
- Execute only the platform operation the user requested, under the declared operation scope.
- Validate upload paths and compare remote file hashes after transfer.
- Produce local plans, diagnostics, and reports for the user to review.

The plugin does not profile users, build advertising audiences, or use platform data for any purpose beyond the requested operation.

## Credential handling

The default login flow opens a local browser authentication page. Passwords and PINs are submitted directly to the selected Rejoin BI platform and are not saved by the plugin. The plugin stores only session cookies and session metadata under the user's local profile directory.

For automation use, passwords or PINs may be read from local environment variables or terminal prompts when the user explicitly chooses that flow.

## Recipients

- The Rejoin BI platform address selected by the user receives the commands and files the user asks the plugin to send.
- No platform data is sent to the plugin author, OpenAI, or any third-party analytics, advertising, or telemetry service.
- Session cookies and local artifacts stay on the user's machine.

## Retention

- Local sessions persist under `.rejoinbi-platform` until the user logs out or deletes that directory.
- Generated reports, plans, backups, and exported packages persist at the local paths the user chose until the user removes them.
- The plugin keeps no server-side copy; retention of uploaded files and platform records is governed by the selected Rejoin BI workspace and its settings.

## User controls

- Log out or delete the local session directory to remove stored cookies.
- Review dry-run plans and `[DESTINATION-MAP]` output before any upload or destructive command.
- Restrict each command with an explicit operation scope, and keep identity operations behind confirmation flags.
- Redact sensitive fields before sharing command output.

## Sensitive data redaction

Inventory commands redact fields that look like passwords, tokens, API keys, credentials, secrets, or connection strings before printing summaries.

## Contact

For questions about this plugin, use the repository issues page:

https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin/issues
