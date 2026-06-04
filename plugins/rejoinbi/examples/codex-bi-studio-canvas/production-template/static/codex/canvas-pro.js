const DATA = {
  total: { receita: 108.69, margemPct: 37.2, clientes: 26.8, churnPct: 0.79, tickets: 7651, uptime: 99.29, sla: 99.05, nps: 70.3, risk: 12.4, margem: 40.44, custo: 68.25 },
  months: [
    ["Jan", 8.82, 36.9, 0.60, 604, 99.29, 71.0, 11.5],
    ["Fev", 9.05, 37.9, 0.63, 579, 99.29, 71.5, 11.4],
    ["Mar", 9.00, 37.7, 0.79, 602, 99.36, 71.3, 10.6],
    ["Abr", 9.41, 37.4, 1.06, 689, 99.30, 70.7, 12.1],
    ["Mai", 9.18, 36.9, 0.97, 680, 99.29, 69.1, 12.8],
    ["Jun", 9.06, 37.2, 0.81, 566, 99.27, 71.1, 11.8],
    ["Jul", 9.36, 37.4, 0.87, 660, 99.22, 70.7, 13.8],
    ["Ago", 9.21, 36.6, 0.71, 642, 99.30, 69.3, 12.2],
    ["Set", 9.03, 37.5, 0.93, 744, 99.19, 68.2, 16.0],
    ["Out", 9.05, 36.2, 0.88, 626, 99.28, 71.7, 11.5],
    ["Nov", 8.80, 37.0, 0.43, 611, 99.33, 68.3, 12.6],
    ["Dez", 8.72, 37.6, 0.75, 648, 99.30, 70.6, 12.2]
  ],
  regions: [
    ["Centro-Oeste", 18.46, 37.3, 4.7, 0.36, 1248, 99.35, 71.6, 10.2],
    ["Nordeste", 20.83, 37.4, 5.2, 0.58, 1510, 99.33, 70.7, 11.1],
    ["Norte", 14.52, 37.6, 4.2, 0.07, 1608, 99.08, 68.6, 18.4],
    ["Sudeste", 30.17, 36.8, 6.9, 1.44, 1751, 99.35, 70.1, 10.8],
    ["Sul", 24.71, 37.2, 5.8, 1.06, 1534, 99.32, 70.4, 11.3]
  ],
  products: [
    ["5G FWA", 17.55, 34.2, 4.7, 0.43, 1649, 99.14, 69.5, 16.5],
    ["Cloud Connect", 25.13, 38.6, 6.0, 0.82, 1647, 99.31, 70.4, 10.8],
    ["Fibra Corporativa", 24.12, 37.7, 5.7, 1.08, 1495, 99.32, 70.8, 11.1],
    ["SD-WAN", 22.56, 37.5, 5.6, 1.06, 1528, 99.32, 69.2, 12.7],
    ["Segurança Gerenciada", 19.33, 37.2, 4.8, 0.45, 1332, 99.34, 71.5, 10.7]
  ],
  segments: [
    ["Enterprise", 37.18, 37.2, 8.6, 1.13, 2533, 99.29, 69.6, 14.8],
    ["Governo", 28.78, 36.8, 7.0, 0.79, 2299, 99.28, 69.4, 15.7],
    ["Residencial Premium", 19.02, 37.8, 5.3, 0.62, 1362, 99.28, 70.0, 11.4],
    ["SMB", 23.70, 37.2, 5.9, 0.45, 1457, 99.28, 72.1, 7.5]
  ],
  channels: [
    ["Direto", 27.31, 37.6, 6.8, 0.75, 1829, 99.32, 70.6, 11.3],
    ["Field Sales", 27.15, 37.1, 6.7, 0.87, 2005, 99.26, 69.9, 13.2],
    ["Inside Sales", 27.13, 37.0, 6.6, 0.76, 1930, 99.28, 70.4, 12.7],
    ["Parceiros", 27.10, 37.2, 6.7, 0.78, 1887, 99.28, 70.3, 12.3]
  ],
  risk: [
    ["Norte", "5G FWA", 2.41, 34.4, 0.0, 349, 98.95, 67.7, 21.7],
    ["Norte", "SD-WAN", 2.99, 37.6, 0.0, 315, 99.11, 66.5, 19.1],
    ["Norte", "Fibra Corporativa", 3.16, 38.2, 0.12, 325, 99.07, 68.8, 18.3],
    ["Sul", "5G FWA", 3.97, 34.7, 0.90, 340, 99.12, 69.4, 17.2],
    ["Norte", "Cloud Connect", 3.33, 38.9, 0.22, 340, 99.13, 68.4, 16.8],
    ["Nordeste", "5G FWA", 3.35, 33.5, 0.11, 358, 99.18, 69.5, 16.0]
  ]
};

const PAGES = {
  executive: {
    title: "Visão Executiva",
    subtitle: "Cockpit executivo de telecom com receita, margem, base ativa e risco operacional.",
    focus: "Priorizar crescimento rentável com SLA acima do contratado.",
    kpis: [
      ["Receita total", `R$ ${DATA.total.receita.toFixed(1)} mi`, "+3,8% vs. plano", "var(--teal)"],
      ["Margem média", `${DATA.total.margemPct.toFixed(1)}%`, "rentabilidade saudável", "var(--green)"],
      ["Clientes ativos", `${DATA.total.clientes.toFixed(1)} mil`, "base consolidada", "var(--blue)"],
      ["NPS médio", DATA.total.nps.toFixed(1), "experiência sob controle", "var(--amber)"]
    ],
    panels: [
      ["Receita e margem por mês", "Tendência mensal com margem estabilizada e receita acima de R$ 8,7 mi.", lineChart(DATA.months, 1, 2, "R$ mi", "%")],
      ["Radar de atenção", "Risco combinado por região e produto.", riskTable(DATA.risk)]
    ],
    insight: "Leitura executiva: o Norte concentra o maior risco operacional, mas a margem segue positiva; a recomendação é atacar SLA e tickets antes de acelerar venda de 5G FWA."
  },
  revenue: {
    title: "Receita e Margem",
    subtitle: "Análise de monetização por produto, canal e rentabilidade operacional.",
    focus: "Proteger margem em produtos de alto crescimento.",
    kpis: [
      ["Receita", `R$ ${DATA.total.receita.toFixed(1)} mi`, "12 meses simulados", "var(--teal)"],
      ["Margem", `R$ ${DATA.total.margem.toFixed(1)} mi`, `${DATA.total.margemPct.toFixed(1)}% sobre receita`, "var(--green)"],
      ["Custo", `R$ ${DATA.total.custo.toFixed(1)} mi`, "pressão controlada", "var(--amber)"],
      ["Produto líder", "Cloud Connect", "38,6% de margem", "var(--blue)"]
    ],
    panels: [
      ["Mix por produto", "Receita e margem por linha de oferta.", barChart(DATA.products, 1, 2, "R$ mi", "%")],
      ["Canal e margem", "Canais com baixa dispersão, mas Field Sales exige controle de tickets.", table(DATA.channels, ["Canal", "Receita", "Margem", "Tickets"], r => [r[0], `R$ ${r[1].toFixed(1)} mi`, `${r[2].toFixed(1)}%`, r[5]])]
    ],
    insight: "Cloud Connect e Fibra Corporativa sustentam a rentabilidade. O plano comercial deve tratar 5G FWA como expansão seletiva, com preço e SLA amarrados."
  },
  customers: {
    title: "Clientes e Churn",
    subtitle: "Retenção, NPS e risco de perda por segmento e região.",
    focus: "Priorizar Governo e Enterprise onde o risco é mais alto.",
    kpis: [
      ["Clientes", `${DATA.total.clientes.toFixed(1)} mil`, "base ativa fictícia", "var(--teal)"],
      ["Churn", `${DATA.total.churnPct.toFixed(2)}%`, "baixo, mas concentrado", "var(--green)"],
      ["NPS", DATA.total.nps.toFixed(1), "zona neutra positiva", "var(--amber)"],
      ["Segmento risco", "Governo", "score 15,7", "var(--red)"]
    ],
    panels: [
      ["Base por segmento", "Distribuição da carteira e risco médio.", barChart(DATA.segments, 3, 8, "mil clientes", "risco")],
      ["Churn por região", "Sudeste e Sul merecem ação de retenção.", table(DATA.regions, ["Região", "Clientes", "Churn", "NPS"], r => [r[0], `${r[3].toFixed(1)} mil`, `${r[4].toFixed(2)}%`, r[7].toFixed(1)])]
    ],
    insight: "O churn total é baixo, mas há concentração no Sudeste e em ofertas corporativas. A ação recomendada é combinar health score, NPS e tickets para campanhas de retenção."
  },
  network: {
    title: "Rede e SLA",
    subtitle: "Disponibilidade, gap de SLA, tickets e saúde operacional.",
    focus: "Reduzir tickets no Norte e estabilizar 5G FWA.",
    kpis: [
      ["Uptime médio", `${DATA.total.uptime.toFixed(2)}%`, `SLA médio ${DATA.total.sla.toFixed(2)}%`, "var(--green)"],
      ["Tickets", DATA.total.tickets.toLocaleString("pt-BR"), "volume 12 meses", "var(--amber)"],
      ["Risco médio", DATA.total.risk.toFixed(1), "score consolidado", "var(--red)"],
      ["NPS operacional", DATA.total.nps.toFixed(1), "impactado por atendimento", "var(--teal)"]
    ],
    panels: [
      ["Uptime por região", "Norte fica no limite; demais regiões entregam folga operacional.", barChart(DATA.regions, 6, 8, "% uptime", "risco")],
      ["Tickets por produto", "Produtos com maior atrito operacional.", table(DATA.products, ["Produto", "Tickets", "Uptime", "Risco"], r => [r[0], r[5], `${r[6].toFixed(2)}%`, r[8].toFixed(1)])]
    ],
    insight: "A rede está acima do SLA médio, mas o Norte e 5G FWA geram risco desproporcional. A recomendação é abrir plano de capacidade e acompanhamento semanal de tickets."
  }
};

function chartFrame(title, copy, content) {
  return `<section class="panel"><div class="panel-header"><div><h2>${title}</h2><p class="panel-copy">${copy}</p></div><span class="status">online</span></div>${content}</section>`;
}

function lineChart(rows, y1, y2, leftLabel, rightLabel) {
  const w = 860, h = 315, p = 38;
  const values = rows.map(r => r[y1]);
  const values2 = rows.map(r => r[y2]);
  const min = Math.min(...values) * 0.97, max = Math.max(...values) * 1.03;
  const x = i => p + i * ((w - p * 2) / (rows.length - 1));
  const y = v => h - p - ((v - min) / (max - min)) * (h - p * 2);
  const points = rows.map((r, i) => `${x(i)},${y(r[y1])}`).join(" ");
  const area = `${p},${h - p} ${points} ${w - p},${h - p}`;
  const bars = rows.map((r, i) => {
    const bw = 30, bh = (r[y2] / 42) * 110;
    return `<rect class="bar alt" x="${x(i) - bw / 2}" y="${h - p - bh}" width="${bw}" height="${bh}" opacity=".52"></rect>`;
  }).join("");
  const labels = rows.map((r, i) => `<text class="tick" x="${x(i)}" y="${h - 8}" text-anchor="middle">${r[0]}</text>`).join("");
  return `<div class="chart tall"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${leftLabel} e ${rightLabel}">
    <defs><linearGradient id="barGradient" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#00B8A9"/><stop offset="1" stop-color="#004090"/></linearGradient></defs>
    ${[0, 1, 2, 3].map(i => `<line class="grid-line" x1="${p}" x2="${w - p}" y1="${p + i * 68}" y2="${p + i * 68}"></line>`).join("")}
    ${bars}<polygon class="area" points="${area}"></polygon><polyline class="line" points="${points}"></polyline>${labels}
  </svg></div>`;
}

function barChart(rows, primary, secondary, primaryLabel, secondaryLabel) {
  const sorted = [...rows].sort((a, b) => b[primary] - a[primary]);
  const max = Math.max(...sorted.map(r => r[primary]));
  return `<div class="chart">${sorted.map(r => {
    const width = Math.max(8, (r[primary] / max) * 100);
    return `<div style="margin:0 0 15px">
      <div style="display:flex;justify-content:space-between;gap:16px;font-size:13px"><strong>${r[0]}</strong><span style="color:var(--muted)">${r[primary].toFixed(secondary === 8 ? 2 : 1)} ${primaryLabel} · ${r[secondary].toFixed(1)} ${secondaryLabel}</span></div>
      <div style="height:12px;margin-top:8px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden"><div style="width:${width}%;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--teal),var(--blue))"></div></div>
    </div>`;
  }).join("")}</div>`;
}

function table(rows, headers, mapper) {
  return `<table class="table"><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${mapper(r).map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function riskTable(rows) {
  return table(rows, ["Região", "Produto", "Risco", "Uptime"], r => [r[0], r[1], r[8].toFixed(1), `${r[6].toFixed(2)}%`]);
}

function renderPage() {
  const key = document.body.dataset.page || "executive";
  const page = PAGES[key];
  document.title = `${page.title} | Rejoin BI`;
  document.querySelector("#app").innerHTML = `
    <main class="dashboard" id="canvas-root">
      <header class="hero">
        <div><span class="eyebrow">Rejoin BI · Canvas Pro</span><h1>${page.title}</h1><p class="subtitle">${page.subtitle}</p></div>
        <aside class="focus-card"><span class="eyebrow">Foco executivo</span><strong>${page.focus}</strong></aside>
      </header>
      <section class="kpi-grid">${page.kpis.map(([label, value, note, accent]) => `<article class="kpi" style="--accent:${accent}"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-note">${note}</div></article>`).join("")}</section>
      <section class="grid">${page.panels.map(p => chartFrame(...p)).join("")}</section>
      <section class="insight"><strong>Próxima decisão:</strong> ${page.insight}</section>
      <footer class="footer"><span>Fonte: Data Engine Canvas Executivo Pro · dados fictícios de telecom · atualização mensal</span><div class="filters"><span class="chip">Região</span><span class="chip">Produto</span><span class="chip">Segmento</span><span class="chip">Mês</span></div></footer>
    </main>`;
}

renderPage();
