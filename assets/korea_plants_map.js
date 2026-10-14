// Korea Watch — 한국 30대 그룹 미국 공장 지도.
// 데이터는 korea_plants_map_html()(R/helpers.R)이 페이지에 인라인 JSON으로 싣는다:
//   #kp-data   공장 점(상태·지역구·선거 등급)
//   #kp-geo    공장이 있는 지역구 경계(2026 본선 지도)
//   #kp-rating 지역구 → Cook 등급 키
(function () {
  const RATING = { solid_d: "#244999", likely_d: "#577CCC", lean_d: "#8AAFFF", tossup: "#C9C09B",
                   lean_r: "#FF8B98", likely_r: "#FF5865", solid_r: "#D22532" };
  const RLAB = { solid_d: "Solid D", likely_d: "Likely D", lean_d: "Lean D", tossup: "Toss-up",
                 lean_r: "Lean R", likely_r: "Likely R", solid_r: "Solid R" };
  const STATUS = { operating: "#2b8a3e", under_construction: "#e8590c", announced: "#7048e8",
                   paused: "#868e96", closed: "#212529" };
  const SLAB = { operating: "가동", under_construction: "건설 중", announced: "발표(미착공)",
                 paused: "중단·보류", closed: "폐쇄·매각" };
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const read = id => JSON.parse(document.getElementById(id).textContent);
  const safeUrl = u => /^https?:\/\//.test(u || "") ? esc(u) : "";
  const fail = (el, msg) => { el.innerHTML = `<p class="kp-nomap">${esc(msg)} 아래 표를 이용하세요.</p>`; };

  function init() {
    const el = document.getElementById("kp-map");
    if (!el) return;
    if (typeof L === "undefined") return fail(el, "지도 라이브러리(Leaflet)를 불러오지 못했습니다.");
    let pts, geo, rk;
    try { pts = read("kp-data"); geo = read("kp-geo"); rk = read("kp-rating"); }
    catch (e) { return fail(el, "지도 데이터를 읽지 못했습니다."); }
    if (!pts.length) return fail(el, "지도에 올릴 시설이 없습니다.");
    el.innerHTML = "";
    const map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.25 });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors", maxZoom: 13
    }).addTo(map);
    L.geoJSON(geo, {
      style: f => ({ fillColor: RATING[rk[f.properties.cd]] || "#dee2e6", fillOpacity: 0.45, color: "#495057", weight: 1 }),
      onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(f.properties.cd)}</b> · Cook ${esc(RLAB[rk[f.properties.cd]] || "미확인")}`, { sticky: true })
    }).addTo(map);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}", { maxZoom: 13, pane: "shadowPane" }).addTo(map);
    const layer = L.featureGroup().addTo(map);
    // 같은 부지에 여러 시설(증설·합작)이 있으면 점이 겹친다 — 작은 원 위로 벌려 놓는다.
    const seen = {};
    pts.forEach(p => { const k = p.lat + "," + p.lon; (seen[k] = seen[k] || []).push(p); });
    Object.values(seen).forEach(g => g.length > 1 && g.forEach((p, i) => {
      const a = 2 * Math.PI * i / g.length; p.lat += 0.012 * Math.sin(a); p.lon += 0.015 * Math.cos(a);
    }));
    pts.forEach(p => {
      const inv = p.investment_usd_m ? `$${Number(p.investment_usd_m).toLocaleString()}M` : "미확인";
      const html = `<div class="kp-pop"><b>${esc(p.group)} · ${esc(p.facility)}</b><br>` +
        `<span class="muted">${esc(p.company)} — ${esc(p.product)}</span><br>` +
        `상태: <b style="color:${STATUS[p.status]}">${esc(p.status_kr)}</b> · 투자 ${esc(inv)}${p.jobs ? " · 고용 " + esc(p.jobs) : ""}<br>` +
        `위치: ${esc(p.city)}, ${esc(p.state)} · <b>${esc(p.district || "지역구 미배정")}</b><hr>` +
        `하원(Cook): ${esc(p.house_rating || "—")}${p.house_inc ? " · 현역 " + esc(p.house_inc) : ""}${p.house_party ? " (" + esc(p.house_party) + ")" : ""}<br>` +
        `상원(Cook): ${esc(p.senate_rating || "올해 선거 없음")} · 주지사(Cook): ${esc(p.gov_rating || "올해 선거 없음")}<br>` +
        (safeUrl(p.source_url) ? `<a href="${safeUrl(p.source_url)}" target="_blank" rel="noopener">출처</a>` : "") + `</div>`;
      L.circleMarker([p.lat, p.lon], {
        radius: 7, color: "#fff", weight: 1.5, fillColor: STATUS[p.status] || "#000", fillOpacity: 0.95
      }).bindPopup(html, { maxWidth: 320 }).addTo(layer);
    });
    map.fitBounds(layer.getBounds().pad(0.08));
    const used = [...new Set(pts.map(p => p.status))];
    document.getElementById("kp-legend").innerHTML =
      '<span class="kp-lh">시설 상태</span>' +
      Object.keys(SLAB).filter(k => used.includes(k)).map(k => `<span class="kp-key"><i class="dot" style="background:${STATUS[k]}"></i>${SLAB[k]}</span>`).join("") +
      '<span class="kp-lh">지역구 색 = Cook 하원 등급</span>' +
      Object.keys(RLAB).map(k => `<span class="kp-key"><i style="background:${RATING[k]}"></i>${RLAB[k]}</span>`).join("");
  }
  document.addEventListener("DOMContentLoaded", init);
})();
