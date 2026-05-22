const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat("pt-BR");
const percent = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });

const params = new URLSearchParams(window.location.search);
const pageId = params.get("pagina_id") || "codex-rls-suite-visao";

function sum(rows, key) {
  return rows.reduce((acc, row) => acc + Number(row[key] || 0), 0);
}

function groupSum(rows, groupKey, valueKey) {
  return rows.reduce((acc, row) => {
    const key = row[groupKey] || "Sem classificação";
    acc[key] = (acc[key] || 0) + Number(row[valueKey] || 0);
    return acc;
  }, {});
}

function applyRls(rows, config) {
  const active = Boolean(config?.active);
  const column = config?.coluna_n || "regiao";
  const allowed = Array.isArray(config?.allowed_values) ? config.allowed_values.map(String) : [];
  if (!active) {
    return { rows, column, allowed, active: false };
  }
  const filtered = rows.filter((row) => allowed.includes(String(row[column] ?? "")));
  return { rows: filtered, column, allowed, active: true };
}

async function loadRlsConfig() {
  const response = await fetch(`/plataforma/api/rls/config?pagina_id=${encodeURIComponent(pageId)}`, {
    credentials: "include",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) {
    throw new Error(`RLS HTTP ${response.status}`);
  }
  const payload = await response.json();
  return payload.rls_config || {};
}

async function loadData() {
  const response = await fetch("./data/atendimentos.json", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Dados HTTP ${response.status}`);
  }
  return response.json();
}

function renderKpis(rows, rlsState) {
  const receita = sum(rows, "receita");
  const clientes = sum(rows, "clientes");
  const churn = rows.length ? rows.reduce((acc, row) => acc + Number(row.churn || 0), 0) / rows.length : 0;

  document.getElementById("kpiReceita").textContent = currency.format(receita);
  document.getElementById("kpiClientes").textContent = integer.format(clientes);
  document.getElementById("kpiChurn").textContent = percent.format(churn);
  document.getElementById("kpiRegioes").textContent = rlsState.allowed.length ? rlsState.allowed.join(", ") : "Todas";
}

function renderCharts(rows) {
  const receitaPorRegiao = groupSum(rows, "regiao", "receita");
  const clientesPorPlano = groupSum(rows, "plano", "clientes");

  const receitaChart = echarts.init(document.getElementById("chartReceita"));
  receitaChart.setOption({
    backgroundColor: "transparent",
    color: ["#25c7b7"],
    grid: { left: 12, right: 16, top: 18, bottom: 0, containLabel: true },
    tooltip: { trigger: "axis", valueFormatter: (value) => currency.format(value) },
    xAxis: { type: "category", data: Object.keys(receitaPorRegiao), axisLabel: { color: "#9fc3c6" }, axisLine: { lineStyle: { color: "#21414b" } } },
    yAxis: { type: "value", axisLabel: { color: "#9fc3c6", formatter: (value) => `${Math.round(value / 1000)}k` }, splitLine: { lineStyle: { color: "rgba(159,195,198,.12)" } } },
    series: [{ type: "bar", data: Object.values(receitaPorRegiao), barWidth: 34, itemStyle: { borderRadius: [5, 5, 0, 0] } }]
  });

  const planoChart = echarts.init(document.getElementById("chartPlanos"));
  planoChart.setOption({
    backgroundColor: "transparent",
    color: ["#25c7b7", "#2f7df6", "#36d27f", "#ffd166"],
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: "#9fc3c6" } },
    series: [{
      type: "pie",
      radius: ["45%", "72%"],
      center: ["50%", "45%"],
      label: { color: "#f5fbfc" },
      data: Object.entries(clientesPorPlano).map(([name, value]) => ({ name, value }))
    }]
  });

  window.addEventListener("resize", () => {
    receitaChart.resize();
    planoChart.resize();
  });
}

function renderRows(rows) {
  const body = document.getElementById("dataRows");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-row">Nenhuma linha liberada para este usuário.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((row) => `
    <tr>
      <td>${row.regiao}</td>
      <td>${row.plano}</td>
      <td>${integer.format(row.clientes)}</td>
      <td>${currency.format(row.receita)}</td>
      <td>${percent.format(row.churn)}</td>
      <td>${percent.format(row.sla)}</td>
    </tr>
  `).join("");
}

async function boot() {
  const [allRows, config] = await Promise.all([loadData(), loadRlsConfig()]);
  const rlsState = applyRls(allRows, config);
  const email = config.user_email || "sessão não identificada";

  document.getElementById("rlsStatus").textContent = rlsState.active
    ? `RLS ativo para ${email}`
    : `RLS inativo para ${email}`;
  document.getElementById("rlsDetails").textContent = rlsState.active
    ? `${rlsState.rows.length} de ${allRows.length} linhas liberadas pela coluna ${rlsState.column}`
    : `${allRows.length} linhas visíveis sem filtro`;

  renderKpis(rlsState.rows, rlsState);
  renderCharts(rlsState.rows);
  renderRows(rlsState.rows);
}

boot().catch((error) => {
  document.getElementById("rlsStatus").textContent = "Falha ao carregar RLS";
  document.getElementById("rlsDetails").textContent = error.message;
  renderRows([]);
});
