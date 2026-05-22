const palette = {
  teal: '#0f766e',
  tealDeep: '#095f59',
  blue: '#3b74ad',
  amber: '#c88722',
  rose: '#ca4f66',
  violet: '#7257b4',
  slate: '#52635e',
  mint: '#6aa98f',
  canvas: '#f3f8f6',
  line: '#d9e5df',
  ink: '#17231f',
  muted: '#65746f'
};

const page = document.body.dataset.page || 'overview';
let charts = [];

const contextMultipliers = {
  '2026 Q1': 0.92,
  '2026 Q2': 1,
  '2026 Q3': 1.08,
  'All units': 1,
  ADN: 1.06,
  Livon: 0.94,
  Instituto: 0.82
};

const model = {
  months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
  revenue: [4.2, 5.1, 5.8, 6.4, 7.5, 8.7],
  target: [4.0, 4.9, 5.6, 6.1, 7.2, 8.1],
  margin: [24, 26, 27, 28, 30, 32],
  cash: [1.4, 1.8, 2.1, 2.4, 2.9, 3.3],
  pipeline: [4260, 1960, 940, 410, 118],
  stages: ['Leads', 'Qualified', 'Visits', 'Proposals', 'Closed'],
  channels: [
    { name: 'Organic', value: 34 },
    { name: 'Paid', value: 28 },
    { name: 'Partners', value: 18 },
    { name: 'Referral', value: 12 },
    { name: 'Events', value: 8 }
  ],
  portfolio: [
    ['ADN Prime', 'Residential', 'R$ 12.4M', 'High', 'Contract'],
    ['Livon Sul', 'Mixed use', 'R$ 8.1M', 'Medium', 'Proposal'],
    ['Instituto Hub', 'Social', 'R$ 3.9M', 'Low', 'Visit'],
    ['Norte Garden', 'Residential', 'R$ 6.7M', 'Medium', 'Finance']
  ],
  workfronts: [
    ['Foundation', 92, 84],
    ['Structure', 78, 75],
    ['Facade', 63, 69],
    ['Finishing', 49, 58],
    ['Delivery', 22, 35]
  ],
  risks: [
    ['Supply delay', 'Medium', 'Procurement', 'Mitigating'],
    ['Cost overrun', 'High', 'Finance', 'Open'],
    ['License dependency', 'Medium', 'Legal', 'Tracking'],
    ['Lead quality drop', 'Low', 'Sales', 'Closed'],
    ['Crew availability', 'High', 'Operations', 'Escalated']
  ],
  capacity: {
    teams: ['Engineering', 'Sales', 'Finance', 'Ops', 'CX'],
    planned: [86, 72, 64, 91, 58],
    used: [78, 66, 51, 83, 46]
  }
};

function selectedContext() {
  const period = document.getElementById('periodFilter')?.value || '2026 Q2';
  const unit = document.getElementById('unitFilter')?.value || 'All units';
  const factor = (contextMultipliers[period] || 1) * (contextMultipliers[unit] || 1);
  return { period, unit, factor };
}

function money(value) {
  return `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}M`;
}

function intFormat(value) {
  return Math.round(value).toLocaleString('pt-BR');
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function toneFor(value) {
  const normalized = String(value || '').toLowerCase();
  if (normalized.includes('high') || normalized.includes('open') || normalized.includes('escalated')) return 'high';
  if (normalized.includes('medium') || normalized.includes('tracking') || normalized.includes('mitigating')) return 'medium';
  return 'good';
}

function metricCards(items) {
  const target = document.getElementById('metrics');
  target.innerHTML = items.map((item, index) => `
    <article class="metric" style="--metric-hue:${item.hue || [178, 245, 75, 15][index % 4]}">
      <div class="metric-label">${escapeHtml(item.label)}</div>
      <div class="metric-value">${escapeHtml(item.value)}</div>
      <div class="metric-delta" data-tone="${escapeHtml(item.tone || 'good')}">${escapeHtml(item.delta)}</div>
    </article>
  `).join('');
}

function panel(title, subtitle, id, options = {}) {
  const chartClass = ['chart', options.tall ? 'tall' : '', options.short ? 'short' : ''].filter(Boolean).join(' ');
  const panelClass = ['panel', options.featured ? 'is-featured' : ''].filter(Boolean).join(' ');
  const badge = options.badge ? `<span class="badge">${escapeHtml(options.badge)}</span>` : '';
  return `
    <article class="${panelClass}">
      <header class="panel-head">
        <div class="panel-title">
          <h2>${escapeHtml(title)}</h2>
          <p class="panel-subtitle">${escapeHtml(subtitle)}</p>
        </div>
        ${badge}
      </header>
      <div id="${id}" class="${chartClass}"></div>
    </article>
  `;
}

function table(headers, rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

function decisionList(items) {
  return `
    <div class="decision-list">
      ${items.map((item, index) => `
        <div class="decision-item">
          <span class="rank">${index + 1}</span>
          <span class="decision-copy">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.detail)}</span>
          </span>
          <span class="tone-pill" data-tone="${escapeHtml(item.tone || 'good')}">${escapeHtml(item.tag)}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function chartTheme() {
  return {
    color: [palette.teal, palette.blue, palette.amber, palette.rose, palette.violet, palette.mint],
    textStyle: { color: palette.ink, fontFamily: 'Inter, Segoe UI, system-ui, sans-serif' },
    grid: { left: 48, right: 20, top: 42, bottom: 38, containLabel: true },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(248, 252, 250, 0.96)',
      borderColor: palette.line,
      textStyle: { color: palette.ink }
    },
    legend: { top: 0, icon: 'roundRect', textStyle: { color: palette.muted } },
    xAxis: {
      axisLine: { lineStyle: { color: palette.line } },
      axisTick: { show: false },
      axisLabel: { color: palette.muted },
      splitLine: { show: false }
    },
    yAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: palette.muted },
      splitLine: { lineStyle: { color: palette.line } }
    }
  };
}

function mountChart(id, option) {
  const element = document.getElementById(id);
  if (!element || !window.echarts) return;
  const chart = echarts.init(element, null, { renderer: 'canvas' });
  chart.setOption(option);
  charts.push(chart);
}

function clearCharts() {
  charts.forEach(chart => chart.dispose());
  charts = [];
}

function scaledSeries(values, factor, digits = 1) {
  return values.map(value => Number((value * factor).toFixed(digits)));
}

function renderOverview() {
  const { factor, period, unit } = selectedContext();
  const revenue = scaledSeries(model.revenue, factor);
  const target = scaledSeries(model.target, factor);
  const cash = scaledSeries(model.cash, factor);
  metricCards([
    { label: 'Net revenue', value: money(revenue.at(-1)), delta: `${period} ${unit}`, hue: 178 },
    { label: 'Gross margin', value: `${Math.round(model.margin.at(-1) + (factor - 1) * 4)}%`, delta: '+4 pp vs plan', hue: 155 },
    { label: 'Qualified demand', value: intFormat(model.pipeline[1] * factor), delta: '+12.4% quality lift', hue: 245 },
    { label: 'Risk exposure', value: '2.1', delta: '-0.5 after mitigations', tone: 'watch', hue: 75 }
  ]);

  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Revenue momentum', 'Actuals, plan and cash generation by month.', 'overviewTrend', { featured: true, tall: true, badge: 'Executive' })}
      <article class="panel">
        <header class="panel-head">
          <div class="panel-title">
            <h2>Decision queue</h2>
            <p class="panel-subtitle">Highest leverage choices for the selected context.</p>
          </div>
          <span class="badge">4 items</span>
        </header>
        ${decisionList([
          { title: 'Release additional sales capacity', detail: 'The pipeline is ahead of plan, but conversion is constrained by follow-up SLA.', tag: 'High', tone: 'high' },
          { title: 'Protect Q3 gross margin', detail: 'Cost pressure is visible in finishing and procurement packages.', tag: 'Medium', tone: 'medium' },
          { title: 'Prioritize Instituto Hub', detail: 'Lower value, strong social return and clean delivery path.', tag: 'Good', tone: 'good' },
          { title: 'Reforecast cash runway', detail: 'Cash generation improved after April and can fund one controlled acceleration.', tag: 'Good', tone: 'good' }
        ])}
      </article>
    </section>
    <section class="grid-3">
      ${panel('Portfolio health', 'Balanced score across commercial and delivery dimensions.', 'overviewRadar')}
      ${panel('Channel contribution', 'Weighted demand source mix.', 'overviewMix')}
      <article class="panel">
        <header class="panel-head">
          <div class="panel-title">
            <h2>Priority portfolio</h2>
            <p class="panel-subtitle">Accounts with material impact this cycle.</p>
          </div>
        </header>
        ${table(['Account', 'Segment', 'Value', 'Signal', 'Next'], model.portfolio.map(row => [
          escapeHtml(row[0]),
          escapeHtml(row[1]),
          escapeHtml(row[2]),
          `<span class="status-pill" data-tone="${toneFor(row[3])}">${escapeHtml(row[3])}</span>`,
          escapeHtml(row[4])
        ]))}
      </article>
    </section>
  `;

  const theme = chartTheme();
  mountChart('overviewTrend', {
    ...theme,
    tooltip: { ...theme.tooltip, trigger: 'axis' },
    xAxis: { ...theme.xAxis, type: 'category', boundaryGap: false, data: model.months },
    yAxis: { ...theme.yAxis, type: 'value', axisLabel: { formatter: 'R$ {value}M' } },
    series: [
      {
        name: 'Actual',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { width: 3 },
        areaStyle: { opacity: 0.16, color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#0f766e55' }, { offset: 1, color: '#0f766e05' }]) },
        data: revenue
      },
      { name: 'Plan', type: 'line', smooth: true, lineStyle: { width: 2, type: 'dashed' }, data: target },
      { name: 'Cash', type: 'bar', yAxisIndex: 0, barWidth: 14, itemStyle: { borderRadius: [4, 4, 0, 0] }, data: cash }
    ]
  });
  mountChart('overviewRadar', {
    ...theme,
    tooltip: { trigger: 'item' },
    radar: {
      radius: '64%',
      axisName: { color: palette.muted },
      splitLine: { lineStyle: { color: palette.line } },
      splitArea: { areaStyle: { color: ['rgba(15,118,110,0.04)', 'rgba(59,116,173,0.03)'] } },
      indicator: [
        { name: 'Sales', max: 100 },
        { name: 'Finance', max: 100 },
        { name: 'Ops', max: 100 },
        { name: 'People', max: 100 },
        { name: 'Impact', max: 100 }
      ]
    },
    series: [{ type: 'radar', data: [{ value: [88, 81, 74, 69, 86], name: 'Health' }], areaStyle: { opacity: 0.18 } }]
  });
  mountChart('overviewMix', {
    ...theme,
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle' },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#f8fcfa', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%', color: palette.ink },
      data: model.channels.map(item => ({ ...item, value: Number((item.value * factor).toFixed(1)) }))
    }]
  });
}

function renderSales() {
  const { factor } = selectedContext();
  const funnel = model.pipeline.map(value => Math.round(value * factor));
  metricCards([
    { label: 'Closed deals', value: intFormat(funnel.at(-1)), delta: '+11 vs previous cycle', hue: 178 },
    { label: 'Weighted pipeline', value: money(31.2 * factor), delta: '+18% qualified value', hue: 245 },
    { label: 'Visit rate', value: '48%', delta: '+5 pp from SLA work', hue: 155 },
    { label: 'Acquisition cost', value: '-7%', delta: 'Improved efficiency', hue: 75 }
  ]);

  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Conversion architecture', 'Stage volume and conversion pressure points.', 'salesFunnel', { featured: true, tall: true, badge: 'Pipeline' })}
      ${panel('Lead quality map', 'Quality by lead volume, segment and projected value.', 'salesScatter', { tall: true })}
    </section>
    <section class="grid-2">
      ${panel('Channel cohort', 'Acquisition strength by source and stage.', 'salesHeatmap')}
      <article class="panel">
        <header class="panel-head">
          <div class="panel-title">
            <h2>Opportunity board</h2>
            <p class="panel-subtitle">Next best actions with owner context.</p>
          </div>
        </header>
        ${table(['Account', 'Segment', 'Score', 'Owner', 'Action'], [
          ['Alpha Towers', 'Residential', '<span class="status-pill" data-tone="good">91</span>', 'Sales', 'Contract review'],
          ['Livon South', 'Mixed use', '<span class="status-pill" data-tone="medium">86</span>', 'Revenue Ops', 'Proposal adjustment'],
          ['Instituto Hub', 'Social', '<span class="status-pill" data-tone="medium">79</span>', 'Executive', 'Sponsor visit'],
          ['Norte Garden', 'Residential', '<span class="status-pill" data-tone="high">74</span>', 'Finance', 'Credit review']
        ])}
      </article>
    </section>
  `;

  const theme = chartTheme();
  mountChart('salesFunnel', {
    ...theme,
    tooltip: { ...theme.tooltip, trigger: 'axis' },
    grid: { left: 112, right: 24, top: 32, bottom: 38 },
    xAxis: { ...theme.xAxis, type: 'value' },
    yAxis: { ...theme.yAxis, type: 'category', data: model.stages.slice().reverse() },
    series: [{
      name: 'Volume',
      type: 'bar',
      data: funnel.slice().reverse(),
      barWidth: 22,
      itemStyle: { borderRadius: [0, 6, 6, 0] },
      label: { show: true, position: 'right', color: palette.ink }
    }]
  });
  mountChart('salesScatter', {
    ...theme,
    tooltip: { trigger: 'item', formatter: params => `${params.data[3]}<br>Volume: ${params.data[0]}<br>Quality: ${params.data[1]}<br>Value: R$ ${params.data[2]}M` },
    xAxis: { ...theme.xAxis, name: 'Lead volume', nameTextStyle: { color: palette.muted } },
    yAxis: { ...theme.yAxis, name: 'Quality score', nameTextStyle: { color: palette.muted }, max: 100 },
    series: [{
      type: 'scatter',
      symbolSize: value => Math.max(18, value[2] * 2.2),
      data: [
        [40, 72, 7.4, 'Residential inbound'],
        [64, 81, 10.2, 'Partner referral'],
        [23, 88, 6.1, 'Executive network'],
        [52, 66, 4.7, 'Paid search'],
        [78, 74, 8.8, 'Events']
      ],
      itemStyle: { opacity: 0.82 }
    }]
  });
  mountChart('salesHeatmap', {
    ...theme,
    tooltip: { position: 'top' },
    grid: { left: 92, right: 24, top: 30, bottom: 54 },
    xAxis: { ...theme.xAxis, type: 'category', data: model.stages },
    yAxis: { ...theme.yAxis, type: 'category', data: ['Organic', 'Paid', 'Partners', 'Referral'] },
    visualMap: { min: 0, max: 100, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#ecf6f2', palette.teal] } },
    series: [{
      type: 'heatmap',
      label: { show: true, color: palette.ink },
      data: [
        [0, 0, 82], [1, 0, 58], [2, 0, 44], [3, 0, 31], [4, 0, 18],
        [0, 1, 76], [1, 1, 62], [2, 1, 39], [3, 1, 26], [4, 1, 12],
        [0, 2, 64], [1, 2, 71], [2, 2, 52], [3, 2, 33], [4, 2, 21],
        [0, 3, 45], [1, 3, 50], [2, 3, 41], [3, 3, 28], [4, 3, 15]
      ]
    }]
  });
}

function renderOperations() {
  metricCards([
    { label: 'On-time workfronts', value: '82%', delta: '+6 pp delivery reliability', hue: 178 },
    { label: 'Quality index', value: '94', delta: '+2 after inspections', hue: 155 },
    { label: 'Open risks', value: '7', delta: '-3 after closure', tone: 'watch', hue: 75 },
    { label: 'SLA breaches', value: '2', delta: '-1 this cycle', tone: 'down', hue: 15 }
  ]);

  document.getElementById('view').innerHTML = `
    <section class="grid-2">
      ${panel('Workfront control', 'Actual progress compared with plan.', 'opsProgress', { featured: true, tall: true, badge: 'Delivery' })}
      ${panel('Capacity discipline', 'Planned allocation and current utilization.', 'opsCapacity', { tall: true })}
    </section>
    <section class="grid-2">
      ${panel('Risk heatmap', 'Severity distribution by risk family.', 'opsHeatmap')}
      <article class="panel">
        <header class="panel-head">
          <div class="panel-title">
            <h2>Risk register</h2>
            <p class="panel-subtitle">Open operational items with accountable owners.</p>
          </div>
        </header>
        ${table(['Risk', 'Severity', 'Owner', 'Status'], model.risks.map(row => [
          escapeHtml(row[0]),
          `<span class="status-pill" data-tone="${toneFor(row[1])}">${escapeHtml(row[1])}</span>`,
          escapeHtml(row[2]),
          `<span class="tone-pill" data-tone="${toneFor(row[3])}">${escapeHtml(row[3])}</span>`
        ]))}
      </article>
    </section>
  `;

  const theme = chartTheme();
  mountChart('opsProgress', {
    ...theme,
    tooltip: { ...theme.tooltip, trigger: 'axis' },
    grid: { left: 104, right: 28, top: 36, bottom: 38 },
    xAxis: { ...theme.xAxis, type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { ...theme.yAxis, type: 'category', data: model.workfronts.map(item => item[0]).reverse() },
    series: [
      { name: 'Plan', type: 'bar', barGap: '-100%', data: model.workfronts.map(item => item[2]).reverse(), itemStyle: { color: '#dce8e3', borderRadius: [0, 6, 6, 0] }, barWidth: 24 },
      { name: 'Actual', type: 'bar', data: model.workfronts.map(item => item[1]).reverse(), itemStyle: { color: palette.teal, borderRadius: [0, 6, 6, 0] }, barWidth: 16, label: { show: true, position: 'right', formatter: '{c}%' } }
    ]
  });
  mountChart('opsCapacity', {
    ...theme,
    tooltip: { ...theme.tooltip, trigger: 'axis' },
    xAxis: { ...theme.xAxis, type: 'category', data: model.capacity.teams },
    yAxis: { ...theme.yAxis, type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      { name: 'Used', type: 'bar', stack: 'capacity', data: model.capacity.used, itemStyle: { borderRadius: [5, 5, 0, 0] } },
      { name: 'Open', type: 'bar', stack: 'capacity', data: model.capacity.planned.map((plan, i) => plan - model.capacity.used[i]), itemStyle: { color: '#dce8e3' } },
      { name: 'Ceiling', type: 'line', data: [92, 88, 78, 96, 72], smooth: true, lineStyle: { type: 'dashed' } }
    ]
  });
  mountChart('opsHeatmap', {
    ...theme,
    tooltip: { position: 'top' },
    grid: { left: 84, right: 24, top: 28, bottom: 54 },
    xAxis: { ...theme.xAxis, type: 'category', data: ['Cost', 'Schedule', 'Quality', 'Safety'] },
    yAxis: { ...theme.yAxis, type: 'category', data: ['Low', 'Medium', 'High'] },
    visualMap: { min: 0, max: 10, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#eef6f3', '#d3a546', '#c24d61'] } },
    series: [{ type: 'heatmap', data: [[0, 0, 2], [1, 0, 4], [2, 0, 3], [3, 0, 1], [0, 1, 5], [1, 1, 7], [2, 1, 5], [3, 1, 4], [0, 2, 8], [1, 2, 9], [2, 2, 6], [3, 2, 5]], label: { show: true, color: palette.ink } }]
  });
}

function storedRecords() {
  return JSON.parse(window.localStorage.getItem('codex-platform-page-records') || '[]');
}

function saveRecords(records) {
  window.localStorage.setItem('codex-platform-page-records', JSON.stringify(records));
}

function validateForm(form) {
  let valid = true;
  form.querySelectorAll('.error-text').forEach(node => { node.textContent = ''; });
  form.querySelectorAll('.field-error').forEach(node => node.classList.remove('field-error'));
  form.querySelectorAll('[required], input[type="number"]').forEach(input => {
    const wrapper = input.closest('label') || input.parentElement;
    const error = wrapper.querySelector('.error-text');
    const value = String(input.value || '').trim();
    let message = '';
    if (input.required && !value) message = 'Required field';
    if (!message && input.type === 'number') {
      const number = Number(value);
      const min = input.min !== '' ? Number(input.min) : null;
      const max = input.max !== '' ? Number(input.max) : null;
      if (Number.isNaN(number)) message = 'Use a valid number';
      else if (min !== null && number < min) message = `Minimum ${min}`;
      else if (max !== null && number > max) message = `Maximum ${max}`;
    }
    if (message) {
      valid = false;
      wrapper.classList.add('field-error');
      if (error) error.textContent = message;
    }
  });
  return valid;
}

function addRecord(type, values) {
  const records = storedRecords();
  records.unshift({
    type,
    name: values.name,
    value: values.value,
    owner: values.owner,
    priority: values.priority || 'Medium',
    notes: values.notes,
    savedAt: new Date().toISOString()
  });
  saveRecords(records.slice(0, 24));
}

function renderRecordTable() {
  const records = storedRecords();
  const target = document.getElementById('records');
  const toolbarCount = document.getElementById('recordCount');
  if (toolbarCount) toolbarCount.textContent = `${records.length} saved`;
  if (!target) return;
  target.innerHTML = records.length ? table(['Type', 'Name', 'Value', 'Owner', 'Priority'], records.map(row => [
    escapeHtml(row.type),
    escapeHtml(row.name),
    escapeHtml(row.value),
    escapeHtml(row.owner),
    `<span class="status-pill" data-tone="${toneFor(row.priority)}">${escapeHtml(row.priority)}</span>`
  ])) : '<div class="notice">No saved records in this browser yet.</div>';
}

function bindSmartForm(id, type) {
  const form = document.getElementById(id);
  if (!form) return;
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!validateForm(form)) return;
    const values = Object.fromEntries(new FormData(form).entries());
    addRecord(type, values);
    const toast = form.querySelector('.toast');
    if (toast) {
      toast.textContent = `${type} saved locally`;
      toast.classList.add('is-visible');
      setTimeout(() => toast.classList.remove('is-visible'), 2400);
    }
    renderRecordTable();
    updateScenarioGauge();
  });
}

function updateScenarioGauge() {
  const chartNode = document.getElementById('scenarioGauge');
  if (!chartNode || !window.echarts) return;
  const records = storedRecords();
  const score = Math.min(98, 62 + records.length * 4);
  const existing = echarts.getInstanceByDom(chartNode);
  const chart = existing || echarts.init(chartNode);
  if (!existing) charts.push(chart);
  chart.setOption({
    color: [palette.teal],
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      radius: '92%',
      progress: { show: true, roundCap: true, width: 14 },
      axisLine: { lineStyle: { width: 14, color: [[1, '#dce8e3']] } },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: { valueAnimation: true, formatter: '{value}', color: palette.ink, fontSize: 34, fontWeight: 800 },
      title: { offsetCenter: [0, '64%'], color: palette.muted, fontSize: 12 },
      data: [{ value: score, name: 'Readiness score' }]
    }]
  });
}

function renderForms() {
  const records = storedRecords();
  metricCards([
    { label: 'Draft records', value: String(records.length), delta: 'Stored in this browser', hue: 178 },
    { label: 'Form coverage', value: '3 flows', delta: 'Scenario, lead, risk', hue: 245 },
    { label: 'Export format', value: 'JSON', delta: 'Ready for API handoff', hue: 155 },
    { label: 'Page file', value: 'forms.html', delta: 'Single platform route', hue: 75 }
  ]);

  document.getElementById('view').innerHTML = `
    <section class="form-grid">
      <form id="scenarioForm" class="form-panel" novalidate>
        <header class="panel-head">
          <div class="panel-title">
            <h2>Scenario planner</h2>
            <p class="panel-subtitle">Capture a business assumption and owner.</p>
          </div>
          <span class="badge">Finance</span>
        </header>
        <div class="field-grid">
          <label><span>Scenario name</span><input name="name" required value="Accelerated launch"><small class="error-text"></small></label>
          <label><span>Projected value</span><input name="value" type="number" min="1" required value="8700000"><small class="error-text"></small></label>
          <label><span>Owner</span><input name="owner" required value="Finance"><small class="error-text"></small></label>
          <label><span>Priority</span><select name="priority"><option>High</option><option selected>Medium</option><option>Low</option></select><small class="error-text"></small></label>
          <label class="field-full"><span>Notes</span><textarea name="notes" required>Stress test revenue and margin assumptions for Q3.</textarea><small class="error-text"></small></label>
        </div>
        <div class="form-actions"><button type="submit">Save scenario</button><button type="button" class="secondary" data-export>Export JSON</button></div>
        <div class="toast" role="status"></div>
      </form>

      <article class="panel">
        <header class="panel-head">
          <div class="panel-title">
            <h2>Scenario quality</h2>
            <p class="panel-subtitle">Local readiness signal based on saved records.</p>
          </div>
        </header>
        <div id="scenarioGauge" class="chart short"></div>
        <div class="quality-meter">
          <div class="meter-row"><span>Completeness</span><span class="meter-track"><span class="meter-fill" style="width:86%"></span></span><strong>86</strong></div>
          <div class="meter-row"><span>Ownership</span><span class="meter-track"><span class="meter-fill" style="width:74%"></span></span><strong>74</strong></div>
          <div class="meter-row"><span>Decision fit</span><span class="meter-track"><span class="meter-fill" style="width:91%"></span></span><strong>91</strong></div>
        </div>
      </article>
    </section>

    <section class="grid-2">
      <form id="leadForm" class="form-panel" novalidate>
        <header class="panel-head">
          <div class="panel-title">
            <h2>Lead intake</h2>
            <p class="panel-subtitle">Qualify an opportunity before it enters the pipeline.</p>
          </div>
        </header>
        <div class="field-grid">
          <label><span>Lead name</span><input name="name" required value="North Garden"><small class="error-text"></small></label>
          <label><span>Score</span><input name="value" type="number" min="0" max="100" required value="84"><small class="error-text"></small></label>
          <label><span>Owner</span><input name="owner" required value="Sales"><small class="error-text"></small></label>
          <label><span>Priority</span><select name="priority"><option selected>High</option><option>Medium</option><option>Low</option></select><small class="error-text"></small></label>
          <label class="field-full"><span>Qualification memo</span><textarea name="notes" required>High-intent inbound lead with financing fit.</textarea><small class="error-text"></small></label>
        </div>
        <div class="form-actions"><button type="submit">Save lead</button></div>
        <div class="toast" role="status"></div>
      </form>

      <form id="riskForm" class="form-panel" novalidate>
        <header class="panel-head">
          <div class="panel-title">
            <h2>Risk register</h2>
            <p class="panel-subtitle">Log operational exposure with a clear mitigation owner.</p>
          </div>
        </header>
        <div class="field-grid">
          <label><span>Risk name</span><input name="name" required value="Vendor bottleneck"><small class="error-text"></small></label>
          <label><span>Impact score</span><input name="value" type="number" min="1" max="10" required value="7"><small class="error-text"></small></label>
          <label><span>Owner</span><input name="owner" required value="Operations"><small class="error-text"></small></label>
          <label><span>Priority</span><select name="priority"><option selected>High</option><option>Medium</option><option>Low</option></select><small class="error-text"></small></label>
          <label class="field-full"><span>Mitigation</span><textarea name="notes" required>Add alternate supplier and weekly status review.</textarea><small class="error-text"></small></label>
        </div>
        <div class="form-actions"><button type="submit">Save risk</button></div>
        <div class="toast" role="status"></div>
      </form>
    </section>

    <article class="panel">
      <div class="record-toolbar">
        <div class="panel-title">
          <h2>Saved records</h2>
          <p class="panel-subtitle">Browser-local data for validating form behavior.</p>
        </div>
        <div class="form-actions">
          <span id="recordCount" class="badge">${records.length} saved</span>
          <button type="button" class="secondary" data-clear>Clear data</button>
        </div>
      </div>
      <div id="records"></div>
    </article>
  `;

  bindSmartForm('scenarioForm', 'Scenario');
  bindSmartForm('leadForm', 'Lead');
  bindSmartForm('riskForm', 'Risk');
  document.querySelector('[data-clear]').addEventListener('click', () => {
    saveRecords([]);
    renderForms();
  });
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
  updateScenarioGauge();
}

function render() {
  clearCharts();
  if (page === 'sales') renderSales();
  else if (page === 'operations') renderOperations();
  else if (page === 'forms') renderForms();
  else renderOverview();
}

document.querySelectorAll('#periodFilter, #unitFilter').forEach(control => {
  control.addEventListener('change', render);
});

window.addEventListener('resize', () => charts.forEach(chart => chart.resize()));
render();
