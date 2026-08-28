# -*- coding: utf-8 -*-
"""
managed_client.py - Cliente otimizado (lote + transação) para o
managed-database externo da Plataforma RJ Local / Rejoin BI.

Contrato completo: docs/managed-database-external-api.md

Principios:
  * keep-alive (requests.Session) - nunca 1 conexao nova por requisicao
  * carga atomica em lote (bulk_insert) e bloco transacional (statements)
  * respeita os limites reais de /limits (bulk_max_rows, teto 200.000)
  * retry com backoff em 423/429/503 (503 database_busy aguarda ate 60s)
  * um database_id dedicado por RPA (isolamento, sem bloqueio cruzado)
"""

import time

import requests


class _ErroHTTP(Exception):
    def __init__(self, status, body):
        super().__init__("HTTP %s: %s" % (status, body))
        self.status = status
        self.body = body


class ManagerManagedDB:
    """Cliente de alta performance para o managed-database externo."""

    def __init__(self, endpoint_base, token, bulk_max_rows=50000,
                 retries=4, backoff=(0.5, 20.0), timeout=180):
        self._base = endpoint_base.rstrip("/")
        self.bulk_max_rows = bulk_max_rows
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self._s = requests.Session()
        self._s.headers.update({
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    def limites(self):
        """Limites reais do servidor (bulk_max_rows, teto, concorrencia...)."""
        r = self._s.get(self._base + "/limits", timeout=30)
        r.raise_for_status()
        return r.json()["limits"]

    def _max_linhas_por_chamada(self):
        try:
            return int(self.limites().get("bulk_max_rows_limit", 200000))
        except Exception:
            return 200000

    def _post(self, payload, timeout=None):
        last = None
        for _ in range(self.retries):
            try:
                r = self._s.post(self._base + "/query", json=payload,
                                 timeout=timeout or self.timeout)
            except requests.RequestException as exc:
                last = exc
                time.sleep(self.backoff[0])
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 409, 423, 429, 502, 503, 504):
                retry_after = None
                if "Retry-After" in r.headers:
                    try:
                        retry_after = min(float(r.headers["Retry-After"]),
                                          self.backoff[1])
                    except ValueError:
                        retry_after = None
                time.sleep(retry_after if retry_after else self.backoff[0])
                last = _ErroHTTP(r.status_code, r.text)
                continue
            r.raise_for_status()
        if isinstance(last, _ErroHTTP) and last.status == 400:
            raise last  # validacao/escopo: nao reenviar em loop
        raise last if last else RuntimeError("Falha sem detalhe")

    # ------------------------------------------------------------------
    def bulk_insert(self, table, columns, rows):
        """Carga atomica em lote; divide lotes quanto passa do teto."""
        limite = self._max_linhas_por_chamada()
        for i in range(0, len(rows), limite):
            self._post({
                "bulk_insert": {
                    "table": table,
                    "columns": columns,
                    "rows": rows[i:i + limite],
                },
                "bulk_max_rows": self.bulk_max_rows,
            })

    def ciclo_carga(self, colunas, linhas, tabela_final, sql_cria_temp):
        """Ciclo DROP -> CREATE -> INSERT(massa) -> DROP -> RENAME, atomico."""
        tmp = "_tmp_" + tabela_final
        cols = ",".join(colunas)
        ph = ",".join(["?"] * len(colunas))
        comandos = [
            {"sql": "DROP TABLE IF EXISTS " + tmp},
            {"sql": sql_cria_temp.format(tabela=tmp)},
        ]
        limite = self._max_linhas_por_chamada()
        for i in range(0, len(linhas), limite):
            comandos.append({
                "sql": "INSERT INTO %s (%s) VALUES (%s)" % (tmp, cols, ph),
                "params": linhas[i:i + limite],
            })
        comandos.append({"sql": "DROP TABLE IF EXISTS " + tabela_final})
        comandos.append({"sql": "ALTER TABLE %s RENAME TO %s" % (tmp, tabela_final)})
        return self._post({"statements": comandos})


# ---------------------------------------------------------------------
# Exemplo de uso (ajuste antes de produzir):
#
# db = ManagerManagedDB(
#     "https://subdomain.rejoinbi.com.br/plataforma/api/managed-databases/external/<database_id>",
#     "rjdb_...",
# )
# res = db.ciclo_carga(
#     ["id", "nome", "valor"],
#     linhas_55863,
#     "carga",
#     "CREATE TABLE {tabela} (id INTEGER PRIMARY KEY, nome TEXT, valor NUMERIC)",
# )
