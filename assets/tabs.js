// 탭(panel-tabset) 보조 — 전국 환경 페이지.
// ① 숨은 탭 안에서 그려진 Chart.js 캔버스는 폭이 0으로 잡힌다 → 탭이 열릴 때 크기를 다시 잰다.
// ② 다른 페이지가 national.html#approval 같은 절 앵커로 들어오면 그 절이 든 탭을 먼저 연다.
(function () {
  function resizeCharts() {
    if (!window.Chart || !Chart.instances) return;
    Object.values(Chart.instances).forEach(function (c) { try { c.resize(); } catch (e) {} });
  }
  function openTabFor(hash) {
    if (!hash || hash.length < 2) return false;
    var el = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!el) return false;
    var pane = el.closest(".tab-pane");
    if (!pane) return false;
    var link = document.querySelector('.nav-tabs a[href="#' + pane.id + '"], .nav-tabs [data-bs-target="#' + pane.id + '"]');
    if (!link || !window.bootstrap) return false;
    bootstrap.Tab.getOrCreateInstance(link).show();
    setTimeout(function () { el.scrollIntoView({ block: "start" }); resizeCharts(); }, 60);
    return true;
  }
  document.addEventListener("shown.bs.tab", function () { setTimeout(resizeCharts, 30); });
  document.addEventListener("DOMContentLoaded", function () { openTabFor(location.hash); });
  window.addEventListener("hashchange", function () { openTabFor(location.hash); });
})();
