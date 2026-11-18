(() => {
  const chart = document.getElementById('chart');
  const select = document.getElementById('metric-select');
  if (!chart || !select) return;

  function esc(value) {
    return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async function refresh() {
    const url = chart.dataset.url + '?metric=' + encodeURIComponent(select.value) + '&limit=500';
    try {
      const response = await fetch(url, {cache: 'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      draw(data.points || [], data.label || data.metric || select.value);
    } catch (_) {
      chart.innerHTML = '<p class="empty">Não foi possível atualizar o gráfico.</p>';
    }
  }

  function draw(points, metric) {
    if (points.length < 2) {
      chart.innerHTML = '<p class="empty">Aguardando pelo menos duas medições de ' + esc(metric) + '.</p>';
      return;
    }
    const values = points.map(p => Number(p.value));
    let min = Math.min(...values), max = Math.max(...values);
    if (min === max) { min -= 1; max += 1; }
    const w = 900, h = 300, pad = 42;
    const coords = values.map((v, i) => {
      const x = pad + i * (w - 2 * pad) / Math.max(values.length - 1, 1);
      const y = h - pad - (v - min) * (h - 2 * pad) / (max - min);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    const unit = esc(points[points.length - 1].unit || '');
    const first = esc(points[0].captured_at);
    const last = esc(points[points.length - 1].captured_at);
    chart.innerHTML =
      '<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Curva de '+esc(metric)+'">' +
      '<line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(h-pad)+'" class="axis"/>' +
      '<line x1="'+pad+'" y1="'+(h-pad)+'" x2="'+(w-pad)+'" y2="'+(h-pad)+'" class="axis"/>' +
      '<polyline points="'+coords+'" class="series"/>' +
      '<text x="8" y="'+(pad+5)+'">'+max.toFixed(2)+' '+unit+'</text>' +
      '<text x="8" y="'+(h-pad)+'">'+min.toFixed(2)+' '+unit+'</text>' +
      '</svg><div class="chart-times"><span>'+first+'</span><span>'+last+'</span></div>';
  }

  select.addEventListener('change', refresh);
  refresh();
  setInterval(refresh, 5000);
})();
