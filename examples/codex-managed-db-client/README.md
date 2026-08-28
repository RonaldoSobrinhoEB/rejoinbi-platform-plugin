# codex-managed-db-client

Cliente de referência (Python) para o **managed-database externo** da Plataforma RJ Local / Rejoin BI, otimizado para cargas de alto volume.

Arquivos:
- `managed_client.py` — cliente pronto: keep-alive (`requests.Session`), `bulk_insert` atômico, bloco `statements` transacional, leitura de `/limits`, retry/backoff e isolamento por `database_id`.

Contrato completo (payloads, escopos de token, erros, metas de performance): [docs/managed-database-external-api.md](../../docs/managed-database-external-api.md).

## Uso rápido
```python
from managed_client import ManagerManagedDB

db = ManagerManagedDB(
    "https://subdomain.rejoinbi.com.br/plataforma/api/managed-databases/external/<database_id>",
    "rjdb_...",
)
print(db.limites())

db.ciclo_carga(
    ["id", "nome", "valor"],
    linhas_55863,
    "carga",
    "CREATE TABLE {tabela} (id INTEGER PRIMARY KEY, nome TEXT, valor NUMERIC)",
)
```

## Regras
- Nunca envie 1 requisição por linha — use `bulk_insert`/`statements`.
- Respeite `bulk_max_rows_limit` de `/limits` (padrão 200.000) ao dividir lotes.
- Dê um `database_id` dedicado por RPA para isolamento.
- Token com escopo `data_write` (escrita) ou `schema_admin` (DDL).
