// 조사기관별 시계열 — data/pollster_series.json 의 개별 조사를 그린다.
//
// 위 trends.js 가 "집계기관의 평균 한 줄"이라면 이쪽은 그 평균을 만든 원자료다.
// 점 = 개별 조사, 색 선 = 주요 조사기관, 굵은 검정 선 = 비당파 조사 이동평균.
// 범례를 눌러 기관을 켜고 끄면 하우스 이펙트가 눈으로 보인다.
(function () {
  const DATA_URL = "data/pollster_series.json";
  const EPOCH = Date.UTC(2026, 0, 1);
  const DAY = 86400000;

  // 8색 — 인접 색끼리 구분되게 고르고, 민주/공화 연상색(순청·순적)은 피한다.
  const PALETTE = ["#1f77b4", "#e8590c", "#2f9e44", "#9c36b5", "#0c8599",
                   "#c2255c", "#5c7cfa", "#f08c00"];

  const x = (iso) => (Date.parse(iso + "T00:00:00Z") - EPOCH) / DAY;
  const fmtDate = (v) => {
    const d = new Date(EPOCH + v * DAY);
    return (d.getUTCMonth() + 1) + "/" + d.getUTCDate();
  };

  function chart(canvasId, block, opts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !window.Chart || !block) return;

    const top = block.top_pollsters || [];
    const isTop = new Set(top);

    // 배경 — 상위 기관에 들지 않은 나머지 전부. 밀도 자체가 정보다.
    const rest = block.polls.filter((p) => !isTop.has(p.p));
    const datasets = [{
      label: "그 밖의 조사기관",
      type: "scatter",
      data: rest.map((p) => ({ x: x(p.d), y: p.v, meta: p })),
      backgroundColor: "rgba(134,142,150,0.30)",
      pointRadius: 2.5,
      pointHoverRadius: 5,
      order: 30,
    }];

    // 주요 기관 — 점을 시간순으로 이어 각 기관의 자체 추세를 만든다.
    top.forEach((name, i) => {
      const mine = block.polls.filter((p) => p.p === name);
      if (!mine.length) return;
      datasets.push({
        label: name + " (" + mine.length + ")",
        type: "line",
        data: mine.map((p) => ({ x: x(p.d), y: p.v, meta: p })),
        borderColor: PALETTE[i % PALETTE.length],
        backgroundColor: PALETTE[i % PALETTE.length],
        borderWidth: 1.5,
        pointRadius: 2.5,
        pointHoverRadius: 5,
        tension: 0.2,
        fill: false,
        hidden: i >= 4,        // 처음엔 4곳만 — 나머지는 범례로 켠다
        order: 20 - i,
      });
    });

    // 이동평균 — 비교 기준선. 개별 조사가 아니므로 시각적으로 확실히 구분한다.
    datasets.push({
      label: (block.trend_window_days || 21) + "일 이동평균 (비당파)",
      type: "line",
      data: (block.trend || []).map((t) => ({ x: x(t.d), y: t.v, meta: null })),
      borderColor: "#212529",
      backgroundColor: "#212529",
      borderWidth: 3,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0.3,
      fill: false,
      order: 1,
    });

    new Chart(ctx, {
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: true },
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, boxHeight: 10, padding: 8,
                      font: { size: 10 }, usePointStyle: true },
          },
          tooltip: {
            callbacks: {
              title: (items) => {
                const m = items[0].raw.meta;
                return m ? m.p : "이동평균";
              },
              label: (c) => {
                const m = c.raw.meta;
                const head = fmtDate(c.parsed.x) + " · " + opts.fmt(c.parsed.y);
                if (!m) return head;
                const bits = [m.pop, m.n ? "n=" + m.n : null,
                              m.party ? m.party + " 성향" : null].filter(Boolean);
                return bits.length ? head + " (" + bits.join(", ") + ")" : head;
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            ticks: { callback: fmtDate, maxTicksLimit: 10, font: { size: 10 } },
            grid: { display: false },
          },
          y: {
            ticks: { callback: opts.tick, font: { size: 10 } },
            grid: { color: "#f1f3f5" },
          },
        },
      },
    });
  }

  // 하우스 이펙트 — 기관별 평균 잔차. 0 기준 좌우로 갈리는 가로 막대.
  //
  // 색은 "어느 당 쪽으로 치우쳤나"를 뜻하므로 지표마다 부호의 의미가 뒤집힌다:
  // 순지지도는 +가 트럼프에 후한 것이지만, 일반투표 마진은 +가 민주 우위다.
  // opts.posParty 로 양수 막대가 어느 당인지 지정한다 (R=빨강 / D=파랑).
  const RED = "rgba(201,42,42,0.75)", BLUE = "rgba(25,113,194,0.75)";

  function effectChart(canvasId, effects, opts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !window.Chart || !effects || !effects.length) return;
    const pos = opts.posParty === "D" ? BLUE : RED;
    const neg = opts.posParty === "D" ? RED : BLUE;
    // 긴 기관명은 축 밖으로 잘려나가므로 줄이고, 전체 이름은 툴팁에 남긴다.
    // Chart.js 는 y축 폭을 차트의 일부로 제한해 왼쪽부터 잘라먹으므로,
    // 자르기만으로는 부족하고 afterFit 으로 라벨 자리를 따로 확보해야 한다.
    const short = (s) => (s.length > 28 ? s.slice(0, 27) + "…" : s);
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: effects.map((e) => short(e.pollster) + " (" + e.n + ")"),
        datasets: [{
          data: effects.map((e) => e.effect),
          backgroundColor: effects.map((e) => (e.effect >= 0 ? pos : neg)),
          borderWidth: 0,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => effects[items[0].dataIndex].pollster,
              label: (c) => opts.fmt(c.parsed.x),
            },
          },
        },
        scales: {
          x: { ticks: { callback: (v) => (v > 0 ? "+" : "") + v, font: { size: 10 } },
               grid: { color: "#f1f3f5" }, title: { display: true, text: opts.axis,
               font: { size: 10 } } },
          y: {
            ticks: { font: { size: 9 }, autoSkip: false },
            grid: { display: false },
            afterFit: (s) => { s.width = Math.max(s.width, 185); },
          },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch(DATA_URL)
      .then((r) => r.json())
      .then((d) => {
        const wd = d.trend_window_days;
        const a = Object.assign({ trend_window_days: wd }, d.approval);
        const g = Object.assign({ trend_window_days: wd }, d.generic);

        chart("pollsterApprovalChart", a, {
          tick: (v) => v,
          fmt: (v) => "순지지도 " + (v > 0 ? "+" : "") + v,
        });
        chart("pollsterGenericChart", g, {
          tick: (v) => (v > 0 ? "D+" + v : v < 0 ? "R+" + Math.abs(v) : "0"),
          fmt: (v) => (v >= 0 ? "민주 D+" + v : "공화 R+" + Math.abs(v)),
        });
        effectChart("approvalEffectChart", d.approval.house_effects, {
          axis: "이동평균 대비 (p) — 오른쪽일수록 트럼프에 후하게",
          posParty: "R",   // 순지지도 + = 트럼프에 후함
          fmt: (v) => "이동평균보다 순지지도 " +
                      (v >= 0 ? "+" + v + "p 높게(트럼프에 후하게)" : v + "p 낮게(박하게)"),
        });
        effectChart("genericEffectChart", d.generic.house_effects, {
          axis: "이동평균 대비 (p) — 오른쪽일수록 민주에 후하게",
          posParty: "D",   // 일반투표 마진 + = 민주 우위
          fmt: (v) => "이동평균보다 " +
                      (v >= 0 ? "+" + v + "p 민주 쪽" : v + "p 공화 쪽"),
        });

        const note = document.getElementById("pollster-note");
        if (note) {
          note.textContent =
            d.source_label + " · 표시 구간 " + d.window_start + "~ · " +
            "순지지도 " + d.approval.n_polls + "건/" + d.approval.n_pollsters + "곳(~" +
            d.approval.data_through + ") · 일반투표 " + d.generic.n_polls + "건/" +
            d.generic.n_pollsters + "곳(~" + d.generic.data_through + ") · " +
            "취득 " + d.as_of + " · " + d.note;
        }
      })
      .catch(function () {
        const r = document.getElementById("pollster-root");
        if (r) r.insertAdjacentHTML("afterbegin",
          '<p style="color:#c92a2a;font-size:.9rem">조사기관별 시계열을 불러오지 못했습니다 — scripts/fetch_pollster_polls.py 실행 여부를 확인하세요.</p>');
      });
  });
})();
