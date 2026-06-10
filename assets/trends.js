// 홈 추이 차트 — data/trends.json 을 fetch 해 트럼프 순지지도·일반투표 추세를 그린다.
(function () {
  const DATA_URL = "data/trends.json";

  function makeLine(canvasId, labels, data, opts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !window.Chart) return;
    new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          data: data,
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
          y: {
            suggestedMin: opts.min, suggestedMax: opts.max,
            ticks: { callback: opts.tick }, grid: { color: "#f1f3f5" },
          },
          x: { grid: { display: false } },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch(DATA_URL)
      .then((r) => r.json())
      .then((d) => {
        const labels = d.weeks.map((w) => w.label);
        const net = d.weeks.map((w) => w.trump_net);
        const gen = d.weeks.map((w) => w.generic);

        makeLine("trumpChart", labels, net, {
          color: "#c92a2a", fill: "rgba(201,42,42,0.08)",
          min: -22, max: -12,
          tick: (v) => v, fmt: (v) => "순지지도 " + v,
        });
        makeLine("genericChart", labels, gen, {
          color: "#1971c2", fill: "rgba(25,113,194,0.10)",
          min: 0, max: 12,
          tick: (v) => "D+" + v, fmt: (v) => "민주 D+" + v,
        });

        const s = document.getElementById("trends-note");
        if (s) s.textContent = d.source;
      })
      .catch(function () {
        const r = document.getElementById("trends-root");
        if (r) r.insertAdjacentHTML("afterbegin",
          '<p style="color:#c92a2a;font-size:.9rem">추이 데이터를 불러오지 못했습니다.</p>');
      });
  });
})();
