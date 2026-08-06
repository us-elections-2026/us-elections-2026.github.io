// 외부 예측 종합 대시보드 — data/model_dashboard.json 을 빌드 산출물에서 fetch 하여 렌더.
// 등급(Cook·Sabato)·예측시장 가격·외부 모델(RtWH·DDHQ)을 종류 구분해 표시.
// 데이터 갱신 = JSON만 고쳐 push → Actions 재빌드 → 자동 반영.
(function () {
  const DATA_URL = "data/model_dashboard.json";

  const probColor = (p) =>
    p >= 55 ? "#2166ac" : p >= 50 ? "#4393c3" : p >= 45 ? "#f4a582" : "#d6604d";

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function renderKPIs(root, d) {
    // 등급(Cook·Sabato) 기반 집계 — 등급은 확률이 아니므로 개수만 센다
    const leanD = d.states.filter((s) => s.rating.includes("Lean D")).length;
    const toss = d.states.filter((s) => s.rating.includes("Toss")).length;
    const leanR = d.states.length - leanD - toss;

    const cards = [
      ["등급 민주 우위 (Lean D)", `${leanD}석`, "Cook·Sabato 종합 — 등급은 확률이 아님", "#1971c2"],
      ["등급 토스업", `${toss}석`, "다수 향배를 좌우하는 구간", "#f59e0b"],
      ["등급 공화 우위 (Lean R)", `${leanR}석`, "확장 표적(토스업 경계 포함)", "#c92a2a"],
      // 대표값 = 예측시장 원가격(2026-08-06 승격). 모델 수치는 재확인 실패로 미검증이라
      // 시나리오 카드에만 '미검증' 표시와 함께 남겨둔다.
      ["민주 다수 — 예측시장 가격", `${d.dem_majority_prob}%`, d.majority_note || "", "#1d4a70"],
    ];
    const wrap = el("div", "kpi-grid");
    cards.forEach(([label, val, sub, color]) => {
      const c = el("div", "kpi-card");
      c.appendChild(el("div", "kpi-label", label));
      const v = el("div", "kpi-value", val);
      v.style.color = color;
      c.appendChild(v);
      c.appendChild(el("div", "kpi-sub", sub));
      wrap.appendChild(c);
    });
    root.appendChild(wrap);
  }

  // 8개 주 가로 막대(자체 모델 v0) × 예측시장가 마커(◆) 오버레이 — 50% 기준선 포함
  function renderStateOutlook(d, m) {
    const ctx = document.getElementById("probChart");
    if (!ctx || !window.Chart) return;
    const v0 = {};
    if (m && m.states) m.states.forEach((s) => { v0[s.state] = Math.round(s.p_blend * 100); });
    const rows = d.states
      .map((s) => ({ name: s.name, v: v0[s.id.toUpperCase()], mk: s.prob }))
      .filter((r) => r.v != null)
      .sort((a, b) => b.v - a.v);
    const fiftyLine = {
      id: "fifty",
      afterDatasetsDraw(chart) {
        const { ctx: c, chartArea, scales } = chart;
        if (!scales.x) return;
        const x = scales.x.getPixelForValue(50);
        c.save(); c.strokeStyle = "#9ca3af"; c.setLineDash([4, 4]);
        c.beginPath(); c.moveTo(x, chartArea.top); c.lineTo(x, chartArea.bottom); c.stroke(); c.restore();
      },
    };
    new Chart(ctx, {
      data: {
        labels: rows.map((r) => r.name),
        datasets: [
          {
            type: "bar", label: "자체 모델 v0",
            data: rows.map((r) => r.v),
            backgroundColor: rows.map((r) => probColor(r.v)),
            borderRadius: 6, borderSkipped: false, maxBarThickness: 26,
          },
          {
            type: "scatter", label: "예측시장가 (Kalshi 원가격)",
            data: rows.filter((r) => r.mk != null).map((r) => ({ x: r.mk, y: r.name })),
            pointStyle: "rectRot", radius: 8, hoverRadius: 9,
            backgroundColor: "#111827", borderColor: "#ffffff", borderWidth: 1.5,
          },
        ],
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: 민주 ${c.parsed.x}%` } },
        },
        scales: {
          x: { min: 0, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: "#f3f4f6" } },
          y: { grid: { display: false } },
        },
      },
      plugins: [fiftyLine],
    });
  }

  // 민주 다수 확률 — 0~100% 스펙트럼 축 위에 모델별 위치 표시 + 설명 리스트
  function renderMajoritySpectrum(root, d, m) {
    const marks = [];
    (d.scenarios || []).forEach((s) => {
      if (s.prob != null) marks.push({ v: s.prob, name: s.id === "ddhq" ? "DDHQ" : s.name });
    });
    if (m && m.dem_majority_prob != null)
      marks.push({ v: Math.round(m.dem_majority_prob), name: "자체 " + (m.version || "v0") });
    marks.sort((a, b) => a.v - b.v);

    const wrap = el("div", "spec-wrap");
    wrap.appendChild(el("div", "spec-axis",
      "<span>0% — 공화 유지 확실</span><span>50%</span><span>100% — 민주 탈환 확실</span>"));
    const bar = el("div", "spec-bar");
    bar.appendChild(el("div", "spec-mid"));
    marks.forEach((mk, i) => {
      const dot = el("div", "spec-mark"); dot.style.left = mk.v + "%"; bar.appendChild(dot);
      const lab = el("div", "spec-lab " + (i % 2 ? "below" : "above"),
        `<span class="spec-val">${mk.v}%</span><span class="spec-name">${mk.name}</span>`);
      lab.style.left = mk.v + "%"; bar.appendChild(lab);
    });
    wrap.appendChild(bar);

    const ul = el("ul", "spec-notes");
    (d.scenarios || []).forEach((s) => {
      const val = s.prob != null ? s.prob + "%" : (s.prob_label || "—");
      ul.appendChild(el("li", null, `<b>${s.name}</b> <span class="spec-sub">${s.subname} · ${val}</span> — ${s.desc}`));
    });
    if (m && m.dem_majority_prob != null)
      ul.appendChild(el("li", null,
        `<b>자체 모델 ${m.version || "v0"}</b> <span class="spec-sub">몬테카를로·재현 가능 · ${Math.round(m.dem_majority_prob)}%</span> — 의석 중앙값 D ${m.seats.median} (90% 구간 ${m.seats.p05}–${m.seats.p95}) · 등급+시장+조사 블렌드, 코드 scripts/model/run_model.R (${m.run_date})`));
    wrap.appendChild(ul);
    root.appendChild(wrap);
  }

  function renderStateCards(root, d) {
    const wrap = el("div", "state-grid");
    d.states.forEach((s) => {
      const card = el("div", "state-card");
      const rc =
        s.rating.includes("Lean D")
          ? "r-lean-d"
          : s.rating.includes("Toss")
          ? "r-toss"
          : "r-lean-r";
      card.appendChild(
        el("div", "state-top",
          `<span class="state-name">${s.name}</span><span class="state-rating ${rc}">${s.rating}</span>`)
      );
      card.appendChild(el("div", "state-matchup", s.matchup));
      const hasProb = s.prob != null;
      const bar = el("div", "prob-bar");
      const fill = el("div", "prob-fill");
      fill.style.width = (hasProb ? s.prob : 0) + "%";
      if (hasProb) fill.style.background = probColor(s.prob);
      bar.appendChild(fill);
      card.appendChild(bar);
      card.appendChild(
        el("div", "prob-row",
          hasProb
            ? `<span>시장가 민주 ${s.prob}%</span><span class="muted">공화 ${100 - s.prob}%</span>`
            : `<span class="muted">예측시장 가격 미확인 — 등급 참조</span>`)
      );
      card.appendChild(el("div", "state-note", `<strong>핵심 변수</strong> ${s.key_var}<br><span class="muted">${s.note}</span>`));
      wrap.appendChild(card);
    });
    root.appendChild(wrap);
  }

  function renderTimeline(root, d) {
    const wrap = el("div", "timeline");
    d.timeline.forEach((t) => {
      const item = el("div", "tl-item tl-" + t.party + (t.status === "done" ? " tl-done" : ""));
      item.appendChild(el("div", "tl-date", t.date));
      item.appendChild(el("div", "tl-body", `<strong>${t.event}</strong><br><span class="muted">${t.detail}</span>`));
      wrap.appendChild(item);
    });
    root.appendChild(wrap);
  }

  function mount(d, m) {
    const stamp = document.getElementById("dash-stamp");
    if (stamp)
      stamp.textContent = `${d.source_label} · 확률 기준 ${d.as_of} · 사실 ${d.facts_updated} · ${d.current_balance} (다수당까지 +${d.dem_needed_net})`;
    const note = document.getElementById("dash-note");
    if (note) note.textContent = d.provenance_note;

    const k = document.getElementById("dash-kpis");
    if (k) renderKPIs(k, d);
    const sc = document.getElementById("dash-scenarios");
    if (sc) renderMajoritySpectrum(sc, d, m);
    renderStateOutlook(d, m);
    const st = document.getElementById("dash-states");
    if (st) renderStateCards(st, d);
    const tl = document.getElementById("dash-timeline");
    if (tl) renderTimeline(tl, d);
  }

  function fail(msg) {
    const root = document.getElementById("dash-root");
    if (root) root.insertAdjacentHTML("afterbegin", `<p class="dash-error">대시보드 데이터를 불러오지 못했습니다 (${msg}). 페이지의 정적 표를 참고하세요.</p>`);
  }

  document.addEventListener("DOMContentLoaded", function () {
    Promise.all([
      fetch(DATA_URL).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      fetch("data/model_v0.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ])
      .then(([d, m]) => mount(d, m))
      .catch(fail);
  });
})();
