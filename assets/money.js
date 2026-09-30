// 주별 자금 누적 추이 — data/fec_timeline.json → 9개 소형 그래프(주당 하나).
// 실선 = 후보 누적 모금 + 우호 독립지출 합계, 점선 = 독립지출만. 파랑 = 민주 측, 빨강 = 공화 측.
(function () {
  const DATA_URL = "data/fec_timeline.json";
  const NM = { GA: "조지아", MI: "미시간", NH: "뉴햄프셔", ME: "메인", NC: "노스캐롤라이나", TX: "텍사스", OH: "오하이오", AK: "알래스카", IA: "아이오와" };
  document.addEventListener("DOMContentLoaded", function () {
    const root = document.getElementById("money-root");
    if (!root || !window.Chart) return;
    fetch(DATA_URL).then(r => r.json()).then(function (d) {
      const labels = d.weeks.map(w => w.slice(5).replace("-", "/"));
      Object.keys(NM).forEach(function (st) {
        const s = d.states[st];
        const canvas = document.getElementById("money-" + st);
        if (!s || !canvas) return;
        const line = (label, data, color, dash) => ({
          label, data, borderColor: color, backgroundColor: "transparent", borderWidth: dash ? 1.2 : 2.2,
          borderDash: dash ? [4, 3] : [], pointRadius: 0, pointHitRadius: 6, tension: 0.1,
        });
        new Chart(canvas, {
          type: "line",
          data: { labels, datasets: [
            line("민주 측 합계 (" + (s.D.name || "—") + ")", s.total_D, "#1971c2", false),
            line("공화 측 합계 (" + (s.R.name || "—") + ")", s.total_R, "#c92a2a", false),
            line("민주 우호 독립지출", s.ie_D, "#1971c2", true),
            line("공화 우호 독립지출", s.ie_R, "#c92a2a", true),
          ]},
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              legend: { display: false },
              title: { display: true, text: NM[st] + " — 민주 $" + s.total_D[s.total_D.length - 1].toFixed(1) + "M · 공화 $" + s.total_R[s.total_R.length - 1].toFixed(1) + "M", font: { size: 12 } },
              tooltip: { callbacks: { label: c => " " + c.dataset.label + ": $" + c.parsed.y.toFixed(1) + "M" } },
            },
            scales: {
              x: { ticks: { maxTicksLimit: 6, font: { size: 9 } }, grid: { display: false } },
              y: { beginAtZero: true, ticks: { callback: v => "$" + v + "M", font: { size: 9 } } },
            },
          },
        });
      });
      const note = document.getElementById("money-note");
      if (note) note.textContent = d.source_label + " · 취득 " + d.as_of + " · 실선 = 후보 누적 모금 + 우호 독립지출, 점선 = 독립지출만. " + d.provenance_note;
    }).catch(function () {
      root.insertAdjacentHTML("afterbegin", '<p style="color:#c92a2a;font-size:.9rem">자금 추이 데이터를 불러오지 못했습니다 — scripts/fetch_fec_timeline.py 실행 여부를 확인하세요.</p>');
    });
  });
})();
