// 전국 경제 지표 차트 — data/national_econ.json 의 series(1월~)를 그린다.
(function () {
  const DATA_URL = "data/national_econ.json";

  function makeLine(canvasId, ts, opts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !window.Chart || !ts) return;
    new Chart(ctx, {
      type: "line",
      data: {
        labels: ts.map((p) => p[0]),
        datasets: [{
          data: ts.map((p) => p[1]),
          borderColor: opts.color,
          backgroundColor: opts.fill,
          borderWidth: 2,
          tension: 0.25,
          spanGaps: true,
          pointRadius: 3,
          pointBackgroundColor: opts.color,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => opts.fmt(c.parsed.y) } },
        },
        scales: {
          y: { ticks: { callback: opts.tick }, grid: { color: "#f1f3f5" } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch(DATA_URL)
      .then((r) => r.json())
      .then((d) => {
        const s = d.series || {};
        makeLine("cpiChart", s.cpi_yoy, {
          color: "#c92a2a", fill: "rgba(201,42,42,0.08)",
          tick: (v) => v + "%", fmt: (v) => "CPI 전년 대비 " + v + "%",
        });
        makeLine("unrateChart", s.unrate, {
          color: "#1f3a5f", fill: "rgba(31,58,95,0.08)",
          tick: (v) => v + "%", fmt: (v) => "실업률 " + v + "%",
        });
        makeLine("umcsentChart", s.umcsent, {
          color: "#e8590c", fill: "rgba(232,89,12,0.08)",
          tick: (v) => v, fmt: (v) => "소비자심리 " + v,
        });
        const note = document.getElementById("econ-note");
        if (note) note.textContent =
          d.source_label + " · " + (d.series_start || "") + "~ · 기준 " + d.as_of;
      })
      .catch(function () {
        const r = document.getElementById("econ-root");
        if (r) r.insertAdjacentHTML("afterbegin",
          '<p style="color:#c92a2a;font-size:.9rem">경제 지표 시계열을 불러오지 못했습니다 — scripts/fetch_national_econ.py 실행 여부를 확인하세요.</p>');
      });
  });
})();
