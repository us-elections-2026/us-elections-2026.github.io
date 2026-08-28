// 홈 추이 차트 — data/trends.json 을 fetch 해 트럼프 순지지도·일반투표 추세를 그린다.
// 결측 주가 있으면 실측(실선·점)과 보간(회색 점선)을 분리해 그린다 — 보간을 값으로 오독하지 않도록.
(function () {
  const DATA_URL = "data/trends.json";

  function makeLine(canvasId, labels, data, opts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !window.Chart) return 0;

    const gaps = data.filter((v) => v === null || v === undefined).length;
    const datasets = [];

    // 결측 구간을 잇는 회색 점선 — 값이 아니라 보간임을 표시. 실선 아래에 깔린다.
    if (gaps > 0) {
      datasets.push({
        data: data,
        borderColor: "#adb5bd",
        borderWidth: 1.5,
        borderDash: [5, 4],
        tension: 0.25,
        spanGaps: true,
        fill: false,
        pointRadius: 0,
      });
    }

    // 실측 구간만 — 결측에서 선이 끊긴다(spanGaps: false).
    datasets.push({
      data: data,
      borderColor: opts.color,
      backgroundColor: opts.fill,
      borderWidth: 2,
      tension: 0.25,
      spanGaps: false,
      pointRadius: 3,
      pointBackgroundColor: opts.color,
      fill: true,
    });

    const solidIndex = datasets.length - 1;

    new Chart(ctx, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: (c) => c.datasetIndex === solidIndex,
            callbacks: {
              label: (c) => (c.parsed.y === null ? "데이터 없음" : opts.fmt(c.parsed.y)),
            },
          },
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

    return gaps;
  }

  function legendHTML(color, total, gaps) {
    return '<p class="text-muted" style="font-size:.72rem; margin:.35rem 0 0; display:flex; flex-wrap:wrap; gap:12px;">' +
      '<span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; vertical-align:middle; background:' + color + '"></span> ' +
      '실측 ' + (total - gaps) + '주</span>' +
      '<span><span style="display:inline-block; width:14px; border-top:2px dashed #adb5bd; vertical-align:middle;"></span> ' +
      '결측 ' + gaps + '주 보간 — 값이 아님</span></p>';
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch(DATA_URL)
      .then((r) => r.json())
      .then((d) => {
        const labels = d.weeks.map((w) => w.label);
        const net = d.weeks.map((w) => w.trump_net);
        const gen = d.weeks.map((w) => w.generic);

        const netGaps = makeLine("trumpChart", labels, net, {
          color: "#c92a2a", fill: "rgba(201,42,42,0.08)",
          min: -22, max: -12,
          tick: (v) => v, fmt: (v) => "순지지도 " + v,
        });
        const genGaps = makeLine("genericChart", labels, gen, {
          color: "#1971c2", fill: "rgba(25,113,194,0.10)",
          min: 0, max: 12,
          tick: (v) => "D+" + v, fmt: (v) => "민주 D+" + v,
        });

        // 결측이 있는 차트에만 범례를 붙인다.
        const legends = [
          ["trumpChart", "#c92a2a", netGaps],
          ["genericChart", "#1971c2", genGaps],
        ];
        legends.forEach(function (item) {
          if (item[2] <= 0) return;
          const canvas = document.getElementById(item[0]);
          if (!canvas) return;
          const box = canvas.parentElement;
          if (box) box.insertAdjacentHTML("afterend", legendHTML(item[1], labels.length, item[2]));
        });

        // 값이 전주와 같으면 선이 평평해 "갱신이 멈춘 것"처럼 보인다.
        // 마지막 실측 주를 앞에 명시해 '변화 없음'과 '반영 안 됨'을 구분한다(2026-08-28).
        const last = d.weeks[d.weeks.length - 1];
        const s = document.getElementById("trends-note");
        if (s) s.textContent =
          "마지막 반영 주: " + last.label + " (" + last.date + " 주간, 데이터 기준 " + d.as_of + ") — "
          + "값이 전주와 같으면 선이 평평하게 그려집니다. " + d.source;
      })
      .catch(function () {
        const r = document.getElementById("trends-root");
        if (r) r.insertAdjacentHTML("afterbegin",
          '<p style="color:#c92a2a;font-size:.9rem">추이 데이터를 불러오지 못했습니다.</p>');
      });
  });
})();
