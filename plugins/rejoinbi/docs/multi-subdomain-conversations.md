# Multi-Subdomain — um agente, muitos projetos

O plugin do Codex para Rejoin BI suporta **vários subdomínios ao mesmo tempo**, sem conflito, para um desenvolvedor trabalhar em vários projetos. Cada subdomínio tem sua própria sessão autenticada, sua própria área de bancos gerenciados e nunca é misturado com outro.

## Como o armazenamento funciona

- Uma **sessão por subdomínio**: `~/.rejoinbi-platform/sessions/<slug>.json` (um arquivo por host; `slug` deriva do hostname).
- Um **subdomínio ativo/atual**: `~/.rejoinbi-platform/config.json` guarda `active_base_url`, que aponta para qual subdomínio é o 'atual'.
- Sessões são independentes e coexistem: conectar em `projetoA.rejoinbi.com.br` **não apaga** a sessão de `projetoB.rejoinbi.com.br`.

## Comandos

| Comando | O que faz |
|---|---|
| `ensure` / `tenant <subdomínio>` / `connect` | Autentica um subdomínio e **salva a sessão** dele (pode ter vários) |
| `tenants list` | Lista todos os subdomínios salvos + qual é o ativo |
| `tenants current` | Mostra o subdomínio atual desta máquina + se tem sessão válida |
| `tenants use <subdomínio>` | Troca o subdomínio ativo (local; exige sessão salva) |
| `tenants rm <subdomínio>` | Remove uma sessão salva (exige `--yes`) |

```powershell
python scripts/rejoinbi.py tenant projetoA.rejoinbi.com.br ensure
python scripts/rejoinbi.py tenants list
python scripts/rejoinbi.py tenants use projetoB.rejoinbi.com.br
python scripts/rejoinbi.py tenants current
```

## Regra de vínculo por conversa (agente)

Uma conversa do Codex atua contra **um único subdomínio de cada vez** (o 'vinculado à conversa'). O agente deve:

1. **Vincular no início**: ao detectar intenção de plataforma, fixa o subdomínio (perguntado, aberto/passado pelo usuário, ou obtido de `tenants current`/`tenants use`) e o mantém **igual por toda a conversa** — incluindo o `--tenant` de cada comando.
2. **Sempre saber qual é**: antes de qualquer comando de gravação/implantacão, confirme mentalmente que o alvo é o subdomínio vinculado. Mostre `tenants current` quando o desenvolvedor pedir 'qual está ativo aqui'.
3. **Nunca trocar silenciosamente**: se o usuário citar um subdomínio **diferente** do vinculado, **pare** e não mude por conta própria — ou abra uma nova conversa, ou peça um `tenants use <subdomínio>` explícito.
4. **Implantar no lugar certo**: comandos mutantes já exigem `--tenant` explícito (ou `--use-active-tenant` após conferir o subdomínio ativo). Use `--use-active-tenant` somente depois que `tenants current` confirmar que o ativo é o vinculado à conversa.
5. **Projetos separados**: um projeto = uma conversa = um subdomínio. Para trabalhar em outro projeto, use outra conversa (ou troque explicitamente com `tenants use`).

## Isolamento de dados

- Cada subdomínio tem **bancos gerenciados próprios** (`database_id` dedicado por RPA/projeto) — dois RPAs em subdomínios diferentes **nunca se bloqueiam**.
- NUNCA use a sessão/coleção de cookies de um subdomínio para outro.

Veja também: `docs/managed-database-external-api.md` (contrato de escrita de alto volume) e `docs/agent-operating-playbook.md`.
