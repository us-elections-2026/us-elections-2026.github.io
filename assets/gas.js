// 휘발유 주간 소매가 — data/gas_prices.json (EIA Regular All Formulations, 지난 1년) → Chart.js 선 그래프.
// 주 실측(OH·TX·NY·US)은 실선, PADD 지역 대리값은 점선. 범례를 눌러 켜고 끈다.
(function () {
  const DATA_URL = "data/gas_prices.json";
  const COLORS = { US: "#212529", OH: "#c92a2a", TX: "#e8590c", "MI·IA": "#1971c2", "GA·NC": "#2b8a3e",
                   "ME·NH": "#5f3dc4", AK: "#0b7285", NY: "#868e96", PA: "#a61e4d" };
  document.addEventListener("DOMContentLoaded", function () {
    const ctx = document.getElementById("gasChart");
    if (!ctx || !window.Chart) return;
    fetch(DATA_URL).then(r => r.json()).then(function (d) {
      const labels = d.weeks.map(w => w.slice(5).replace("-", "/"));
      const datasets = d.series.map(function (s) {
        return {
          label: s.label, data: s.values, borderColor: COLORS[s.code] || "#999",
          backgroundColor: "transparent", borderWidth: s.code === "US" ? 3 : 1.6,
          borderDash: s.proxy ? [5, 4] : [], pointRadius: 0, pointHitRadius: 6, tension: 0.15, spanGaps: true,
          hidden: (s.code === "NY" || s.code === "PA"),
        };
      });
      new Chart(ctx, {
        type: "line",
        data: { labels: labels, datasets: datasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 18, font: { size: 11 } } },
            tooltip: { callbacks: { label: c => " " + c.dataset.label + ": $" + (c.parsed.y == null ? "—" : c.parsed.y.toFixed(3)) } },
          },
          scales: {
            x: { ticks: { maxTicksLimit: 13, font: { size: 10 } }, grid: { display: false } },
            y: { ticks: { callback: v => "$" + v.toFixed(2) }, title: { display: true, text: "달러/갤런" } },
          },
        },
      });
      const note = document.getElementById("gas-note");
      if (note) note.textContent = d.source_label + " · 마지막 주 " + d.data_through + " · 취득 " + d.as_of +
        " · 점선은 주 실측이 없어 소속 PADD 지역 평균으로 대신한 것입니다.";
    }).catch(function () {
      const r = document.getElementById("gas-root");
      if (r) r.insertAdjacentHTML("afterbegin", '<p style="color:#c92a2a;font-size:.9rem">휘발유 가격 데이터를 불러오지 못했습니다 — scripts/fetch_gas_prices.py 실행 여부를 확인하세요.</p>');
    });
  });
})();
