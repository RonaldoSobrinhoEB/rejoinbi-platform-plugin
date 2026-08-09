# Privacy Policy

Rejoin BI is a Codex plugin for operating Rejoin BI addresses selected by the user.

## Data handled by the plugin

- Platform addresses provided by the user, such as `subdomain.rejoinbi.com.br`.
- Rejoin BI session cookies created after the user completes login.
- Metadata returned by the authenticated Rejoin BI platform, such as workspace names, page names, BI Studio project names, Data Engine dataset names, and admin configuration summaries.
- Local files selected by the user for upload to a Rejoin BI workspace.

## Credential handling

The default login flow opens a local browser authentication page. Passwords and PINs are submitted directly to the selected Rejoin BI platform and are not saved by the plugin. The plugin stores only session cookies and session metadata under the user's local profile directory.

For automation use, passwords or PINs may be read from local environment variables or terminal prompts when the user explicitly chooses that flow.

## Network access

The plugin communicates with the Rejoin BI platform address selected by the user. It does not send platform data to the plugin author, OpenAI, or any third-party analytics service.

## Local storage

Saved sessions are stored locally under `.rejoinbi-platform` in the user's home directory. Generated reports, backups, and exported packages are written only to local paths selected by the user or documented plugin defaults.

## Sensitive data redaction

Inventory commands redact fields that look like passwords, tokens, API keys, credentials, secrets, or connection strings before printing summaries.

## Contact

For questions about this plugin, use the repository issues page:

https://github.com/RonaldoSobrinhoEB/rejoinbi-platform-plugin/issues
