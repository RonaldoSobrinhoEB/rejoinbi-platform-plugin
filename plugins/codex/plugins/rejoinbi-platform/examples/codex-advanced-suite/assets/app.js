const colors = ['#0f766e', '#3274a8', '#d89a26', '#d85c73', '#657468', '#6b5fa7'];

const data = {
  months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
  revenue: [4.2, 5.1, 5.8, 6.4, 7.5, 8.7],
  margin: [24, 26, 27, 28, 30, 32],
  forecast: [4.0, 4.9, 5.6, 6.1, 7.2, 8.1],
  channels: [
    { name: 'Organic', value: 34 },
    { name: 'Paid', value: 28 },
    { name: 'Partners', value: 18 },
    { name: 'Referral', value: 12 },
    { name: 'Events', value: 8 }
  ],
  funnel: [
    { stage: 'Leads', value: 4260 },
    { stage: 'Qualified', value: 1960 },
    { stage: 'Visits', value: 940 },
    { stage: 'Proposals', value: 410 },
    { stage: 'Closed', value: 118 }
  ],
  ops: [
    ['Foundation', 92],
    ['Structure', 78],
    ['Facade', 63],
    ['Finishing', 49],
    ['Delivery', 22]
  ],
  risks: [
    ['Supply delay', 'Medium', 'Procurement', 'Open'],
    ['Cost overrun', 'High', 'Finance', 'Mitigating'],
    ['License dependency', 'Medium', 'Legal', 'Tracking'],
    ['Lead quality drop', 'Low', 'Sales', 'Closed']
  ]
};

const charts = [];
const page = document.body.dataset.page || 'overview';

function metricCards(items) {
  document.getElementById('metrics').innerHTML = items.map(item => `
    <article class="metric">
      <div class="metric-label">${item.label}</div>
      <div class="metric-value">${item.value}</div>
      <div class="metric-delta">${item.delta}</div>
    </article>
  `).join('');
}

function panel(title, id, tall = false) {
  return `<article class="panel"><h2>${title}</h2><div id="${id}" class="chart ${tall ? 'tall' : ''}"></div></article>`;
}

function mountChart(id, option) {
  const element = document.getElementById(id);
  if (!element || !window.echarts) return;
  const chart = echarts.init(element);
  chart.setOption(option);
  charts.push(chart);
}

function renderOverview() {
  metricCards([
    { label: 'Revenue', value: 'R$ 8.7M', delta: '+14.2%' },
    { label: 'Margin', value: '32%', delta: '+4 pp' },
    { label: 'Lead volume', value: '4,260', delta: '+8.1%' },
    { label: 'Risk index', value: '2.4', delta: '-0.6' }
  ]);
  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Revenue and forecast', 'overviewTrend')}
      ${panel('Channel mix', 'overviewMix')}
    </section>
    <section class="grid-3">
      ${panel('Margin evolution', 'overviewMargin')}
      <article class="panel">
        <h2>Platform page binding</h2>
        <div class="notice">This dashboard is a standalone HTML page. Rejoin BI owns the menu, hierarchy, route, icon, and permissions through Gerenciar Paginas.</div>
        <div class="table-wrap"><table>
          <tr><th>Field</th><th>Value</th></tr>
          <tr><td>Arquivo HTML</td><td>overview.html</td></tr>
          <tr><td>Rota personalizada</td><td>codex-platform-overview</td></tr>
          <tr><td>Internal menu</td><td>None</td></tr>
        </table></div>
      </article>
      ${panel('Portfolio balance', 'overviewRadar')}
    </section>
  `;
  mountChart('overviewTrend', {
    color: colors,
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 42, right: 18, top: 46, bottom: 34 },
    xAxis: { type: 'category', data: data.months },
    yAxis: { type: 'value', axisLabel: { formatter: 'R$ {value}M' } },
    series: [
      { name: 'Revenue', type: 'line', smooth: true, areaStyle: { opacity: .12 }, data: data.revenue },
      { name: 'Forecast', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, data: data.forecast }
    ]
  });
  mountChart('overviewMix', {
    color: colors,
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['42%', '72%'], center: ['50%', '43%'], data: data.channels }]
  });
  mountChart('overviewMargin', {
    color: [colors[0]],
    grid: { left: 36, right: 12, top: 16, bottom: 28 },
    xAxis: { type: 'category', data: data.months },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{ type: 'bar', data: data.margin, barWidth: 18 }]
  });
  mountChart('overviewRadar', {
    color: [colors[1]],
    radar: { indicator: [
      { name: 'Sales', max: 100 },
      { name: 'Finance', max: 100 },
      { name: 'Ops', max: 100 },
      { name: 'People', max: 100 },
      { name: 'ESG', max: 100 }
    ] },
    series: [{ type: 'radar', data: [{ value: [86, 78, 72, 69, 81], name: 'Health' }] }]
  });
}

function renderSales() {
  metricCards([
    { label: 'Closed deals', value: '118', delta: '+11' },
    { label: 'Proposal value', value: 'R$ 31M', delta: '+18%' },
    { label: 'Visit rate', value: '48%', delta: '+5 pp' },
    { label: 'CAC trend', value: '-7%', delta: 'better' }
  ]);
  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Funnel conversion', 'salesFunnel', true)}
      ${panel('Lead quality by source', 'salesScatter', true)}
    </section>
    <article class="panel">
      <h2>Priority opportunities</h2>
      <div class="table-wrap"><table>
        <tr><th>Account</th><th>Segment</th><th>Score</th><th>Next action</th></tr>
        <tr><td>Alpha Towers</td><td>Residential</td><td>91</td><td>Contract review</td></tr>
        <tr><td>Livon South</td><td>Mixed use</td><td>86</td><td>Proposal adjustment</td></tr>
        <tr><td>Instituto Hub</td><td>Social</td><td>79</td><td>Executive visit</td></tr>
      </table></div>
    </article>
  `;
  mountChart('salesFunnel', {
    color: colors,
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: data.funnel.map(x => x.stage).reverse() },
    grid: { left: 90, right: 20, top: 20, bottom: 30 },
    series: [{ type: 'bar', data: data.funnel.map(x => x.value).reverse(), label: { show: true, position: 'right' } }]
  });
  mountChart('salesScatter', {
    color: [colors[3]],
    tooltip: { trigger: 'item' },
    grid: { left: 42, right: 18, top: 22, bottom: 36 },
    xAxis: { name: 'Volume' },
    yAxis: { name: 'Quality' },
    series: [{ type: 'scatter', symbolSize: value => Math.max(12, value[2] / 2), data: [[40, 72, 30], [64, 81, 42], [23, 88, 18], [52, 66, 24], [78, 74, 38]] }]
  });
}

function renderOperations() {
  metricCards([
    { label: 'On-time workfronts', value: '82%', delta: '+6 pp' },
    { label: 'Quality index', value: '94', delta: '+2' },
    { label: 'Open risks', value: '7', delta: '-3' },
    { label: 'SLA breaches', value: '2', delta: '-1' }
  ]);
  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Workfront completion', 'opsProgress')}
      ${panel('Risk heatmap', 'opsHeatmap')}
    </section>
    <article class="panel">
      <h2>Risk register</h2>
      <div class="table-wrap"><table>
        <tr><th>Risk</th><th>Severity</th><th>Owner</th><th>Status</th></tr>
        ${data.risks.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}
      </table></div>
    </article>
  `;
  mountChart('opsProgress', {
    color: colors,
    tooltip: {},
    xAxis: { type: 'value', max: 100 },
    yAxis: { type: 'category', data: data.ops.map(x => x[0]).reverse() },
    grid: { left: 92, right: 20, top: 20, bottom: 30 },
    series: [{ type: 'bar', data: data.ops.map(x => x[1]).reverse(), label: { show: true, formatter: '{c}%' } }]
  });
  mountChart('opsHeatmap', {
    color: colors,
    tooltip: {},
    grid: { left: 60, right: 20, top: 20, bottom: 45 },
    xAxis: { type: 'category', data: ['Cost', 'Schedule', 'Quality', 'Safety'] },
    yAxis: { type: 'category', data: ['Low', 'Medium', 'High'] },
    visualMap: { min: 0, max: 10, orient: 'horizontal', left: 'center', bottom: 0 },
    series: [{ type: 'heatmap', data: [[0,0,2],[1,0,4],[2,0,3],[3,0,1],[0,1,5],[1,1,7],[2,1,5],[3,1,4],[0,2,8],[1,2,9],[2,2,6],[3,2,5]], label: { show: true } }]
  });
}

function storedRecords() {
  return JSON.parse(window.localStorage.getItem('codex-platform-page-records') || '[]');
}

function saveRecords(records) {
  window.localStorage.setItem('codex-platform-page-records', JSON.stringify(records));
}

function renderRecordTable() {
  const records = storedRecords();
  const target = document.getElementById('records');
  target.innerHTML = records.length ? `
    <table>
      <tr><th>Type</th><th>Name</th><th>Value</th><th>Owner</th></tr>
      ${records.map(row => `<tr><td>${row.type}</td><td>${row.name}</td><td>${row.value}</td><td>${row.owner}</td></tr>`).join('')}
    </table>
  ` : '<div class="notice">No local records yet. Submit a scenario, lead, or risk to validate the form flow.</div>';
}

function bindForm(id, type) {
  document.getElementById(id).addEventListener('submit', event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    const records = storedRecords();
    records.unshift({ type, name: values.name, value: values.value, owner: values.owner, notes: values.notes, savedAt: new Date().toISOString() });
    saveRecords(records.slice(0, 20));
    renderForms();
  });
}

function renderForms() {
  metricCards([
    { label: 'Draft records', value: String(storedRecords().length), delta: 'local storage' },
    { label: 'Validated forms', value: '3', delta: 'scenario + lead + risk' },
    { label: 'Export format', value: 'JSON', delta: 'ready' },
    { label: 'Platform page', value: 'forms.html', delta: 'single route' }
  ]);
  document.getElementById('view').innerHTML = `
    <section class="form-grid">
      <form id="scenarioForm" class="form-panel">
        <h2>Scenario planner</h2>
        <label><span>Scenario name</span><input name="name" required value="Aggressive launch"></label>
        <label><span>Projected value</span><input name="value" type="number" min="1" required value="8700000"></label>
        <label><span>Owner</span><input name="owner" required value="Finance"></label>
        <label><span>Notes</span><textarea name="notes">Stress test revenue and margin assumptions.</textarea></label>
        <div class="form-actions"><button type="submit">Save scenario</button><button type="button" class="secondary" data-export>Export JSON</button></div>
      </form>
      <form id="leadForm" class="form-panel">
        <h2>Lead intake</h2>
        <label><span>Lead name</span><input name="name" required value="North Garden"></label>
        <label><span>Score</span><input name="value" type="number" min="0" max="100" required value="84"></label>
        <label><span>Owner</span><input name="owner" required value="Sales"></label>
        <label><span>Qualification memo</span><textarea name="notes">High-intent inbound lead with financing fit.</textarea></label>
        <div class="form-actions"><button type="submit">Save lead</button><button type="button" class="secondary" data-clear>Clear local data</button></div>
      </form>
    </section>
    <form id="riskForm" class="form-panel">
      <h2>Risk register form</h2>
      <div class="form-grid">
        <label><span>Risk name</span><input name="name" required value="Vendor bottleneck"></label>
        <label><span>Impact score</span><input name="value" type="number" min="1" max="10" required value="7"></label>
        <label><span>Owner</span><input name="owner" required value="Operations"></label>
        <label><span>Mitigation</span><input name="notes" value="Add alternate supplier and weekly status review."></label>
      </div>
      <div class="form-actions"><button type="submit">Save risk</button></div>
    </form>
    <article class="panel">
      <h2>Stored records</h2>
      <div id="records" class="table-wrap"></div>
    </article>
  `;
  bindForm('scenarioForm', 'Scenario');
  bindForm('leadForm', 'Lead');
  bindForm('riskForm', 'Risk');
  document.querySelector('[data-clear]').addEventListener('click', () => { saveRecords([]); renderForms(); });
  document.querySelector('[data-export]').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(storedRecords(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'codex-platform-page-records.json';
    link.click();
    URL.revokeObjectURL(url);
  });
  renderRecordTable();
}

function render() {
  if (page === 'sales') renderSales();
  else if (page === 'operations') renderOperations();
  else if (page === 'forms') renderForms();
  else renderOverview();
}

window.addEventListener('resize', () => charts.forEach(chart => chart.resize()));
render();
