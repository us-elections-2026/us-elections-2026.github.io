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
      ["민주 다수 확률 — 외부 모델", `${d.dem_majority_prob}%`, d.majority_note || "", "#7c3aed"],
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

  function renderProbChart(d) {
    const ctx = document.getElementById("probChart");
    if (!ctx || !window.Chart) return;
    // 예측시장 가격이 확인된 주만 표시 — 나머지는 추정으로 채우지 않는다
    const priced = d.states.filter((s) => s.prob != null);
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: priced.map((s) => s.name),
        datasets: [
          {
            data: priced.map((s) => s.prob),
            backgroundColor: priced.map((s) => probColor(s.prob)),
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => `민주 ${c.parsed.y}% / 공화 ${100 - c.parsed.y}%`,
            },
          },
        },
        scales: {
          y: { min: 0, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: "#f3f4f6" } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function renderScenarios(root, d) {
    const wrap = el("div", "scenario-grid");
    d.scenarios.forEach((s) => {
      const c = el("div", "scenario-card sc-" + s.id);
      c.appendChild(el("div", "sc-prob", s.prob != null ? s.prob + "%" : (s.prob_label || "—")));
      c.appendChild(el("div", "sc-name", `${s.name} <span>· ${s.subname}</span>`));
      c.appendChild(el("div", "sc-seats", s.seats));
      c.appendChild(el("div", "sc-majority", s.majority));
      c.appendChild(el("div", "sc-desc", s.desc));
      wrap.appendChild(c);
    });
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

  function mount(d) {
    const stamp = document.getElementById("dash-stamp");
    if (stamp)
      stamp.textContent = `${d.source_label} · 확률 기준 ${d.as_of} · 사실 ${d.facts_updated} · ${d.current_balance} (다수당까지 +${d.dem_needed_net})`;
    const note = document.getElementById("dash-note");
    if (note) note.textContent = d.provenance_note;

    const k = document.getElementById("dash-kpis");
    if (k) renderKPIs(k, d);
    renderProbChart(d);
    const sc = document.getElementById("dash-scenarios");
    if (sc) renderScenarios(sc, d);
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
    fetch(DATA_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(mount)
      .catch(fail);
  });
})();
