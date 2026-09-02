# Managed Database — External API (alta performance)

Contrato oficial para **clientes remotos** (RPA/agentes/scripts) gravarem e consultarem os bancos de dados gerenciados da Plataforma RJ Local / Rejoin BI fora dos workspaces. Este documento substitui a mentalidade de '1 linha = 1 requisição' por cargas **atômicas, transacionais e em lote**.

> **Regra de ouro:** nunca instrua um cliente de alto volume a mandar **uma requisição HTTP por linha**. O gargalo é a latência de rede, não o SQLite. Use os modos `bulk_insert` e `statements` abaixo com uma sessão keep-alive.

---

## 1. Endpoints

Todos os acessos externos usam **HTTPS**, um token revogável com escopo (`rjdb_...`) no header `Authorization: Bearer <token>` e o `database_id` do banco de destino.

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/plataforma/api/managed-databases/external/<database_id>/limits` | Limites reais do servidor (bulk_max_rows, batch_rows, timeouts, concorrência, etc.) |
| `POST` | `/plataforma/api/managed-databases/external/<database_id>/query` | Executa SQL legado, carga em lote atômica ou bloco transacional |
| `POST` | `/plataforma/api/managed-databases/external/<database_id>/csv-import` | **Importação CSV** (multipart/form-data) — streaming parse C, até 1M linhas por request |

### `GET /limits` — exemplo de resposta
```json
{
  "limits": {
    "bulk_max_rows": 200000,
    "bulk_max_rows_limit": 1000000,
    "batch_rows": 50000,
    "max_result_rows": 100000,
    "query_timeout_ms": 30000,
    "max_concurrent_queries": 4,
    "max_sql_length": 500000,
    "write_lock_wait_seconds": 60
  }
}
```

---

## 2. Modos do `POST /query`

### 2.1 Legado (compatível, não quebrou nada)
```json
{ "sql": "SELECT * FROM carga WHERE valor > ?", "params": [100] }
```
Clientes antigos continuam funcionando **sem nenhuma mudança**. As novidades só ativam quando as chaves do payload estiverem presentes.

### 2.2 Carga em lote atômica — `bulk_insert`
```json
{
  "bulk_insert": {
    "table": "carga",
    "columns": ["id", "nome", "valor"],
    "rows": [[1, "a", 1.5], [2, "b", 2.5], [3, "c", 3.5]]
  },
  "bulk_max_rows": 50000
}
```
- **Atômico**: 1 banco recebe tudo ou nada; internamente o servidor insere em lotes de `batch_rows` (50.000) dentro de uma única transação.
- `bulk_max_rows` é `opcional` (padrão 200.000; teto 1.000.000). Acima do teto → erro `400` `bulk_max_exceeded`: **divida em mais de uma chamada**.
- Escopo do token exigido: `data_write` ou `schema_admin`.

### 2.3 Bloco transacional — `statements` (recomendado para ciclos com DDL)
```json
{
  "statements": [
    { "sql": "DROP TABLE IF EXISTS _tmp_carga" },
    { "sql": "CREATE TABLE _tmp_carga (id INTEGER PRIMARY KEY, nome TEXT, valor NUMERIC)" },
    { "sql": "INSERT INTO _tmp_carga (id, nome, valor) VALUES (?, ?, ?)",
      "params": [[1, "a", 1.5], [2, "b", 2.5], [3, "c", 3.5]] },
    { "sql": "DROP TABLE IF EXISTS carga" },
    { "sql": "ALTER TABLE _tmp_carga RENAME TO carga" }
  ]
}
```
- Todas as instruções rodam **na mesma conexão** dentro de uma transação (`BEGIN IMMEDIATE` … `COMMIT`). Se qualquer uma falhar, **todas revertem** (`ROLLBACK`) — sem dados parciais nem duplicação.
- `params` pode ser:
  - **ausente** → SQL puro (`cursor.execute(sql)`),
  - **lista simples** → executa uma instrução com aqueles parâmetros,
  - **lista de listas** → inserção em massa (`executemany`) — use para o `INSERT` do ciclo.
- Escopos validados **antes** de adquirir locks:
  - DDL (`CREATE`/`DROP`/`ALTER`/`RENAME` etc.) → exige `schema_admin`;
  - apenas escrita → `data_write` ou `schema_admin`;
  - blocos de só leitura também são rejeitados em tokens de leitura pura.
- Falha na instrução N → `400` com mensagem clara `Falha na instrução N do bloco transacional: ...` (não vira `503`).

### 2.4 Importação CSV — `csv-import` (recomendado para volumetria extrema)

Para transferências acima de ~50 mil linhas, o **CSV é o caminho mais rápido**: o servidor faz o parse em C (`csv.reader`) direto do stream do arquivo, sem materializar o payload inteiro em memória como o JSON bulk faz. Aceita até **1.000.000 de linhas por request**.

```bash
# HTTP multipart/form-data com um Bearer token de escrita
curl -X POST "https://subdomain.rejoinbi.com.br/plataforma/api/managed-databases/external/<database_id>/csv-import" \
  -H "Authorization: Bearer rjdb_..." \
  -F "file=@dados.csv" \
  -F "table=minha_tabela" \
  -F "header=1"
```

**Parâmetros (multipart/form-data):**
| Campo | Obrigatório | Descrição |
|---|---|---|
| `file` | sim | Arquivo `.csv` (UTF-8; BOM aceito) |
| `table` | sim | Nome da tabela de destino |
| `header` | não (default `1`) | `1`/`0` — primeira linha é cabeçalho? |
| `columns` | não | Lista de colunas separada por vírgula; se ausente, usa o cabeçalho |

- O arquivo é lido **em streaming** e inserido em lotes de `batch_rows` dentro de uma única transação atômica.
- Linhas vazias são puladas; linhas com nº de valores diferente do esperado → `400` com o nº da linha.
- Após o commit, o servidor faz `wal_checkpoint(PASSIVE)` (sem reescrever o WAL inteiro).
- Escopo do token exigido: `data_write` ou `schema_admin`.

**Resposta:**
```json
{ "success": true, "mode": "csv_import", "table": "minha_tabela", "columns": [...], "rows_inserted": 123456, "elapsed_ms": 5120 }
```

---

## 3. Semântica de erros e concorrência

| HTTP | Significado | Ação do cliente |
|---|---|---|
| `200` | Sucesso | — |
| `400` | Validação/escopo/`bulk_max_exceeded` | Corrija o payload; não reenvie em loop |
| `409` | Conflito (ex.: nome em uso) | Trate como estado; recrie com outro nome |
| `423`/`429` | Token/slot/lock ocupado ou rate limit | **Backoff** e reenvie (respeite `Retry-After`) |
| `503` `database_busy` | Tabela/banco com lock por outro cliente | **Aguarde e reenvie**: o servidor segura o lock até `write_lock_wait_seconds` (até 60 s) em vez de recusar na hora |

- **Lock por tabela** + espera longa: dois escritores em **tabelas diferentes** não se bloqueiam; dois no mesmo objeto **aguardam** até 60 s.
- **Rate limit por token** por minuto — leia a janela real em `/limits` quando aplicável.

---

## 4. Melhores práticas de cliente

- **Keep-alive**: reutilize a conexão com `requests.Session` (ou equivalente HTTP/1.1 persistente) — nunca abra uma conexão nova por requisição.
- **Ciclo atômico**: prefira **um único** `statements` com `DROP → CREATE → INSERT(massa) → DROP → RENAME` em vez de várias chamadas separadas.
- **Prefira CSV para volumetria**: acima de ~50 mil linhas, use `csv-import` (streaming parse C) em vez de JSON bulk — 3-5x mais rápido.
- **Respeite `/limits`**: leia `bulk_max_rows`/`bulk_max_rows_limit` no início e divida lotes > 1.000.000.
- **Retry com backoff** em `423/429/503`, com timeout de cliente generoso (ex.: 180 s) para cargas grandes.
- **Isolamento por RPA**: crie um `database_id` dedicado por cliente/workspace — cada banco é um arquivo `.sqlite3` próprio, então dois RPAs **nunca se bloqueiam**.
- **Compatibilidade**: modos novos **coexistem** com o payload legado `{sql}`.

---

## 5. Cliente Python de referência

```python
import time
import requests


class _ErroHTTP(Exception):
    def __init__(self, status, body):
        super().__init__('HTTP %s: %s' % (status, body))
        self.status = status
        self.body = body


class ManagerManagedDB:
    """Cliente otimizado (lote + transação) para o managed-database externo."""

    def __init__(self, endpoint_base, token, bulk_max_rows=50000,
                 retries=4, backoff=(0.5, 20.0), timeout=180):
        self._base = endpoint_base.rstrip('/')
        self.bulk_max_rows = bulk_max_rows
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        # keep-alive: reutiliza a mesma conexão TCP/TLS entre chamadas
        self._s = requests.Session()
        self._s.headers.update({
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    def limites(self):
        r = self._s.get(self._base + '/limits', timeout=30)
        r.raise_for_status()
        return r.json()['limits']

    def _post(self, payload, timeout=None):
        last = None
        for tentativa in range(self.retries):
            try:
                r = self._s.post(self._base + '/query', json=payload,
                                 timeout=timeout or self.timeout)
            except requests.RequestException as exc:
                last = exc
                time.sleep(self.backoff[0])
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 409, 423, 429, 502, 503, 504):
                retry_after = None
                if 'Retry-After' in r.headers:
                    try:
                        retry_after = min(float(r.headers['Retry-After']),
                                          self.backoff[1])
                    except ValueError:
                        retry_after = None
                # 503 database_busy: o servidor segura o lock até 60s;
                # aguardamos e reenviamos em vez de tratar como erro fatal.
                time.sleep(retry_after if retry_after else self.backoff[0])
                last = _ErroHTTP(r.status_code, r.text)
                continue
            r.raise_for_status()
        if isinstance(last, _ErroHTTP) and last.status == 400:
            raise last  # erro de validação: não reenviar em loop
        raise last if last else RuntimeError('Falha sem detalhe')

    # ------------------------------------------------------------------
    def bulk_insert(self, table, columns, rows, max_rows=None):
        """Carga atômica em lote (uma transação). Divide se passar do teto."""
        limite = self._bulk_teto()
        blocos = [rows[i:i + limite] for i in range(0, len(rows), limite)]
        for bloco in blocos:
            self._post({
                "bulk_insert": {"table": table, "columns": columns, "rows": bloco},
                "bulk_max_rows": self.bulk_max_rows,
            })

    def ciclo_carga(self, colunas, linhas, tabela_final, sql_cria_temp):
        """Ciclo DROP -> CREATE -> INSERT(massa) -> DROP -> RENAME, atômico."""
        tmp = '_tmp_' + tabela_final
        cols = ','.join(colunas)
        ph = ','.join(['?'] * len(colunas))
        comandos = [
            {"sql": 'DROP TABLE IF EXISTS ' + tmp},
            {"sql": sql_cria_temp.format(tabela=tmp)},
        ]
        for regiao in range(0, len(linhas), self._bulk_teto()):
            comandos.append({
                "sql": 'INSERT INTO %s (%s) VALUES (%s)' % (tmp, cols, ph),
                "params": linhas[regiao:regiao + self._bulk_teto()],
            })
        comandos.append({"sql": 'DROP TABLE IF EXISTS ' + tabela_final})
        comandos.append({"sql": 'ALTER TABLE %s RENAME TO %s' % (tmp, tabela_final)})
        return self._post({"statements": comandos})

    def _bulk_teto(self):
        try:
            return int(self.limites().get('bulk_max_rows_limit', 1000000))
        except Exception:
            return 1000000

    def csv_import(self, table, csv_path, header=True, columns=None):
        """Importa CSV via streaming (preferido para >50k linhas)."""
        data = {'table': table, 'header': '1' if header else '0'}
        if columns:
            data['columns'] = ','.join(columns)
        with open(csv_path, 'rb') as fh:
            r = self._s.post(
                self._base + '/csv-import',
                files={'file': (csv_path, fh, 'text/csv')},
                data=data,
                timeout=self.timeout,
            )
        r.raise_for_status()
        return r.json()
```

**Uso:**
```python
db = ManagerManagedDB(
    'https://subdomain.rejoinbi.com.br/plataforma/api/managed-databases/external/<database_id>',
    'rjdb_...',
)
res = db.ciclo_carga(
    ["id", "nome", "valor"],
    linhas_55863,
    'carga',
    'CREATE TABLE {tabela} (id INTEGER PRIMARY KEY, nome TEXT, valor NUMERIC)',
)
```

Com este contrato, **55.863 linhas** saem de `~440–503 s` para o objetivo de **<60–90 s**, e o ciclo completo cai de `~16 min` para **<5 min**.
