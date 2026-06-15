# R/helpers.R
# data/ 의 정규화 JSON/CSV를 읽어 gt 표로 렌더링하는 헬퍼.
# 핵심 원칙: 정규화(comparability) · 변화추적(delta) · 출처라벨(provenance)

suppressPackageStartupMessages({
  library(jsonlite)
  library(dplyr)
  library(gt)
  library(readr)
})

# _quarto.yml 에서 execute-dir: project 로 두어 작업 경로를 레포 루트로 고정한다.
.load_json <- function(name) {
  jsonlite::read_json(file.path("data", paste0(name, ".json")),
                      simplifyVector = TRUE)
}

# 종류 라벨(영문 -> 한글)
.type_kr <- c(market = "시장", model = "모델", rating = "등급", aggregate = "집계")

# 확률(0~1) -> "81%"
.fmt_pct <- function(x) ifelse(is.na(x), "—", paste0(round(x * 100), "%"))

# delta -> "▲ 1.2p" / "▼ 0.5p" / "—"
.fmt_delta <- function(x, pct = FALSE) {
  v <- if (pct) round(x * 100, 1) else round(x, 1)
  arrow <- ifelse(is.na(x), "—", ifelse(x > 0, "▲", ifelse(x < 0, "▼", "—")))
  ifelse(is.na(x), "—", paste0(arrow, " ", abs(v), if (pct) "p" else ""))
}

# 마진(양수=민주 우위) -> "D+6.8" / "R+2.0"
.fmt_margin <- function(x) {
  ifelse(is.na(x), "—",
         ifelse(x >= 0, paste0("D+", round(x, 1)), paste0("R+", round(abs(x), 1))))
}

.tbl_opts <- function(g) {
  g |>
    opt_table_font(font = list(gt::google_font("IBM Plex Sans KR"), gt::default_fonts())) |>
    tab_options(
      table.font.size = px(14),
      heading.title.font.size = px(16),
      heading.subtitle.font.size = px(12),
      column_labels.font.weight = "bold",
      data_row.padding = px(6),
      table.border.top.style = "none"
    )
}

# 1.1 예보 종합 --------------------------------------------------------------
gt_forecast <- function() {
  d <- .load_json("forecast")
  r <- d$rows
  tibble(
    출처 = r$source,
    종류 = .type_kr[r$type],
    `하원 민주` = .fmt_pct(r$house_dem),
    `상원 민주` = .fmt_pct(r$senate_dem),
    `하원 Δ` = .fmt_delta(r$house_delta, pct = TRUE),
    `상원 Δ` = .fmt_delta(r$senate_delta, pct = TRUE),
    비고 = r$note
  ) |>
    gt() |>
    tab_header(title = "예보 종합 — 상·하원 통제 확률",
               subtitle = paste0("기준 ", d$as_of, " · 시장/모델/등급은 성격이 다름에 유의")) |>
    .tbl_opts()
}

# 1.2 제너릭 밸럿 ------------------------------------------------------------
gt_generic <- function() {
  d <- .load_json("generic_ballot")
  a <- d$aggregators
  tibble(
    집계기관 = a$source,
    민주 = ifelse(is.na(a$dem), "—", a$dem),
    공화 = ifelse(is.na(a$rep), "—", a$rep),
    마진 = .fmt_margin(a$margin),
    기준일 = a$agg_as_of,
    모집단 = a$population
  ) |>
    gt() |>
    tab_header(title = "제너릭 밸럿 — 집계기관 평균",
               subtitle = paste0("기준 ", d$as_of, " · 양수는 민주 우위")) |>
    .tbl_opts()
}

gt_generic_spread <- function() {
  d <- .load_json("generic_ballot")
  s <- d$spread_examples
  tibble(
    `조사기관` = s$pollster,
    민주 = s$dem, 공화 = s$rep,
    마진 = .fmt_margin(s$margin),
    모집단 = s$population,
    메모 = s$note
  ) |>
    gt() |>
    tab_header(title = "개별조사 스프레드 — 왜 평균만 봐야 하는가",
               subtitle = "같은 시점, 같은 질문 — 그래도 이만큼 벌어진다") |>
    .tbl_opts()
}

# 1.3 대통령 지지율 ----------------------------------------------------------
gt_approval <- function() {
  d <- .load_json("approval")
  r <- d$rows
  tibble(
    집계 = r$source,
    승인 = ifelse(is.na(r$approve), "—", r$approve),
    비승인 = ifelse(is.na(r$disapprove), "—", r$disapprove),
    순지지 = ifelse(is.na(r$net), "—", sprintf("%+.1f", r$net)),
    기준일 = r$row_as_of,
    비고 = r$note
  ) |>
    gt() |>
    tab_header(title = "트럼프 국정지지율",
               subtitle = paste0("기준 ", d$as_of)) |>
    .tbl_opts()
}

# 1.4 상원 경합주 ------------------------------------------------------------
gt_senate <- function() {
  d <- .load_json("senate_races")
  r <- d$races
  tibble(
    주 = r$state,
    구도 = ifelse(r$defense == "D", "민주 방어", "공화 방어"),
    `현직/구도` = r$incumbent,
    등급 = r$rating,
    `최신 폴` = ifelse(is.na(r$latest_poll), "【수집】", r$latest_poll),
    출처 = ifelse(is.na(r$poll_source), "—", r$poll_source),
    `모금(현금)` = ifelse(is.na(r$cash_on_hand), "—", r$cash_on_hand),
    `한국 관심` = r$kr_relevance
  ) |>
    gt() |>
    tab_header(
      title = "상원 경합주 트래커",
      subtitle = paste0(d$current_balance, " · 민주 다수당까지 순증 +", d$dem_needed_net)
    ) |>
    .tbl_opts()
}

# 1.4b 상원 경선 캘린더 ------------------------------------------------------
gt_senate_primaries <- function() {
  d <- .load_json("senate_primaries")
  r <- d$rows
  tibble(
    주 = r$state,
    경선 = r$event,
    일자 = ifelse(is.na(r$date), "【수집】", r$date),
    상태 = r$status,
    내용 = ifelse(is.na(r$detail), "—", r$detail)
  ) |>
    arrange(일자 == "【수집】", 일자) |>
    gt() |>
    tab_header(title = "경선 캘린더 — 본선 대진 확정 일정",
               subtitle = paste0("기준 ", d$as_of)) |>
    .tbl_opts()
}

# 1.4c 주별 상세 카드 (State Focus 페이지용) ---------------------------------
gt_state_detail <- function(code) {
  d <- .load_json("senate_races")
  r <- d$races[d$races$state == code, ]
  p <- .load_json("senate_primaries")$rows
  p <- p[p$state == code, ]

  poll <- if (is.na(r$latest_poll)) "【수집】" else
    paste0(r$latest_poll, if (!is.na(r$poll_source)) paste0(" (", r$poll_source, ")") else "")
  rows <- tibble(
    항목 = c("구도", "현직/구도", "등급", "최신 폴", "모금(현금)", "한국 관심"),
    내용 = c(ifelse(r$defense == "D", "민주 방어", "공화 방어"),
           r$incumbent, r$rating, poll,
           ifelse(is.na(r$cash_on_hand), "—", r$cash_on_hand),
           r$kr_relevance)
  )
  if (nrow(p) > 0) {
    rows <- bind_rows(rows, tibble(
      항목 = paste0("경선 — ", p$event),
      내용 = paste0(ifelse(is.na(p$date), p$status, paste0(p$date, " ", p$status)),
                  ifelse(is.na(p$detail), "", paste0(" · ", p$detail)))
    ))
  }
  rows |>
    gt() |>
    tab_header(title = paste0(code, " 레이스 카드"),
               subtitle = paste0("기준 ", d$as_of)) |>
    .tbl_opts()
}

# 1.4d 후보자 프로필 카드 (HTML) --------------------------------------------
# data/candidates.json 을 읽어 HTML 카드 문자열을 반환. qmd 청크에서
# `#| output: asis` 와 함께 cat() 으로 출력한다. status="primary"는 경선 후보(하단 가로),
# 그 외는 확정 후보(상단 정식 카드)로 분리 렌더한다.
.party_kr <- c(D = "민주", R = "공화")

.c_ul <- function(v) { v <- v[!is.na(v) & nzchar(v)]
  if (!length(v)) "" else paste0("<ul>", paste0("<li>", v, "</li>", collapse = ""), "</ul>") }
.c_inline <- function(v) { v <- v[!is.na(v) & nzchar(v)]; if (!length(v)) "—" else paste(v, collapse = " · ") }
.c_srcs <- function(v) { v <- v[!is.na(v) & nzchar(v)]; if (!length(v)) return("")
  links <- vapply(seq_along(v), function(i) { u <- v[i]
    if (grepl("^https?://", u)) sprintf('<a href="%s" target="_blank" rel="noopener">[%d]</a>', u, i)
    else sprintf('<span>[%d] %s</span>', i, u) }, character(1))
  paste0('<span class="cand-src">출처 ', paste(links, collapse = " "), "</span>") }
.c_badge <- function(r) paste0(.party_kr[[r$party]], if (isTRUE(r$incumbent)) " · 현직" else "")
.c_credit <- function(r) if (!is.na(r$photo_credit) && nzchar(r$photo_credit)) paste0("사진: ", r$photo_credit) else "사진 미확보"
.c_age <- function(r) if (!is.na(r$born)) paste0(r$born, "년생(", 2026 - r$born, "세) · ") else ""

# 정식(전체) 카드 — 행 단위 평탄 구조(두 카드 간 subgrid 정렬용).
# 정렬을 위해 비어 있어도 모든 행(가족/학력/경력/펀드레이징…)을 항상 출력한다.
.c_val <- function(x) if (length(x) == 0 || is.na(x) || !nzchar(x)) "—" else x
.full_card <- function(r) {
  kr <- if (!is.na(r$kr_note) && nzchar(r$kr_note)) r$kr_note else
    "<span class='muted'>한국 관련 직접 입장은 공개 출처에서 확인되지 않음</span>"
  paste0(
    '<div class="cand-card cand-', r$party, '">',
    '<img class="cand-photo" src="/', r$photo, '" alt="', r$name, '" loading="lazy">',
    '<div class="cand-intro"><div class="cand-head"><span class="cand-name">', r$name_kr,
      ' <em>', r$name, '</em></span><span class="cand-badge b-', r$party, '">', .c_badge(r),
      '</span></div><p class="cand-sub">', .c_age(r), r$occupation, '</p></div>',
    '<div class="cand-fact"><b>가족</b> ', .c_val(r$family), '</div>',
    '<div class="cand-fact"><b>학력</b> ', .c_val(r$education), '</div>',
    '<div class="cand-fact"><b>경력</b> ', .c_inline(r$past_elections[[1]]), '</div>',
    '<div class="cand-fact"><b>펀드레이징</b> ', .c_val(r$fundraising), '</div>',
    '<div class="cand-fact cand-divide"><b class="t-str">강점</b>', .c_ul(r$strengths[[1]]), '</div>',
    '<div class="cand-fact"><b class="t-wk">약점</b>', .c_ul(r$weaknesses[[1]]), '</div>',
    '<div class="cand-fact"><b>정책</b> ', .c_inline(r$policy[[1]]), '</div>',
    '<div class="cand-fact cand-kr"><b>🇰🇷 한국 함의</b> ', kr, '</div>',
    '<div class="cand-credit">', .c_credit(r), ' &nbsp; ', .c_srcs(r$sources[[1]]), '</div>',
    '</div>'
  )
}

# 경선용 컴팩트(세로형, 가로 나열) 카드
.mini_card <- function(r) {
  paste0(
    '<div class="cand-mini cand-', r$party, '">',
    '<img class="cand-mini-photo" src="/', r$photo, '" alt="', r$name, '" loading="lazy">',
    '<div class="cand-mini-head"><span class="cand-name">', r$name_kr, '</span>',
      '<span class="cand-badge b-', r$party, '">', .c_badge(r), '</span></div>',
    '<p class="cand-en">', r$name, '</p>',
    '<p class="cand-sub">', .c_age(r), r$occupation, '</p>',
    '<ul class="cand-facts">',
      if (!is.na(r$education)) paste0('<li><b>학력</b> ', r$education, '</li>') else "",
      if (!is.na(r$fundraising)) paste0('<li><b>펀드레이징</b> ', r$fundraising, '</li>') else "",
    '</ul>',
    '<p class="cand-line"><b class="t-str">강점</b> ', .c_inline(r$strengths[[1]]), '</p>',
    '<p class="cand-line"><b class="t-wk">약점</b> ', .c_inline(r$weaknesses[[1]]), '</p>',
    '<p class="cand-line"><b>정책</b> ', .c_inline(r$policy[[1]]), '</p>',
    '<p class="cand-credit">', .c_credit(r), ' &nbsp; ', .c_srcs(r$sources[[1]]), '</p>',
    '</div>'
  )
}

.c_status <- function(cc) { s <- cc$status; if (is.null(s)) rep(NA_character_, nrow(cc)) else s }

# 상단: 정당별 1장씩(민주 좌 · 공화 우) — 확정 후보는 정식 카드,
# 경선중인 당은 '후보 미정' 플레이스홀더.
candidate_cards_html <- function(code) {
  d <- .load_json("candidates")
  cc <- d$candidates[d$candidates$state == code, ]
  if (nrow(cc) == 0) return("")
  st <- .c_status(cc)
  is_prim <- !is.na(st) & st == "primary"
  pr <- .load_json("senate_primaries")$rows
  cards <- character(0)
  for (pty in c("D", "R")) {
    nom_p <- cc[!is_prim & cc$party == pty, ]
    if (nrow(nom_p) > 0) {
      for (i in seq_len(nrow(nom_p))) cards <- c(cards, .full_card(nom_p[i, ]))
    } else {
      prim_p <- cc[is_prim & cc$party == pty, ]
      if (nrow(prim_p) > 0) {
        cand_names <- paste(prim_p$name_kr, collapse = " · ")
        kw <- if (pty == "D") "민주" else "공화"
        prow <- pr[pr$state == code & grepl(kw, pr$event), ]
        meta <- if (nrow(prow))
          paste0(ifelse(is.na(prow$date[1]), "", paste0(prow$date[1], " ")), prow$event[1]) else "경선 진행 중"
        cards <- c(cards, paste0(
          '<div class="cand-card cand-', pty, ' cand-ph">',
          '<div class="cand-ph-mark">🗳️</div>',
          '<div class="cand-body"><div class="cand-head">',
            '<span class="cand-name">', .party_kr[[pty]], '당 후보 — 미정</span>',
            '<span class="cand-badge b-', pty, '">경선 중</span></div>',
          '<p class="cand-sub">', meta, '</p>',
          '<p class="cand-line">경쟁 후보: <b>', cand_names, '</b></p>',
          '<p class="cand-line muted">↓ 페이지 하단 <b>경선 후보</b>에서 상세 프로필을 확인하세요.</p>',
          '</div></div>'))
      }
    }
  }
  paste0('<div class="cand-wrap">', paste(cards, collapse = ""), "</div>")
}

# 하단: 경선 후보를 가로로 배치 (없으면 빈 문자열)
primary_cards_html <- function(code) {
  d <- .load_json("candidates")
  cc <- d$candidates[d$candidates$state == code, ]
  if (nrow(cc) == 0) return("")
  st <- .c_status(cc)
  prim <- cc[!is.na(st) & st == "primary", ]
  if (nrow(prim) == 0) return("")
  minis <- vapply(seq_len(nrow(prim)), function(i) .mini_card(prim[i, ]), character(1))
  paste0('<div class="cand-mini-wrap">', paste(minis, collapse = ""), "</div>")
}

# 1.6 자체 모델 대시보드 (정적 폴백 표) -------------------------------------
gt_model_states <- function() {
  d <- .load_json("model_dashboard")
  s <- d$states
  tibble(
    주 = s$name,
    구도 = ifelse(s$defense == "D", "민주 방어", "공화 방어"),
    대결 = s$matchup,
    `D 승리확률` = ifelse(is.na(s$prob), "산정 전", paste0(s$prob, "%")),
    등급 = s$rating,
    `핵심 변수` = s$key_var
  ) |>
    gt() |>
    tab_header(
      title = "경합주 민주당 승리확률 — 자체 분석 모델",
      subtitle = paste0(d$source_label, " · 확률 기준 ", d$as_of, " · 사실 ", d$facts_updated)
    ) |>
    tab_source_note(d$provenance_note) |>
    .tbl_opts()
}

gt_model_scenarios <- function() {
  d <- .load_json("model_dashboard")
  s <- d$scenarios
  tibble(
    시나리오 = paste0(s$name, " (", s$subname, ")"),
    확률 = paste0(s$prob, "%"),
    `의석 결과` = s$seats,
    다수당 = s$majority,
    설명 = s$desc
  ) |>
    gt() |>
    tab_header(title = "상원 시나리오 — 자체 분석 모델",
               subtitle = paste0("다수당 탈환 확률 ", d$dem_majority_prob, "% · 순 기대의석 +", d$net_expected_seats)) |>
    .tbl_opts()
}

# 등급 → 버킷 분류 (Solid D / Lean D / Toss-up / Lean R / Solid R)
.rating_bucket <- function(x) {
  if (grepl("Solid D|Safe D|Likely D", x, ignore.case = TRUE)) "Solid D"
  else if (grepl("Lean", x, ignore.case = TRUE) && grepl("D", x)) "Lean D"
  else if (grepl("Toss", x, ignore.case = TRUE)) "Toss-up"
  else if (grepl("Lean", x, ignore.case = TRUE) && grepl("R", x)) "Lean R"
  else if (grepl("Solid R|Safe R|Likely R", x, ignore.case = TRUE)) "Solid R"
  else "기타"
}

model_rating_counts <- function() {
  d <- .load_json("model_dashboard")
  b <- vapply(d$states$rating, .rating_bucket, character(1))
  cats <- c("Solid D", "Lean D", "Toss-up", "Lean R", "Solid R")
  setNames(vapply(cats, function(k) sum(b == k), integer(1)), cats)
}

# 등급 분포를 5개 타일 HTML로 (각 타일에 해당 주 명칭 + 링크)
rating_tiles_html <- function() {
  d <- .load_json("model_dashboard"); s <- d$states
  b <- vapply(s$rating, .rating_bucket, character(1))
  defs <- list(c("Solid D", "rt-sd"), c("Lean D", "rt-ld"), c("Toss-up", "rt-tu"),
               c("Lean R", "rt-lr"), c("Solid R", "rt-sr"))
  tiles <- vapply(defs, function(x) {
    idx <- which(b == x[1])
    states <- if (length(idx) == 0) '<span class="rt-empty">—</span>' else
      paste0(vapply(idx, function(i) sprintf(
        '<div class="rt-st"><a href="/states/%s.html">%s</a><span class="rt-hold rt-hold-%s">%s</span></div>',
        s$id[i], s$name[i], tolower(s$defense[i]), s$defense[i]), character(1)),
        collapse = "")
    sprintf('<div class="rtile %s"><div class="rt-num">%d</div><div class="rt-lab">%s</div><div class="rt-states">%s</div></div>',
            x[2], length(idx), x[1], states)
  }, character(1))
  paste0('<div class="rating-tiles">', paste(tiles, collapse = ""), "</div>")
}

# 현 보유 정당 요약 (defense 기준) + 탈환 표적
holder_note_html <- function() {
  d <- .load_json("model_dashboard"); s <- d$states
  dh <- s$name[s$defense == "D"]; rh <- s$name[s$defense == "R"]
  b <- vapply(s$rating, .rating_bucket, character(1))
  flip <- s$name[s$defense == "R" & b %in% c("Lean D", "Solid D")]
  paste0(
    '<p class="holder-note">',
    '<span class="hold-chip hold-d">현 민주 ', length(dh), '석</span> ', paste(dh, collapse = " · "),
    ' &nbsp; <span class="hold-chip hold-r">현 공화 ', length(rh), '석</span> ', paste(rh, collapse = " · "), '.',
    if (length(flip) > 0) paste0(
      ' 이 중 <b>공화 보유이면서 민주 우세(Lean D)</b>인 <b>', paste(flip, collapse = "·"),
      '</b>가 민주당 탈환 1순위 — 각 타일의 <span class="rt-hold rt-hold-d">D</span>/',
      '<span class="rt-hold rt-hold-r">R</span> 배지가 현 보유 정당입니다.') else "",
    '</p>')
}

# 홈 요약용 KPI 값 (리스트 반환)
model_kpi <- function() {
  d <- .load_json("model_dashboard")
  n_states <- nrow(d$states)
  probs <- d$states$prob
  probs <- probs[!is.na(probs)]   # 확률 미산정 주(prob=null)는 평균·우세 집계에서 제외
  dem_wins <- sum(probs >= 50)
  list(
    as_of = d$as_of, facts = d$facts_updated,
    balance = d$current_balance, needed = d$dem_needed_net,
    majority = d$dem_majority_prob, net = d$net_expected_seats,
    dem_wins = dem_wins, n = n_states, n_scored = length(probs),
    avg = sprintf("%.1f", mean(probs)),
    base_seats = d$scenarios$seats[d$scenarios$id == "base"]
  )
}

# 1.5 신규 여론조사 로그 ----------------------------------------------------
gt_polls_log <- function() {
  readr::read_csv(file.path("data", "polls_log.csv"), show_col_types = FALSE) |>
    arrange(desc(date)) |>
    gt() |>
    tab_header(title = "이번 주 신규 여론조사 로그",
               subtitle = "모집단(A/RV/LV)·방식·스폰서를 항상 병기") |>
    .tbl_opts()
}

# 2.1 하원 경합구 트래커 ------------------------------------------------------
# data/house_races.json — Cook 토스업 명단 중심. 빈 값은 — / 【수집】 렌더.
gt_house_races <- function() {
  d <- .load_json("house_races")
  r <- d$races
  tibble(
    지역구 = r$district,
    `현역` = r$incumbent,
    보유 = ifelse(r$party == "D", "민주", "공화"),
    `등급(Cook)` = r$rating_cook,
    `등급(Sabato)` = ifelse(is.na(r$rating_sabato), "【수집】", r$rating_sabato),
    `전주 대비` = ifelse(is.na(r$rating_delta), "—", r$rating_delta),
    `2024 마진` = ifelse(is.na(r$margin_2024), "【수집】", .fmt_margin(r$margin_2024)),
    비고 = ifelse(is.na(r$note), "—", r$note)
  ) |>
    arrange(보유, 지역구) |>
    gt(groupname_col = "보유") |>
    tab_header(
      title = "하원 경합구 트래커 — Cook 토스업",
      subtitle = paste0("기준 ", d$as_of, " · ", d$cook_outlook, " · ", d$source_label)
    ) |>
    .tbl_opts()
}

# 2.1b 전국 경제 지표 ---------------------------------------------------------
# data/national_econ.json — scripts/fetch_national_econ.py(FRED)가 생성.
# 파일이 없으면 【수집】 안내만 렌더 (빌드 실패 방지).
gt_national_econ <- function() {
  path <- file.path("data", "national_econ.json")
  if (!file.exists(path)) {
    return(tibble(안내 = "data/national_econ.json 미생성 — scripts/fetch_national_econ.py 실행 후 채워집니다.") |>
             gt() |> tab_header(title = "경제 지표") |> .tbl_opts())
  }
  d <- jsonlite::read_json(path, simplifyVector = TRUE)
  r <- d$rows
  tibble(
    지표 = r$indicator,
    최신값 = ifelse(is.na(r$value), "【수집】",
                 paste0(r$value, ifelse(r$unit == "%", "%", ""))),
    기준월 = ifelse(is.na(r$period), "—", r$period),
    `선거 함의` = r$election_note
  ) |>
    gt() |>
    tab_header(title = "경제 지표 — 선거 환경 직결분",
               subtitle = paste0("기준 ", d$as_of, " · ", d$source_label)) |>
    .tbl_opts()
}

# 2.2 Korea Watch 동향 표 ------------------------------------------------------
# data/korea_watch.csv — 누적 DB. 스키마 고정(열 추가·변경 금지):
# date,type,actor,affiliation,state_or_district,event,detail,race_link,significance,source_url
gt_korea_watch <- function(n = 30) {
  kw <- readr::read_csv(file.path("data", "korea_watch.csv"),
                        show_col_types = FALSE,
                        col_types = readr::cols(.default = readr::col_character(),
                                                significance = readr::col_integer()))
  if (nrow(kw) == 0) {
    return(tibble(안내 = "수집된 항목이 아직 없습니다 — Korea Watch 일일 수집 시작 후 이 표가 채워집니다.") |>
             gt() |> tab_header(title = "Korea Watch — 한국 관련 동향") |> .tbl_opts())
  }
  kw |>
    arrange(desc(date)) |>
    head(n) |>
    mutate(중요도 = strrep("★", significance)) |>
    transmute(
      날짜 = date, 유형 = type, 행위자 = actor,
      소속 = ifelse(is.na(affiliation), "—", affiliation),
      내용 = event,
      `선거 연관` = ifelse(is.na(race_link), "—", race_link),
      중요도,
      출처 = ifelse(is.na(source_url), "—",
                  paste0("<a href='", source_url, "'>링크</a>"))
    ) |>
    gt() |>
    fmt_markdown(columns = "출처") |>
    tab_header(title = "Korea Watch — 한국 관련 동향 (최신순)",
               subtitle = paste0("누적 ", nrow(kw), "건 중 최근 ", min(n, nrow(kw)), "건 표시")) |>
    .tbl_opts()
}

# 2.3 재획정 주별 현황 --------------------------------------------------------
# data/redistricting_states.json — 양수=민주 순증(D+), 음수=공화 순증(R+).
.seat_lab <- function(x) ifelse(is.na(x) | x == 0, "—",
                         ifelse(x > 0, paste0("D+", x), paste0("R+", abs(x))))

gt_redistricting_states <- function() {
  d <- .load_json("redistricting_states")
  s <- d$states
  grp <- c(enacted = "시행 (2026 사용)", blocked = "차단", failed = "무산·정체")
  net_disp <- ifelse(s$category == "blocked",
                     paste0("— (의도 ", .seat_lab(s$intended_d), ")"),
                     .seat_lab(s$net_d))
  tibble(
    구분 = grp[s$category],
    주 = paste0(s$name, " (", s$state, ")"),
    획정주체 = s$drawer,
    상태 = s$status,
    순효과 = net_disp,
    `시행·근거` = s$enacted,
    출처 = paste0("<a href='", s$source_url, "'>", s$source, "</a>")
  ) |>
    gt(groupname_col = "구분") |>
    fmt_markdown(columns = "출처") |>
    tab_header(title = "재획정 주별 현황 — 누가·어떻게·순효과",
               subtitle = paste0("기준 ", d$as_of, " · ", d$net_enacted_label,
                                 " · 양수=민주 순증(D+)")) |>
    tab_source_note(d$note) |>
    .tbl_opts()
}

# 순효과 다이버징 바 (인라인 SVG) — `#| output: asis` 청크에서 cat() 으로 출력.
# 시행·차단 지도만 표시(차단은 의도 의석을 흐리게). enacted=net_d, blocked=intended_d.
svg_redistricting_bar <- function() {
  d <- .load_json("redistricting_states")
  s <- d$states[d$states$category %in% c("enacted", "blocked"), ]
  val <- ifelse(s$category == "blocked", s$intended_d, s$net_d)
  blocked <- s$category == "blocked"
  ord <- order(val, decreasing = TRUE)
  s <- s[ord, ]; val <- val[ord]; blocked <- blocked[ord]
  n <- nrow(s)
  rowh <- 28; top <- 34; bot <- 14; cx <- 270; per <- 30; W <- 560
  H <- top + n * rowh + bot
  dem <- "#1971c2"; rep <- "#c92a2a"
  p <- sprintf('<svg viewBox="0 0 %d %d" width="100%%" style="height:auto;max-width:%dpx;display:block;margin:8px auto;font-family:\'IBM Plex Sans KR\',sans-serif;" role="img" aria-label="재획정 주별 순효과 다이버징 바">', W, H, W)
  p <- c(p, sprintf('<line x1="%d" y1="%d" x2="%d" y2="%.0f" stroke="#ced4da" stroke-width="1"/>', cx, top - 4, cx, H - bot + 2))
  p <- c(p, sprintf('<text x="%d" y="%d" text-anchor="end" font-size="10" fill="%s">← 공화 순증(R+)</text>', cx - 8, top - 12, rep))
  p <- c(p, sprintf('<text x="%d" y="%d" text-anchor="start" font-size="10" fill="%s">민주 순증(D+) →</text>', cx + 8, top - 12, dem))
  for (i in seq_len(n)) {
    y <- top + (i - 1) * rowh
    v <- val[i]; w <- abs(v) * per
    col <- if (v >= 0) dem else rep
    op <- if (blocked[i]) "0.35" else "1"
    x0 <- if (v >= 0) cx else cx - w
    p <- c(p, sprintf('<rect x="%.1f" y="%d" width="%.1f" height="16" rx="2" fill="%s" fill-opacity="%s"/>', x0, y, w, col, op))
    lab <- paste0(s$state[i], " ", .seat_lab(v), if (blocked[i]) " (차단)" else "")
    if (v >= 0) {
      p <- c(p, sprintf('<text x="%.1f" y="%d" text-anchor="start" font-size="11" fill="#3a3a3a">%s</text>', cx + w + 6, y + 12, lab))
    } else {
      p <- c(p, sprintf('<text x="%.1f" y="%d" text-anchor="end" font-size="11" fill="#3a3a3a">%s</text>', cx - w - 6, y + 12, lab))
    }
  }
  paste(c(p, '</svg>'), collapse = "")
}

# 2.4 지역구별 2024 대선 마진 변화 (재획정) ----------------------------------
# data/redistricting_pres.json — 같은 2024 표를 신·구 경계로 재집계. 양수=민주(D+).
gt_redistricting_pres <- function() {
  d <- .load_json("redistricting_pres")
  r <- d$districts
  dm <- r$new_margin - r$old_margin
  delta <- ifelse(is.na(dm), "【수집】",
            ifelse(dm < 0, paste0("R+", abs(round(dm, 1)), "p 이동"),
            ifelse(dm > 0, paste0("D+", round(dm, 1), "p 이동"), "변화 없음")))
  tibble(
    지역구 = paste0(r$district, " — ", r$name),
    현역 = r$incumbent,
    `구지도(2024)` = ifelse(is.na(r$old_margin), "【수집】", .fmt_margin(r$old_margin)),
    `신지도(2024)` = ifelse(is.na(r$new_margin), "【수집】", .fmt_margin(r$new_margin)),
    `변화(Δ)` = delta,
    출처 = paste0("<a href='", r$source_url, "'>", r$source, "</a>")
  ) |>
    gt() |>
    fmt_markdown(columns = "출처") |>
    tab_header(title = "지역구별 2024 대선 마진 — 구지도 vs 신지도",
               subtitle = paste0("기준 ", d$as_of,
                                 " · 양수=민주 우위(D+) · 같은 2024년 표를 새 경계로 재집계")) |>
    tab_source_note(d$note) |>
    .tbl_opts()
}

# 지역구 마진 이동 덤벨 (인라인 SVG) — old·new 둘 다 있는 구만 표시.
# `#| output: asis` 청크에서 cat()으로 출력. 완전 쌍이 없으면 빈 문자열.
svg_redistricting_dumbbell <- function() {
  d <- .load_json("redistricting_pres")
  r <- d$districts
  keep <- !is.na(r$old_margin) & !is.na(r$new_margin)
  r <- r[keep, , drop = FALSE]
  n <- nrow(r)
  if (n == 0) return("")
  r <- r[order(r$new_margin), , drop = FALSE]   # 가장 공화(음수) 위로
  lim <- max(5, ceiling(max(abs(c(r$old_margin, r$new_margin))) / 5) * 5)
  W <- 600; padL <- 84; padR <- 64; plotW <- W - padL - padR
  cx <- padL + plotW / 2
  sc <- function(m) cx + (m / lim) * (plotW / 2)
  rowh <- 36; top <- 46; bot <- 24
  H <- top + n * rowh + bot
  dem <- "#1971c2"; rep <- "#c92a2a"; gray <- "#adb5bd"
  fmtm <- function(m) ifelse(m >= 0, paste0("D+", abs(round(m, 1))), paste0("R+", abs(round(m, 1))))
  p <- sprintf('<svg viewBox="0 0 %d %d" width="100%%" style="height:auto;max-width:%dpx;display:block;margin:8px auto;font-family:\'IBM Plex Sans KR\',sans-serif;" role="img" aria-label="지역구 2024 대선 마진 구→신 이동 덤벨">', W, H, W)
  # 중앙 0선 + 축 라벨
  p <- c(p, sprintf('<line x1="%.0f" y1="%d" x2="%.0f" y2="%.0f" stroke="#ced4da" stroke-width="1"/>', cx, top - 6, cx, H - bot + 2))
  p <- c(p, sprintf('<text x="%.0f" y="%d" text-anchor="middle" font-size="10" fill="#868e96">0</text>', cx, top - 12))
  p <- c(p, sprintf('<text x="%.0f" y="%d" text-anchor="middle" font-size="10" fill="%s">← 공화(R+)</text>', cx - plotW / 4, top - 12, rep))
  p <- c(p, sprintf('<text x="%.0f" y="%d" text-anchor="middle" font-size="10" fill="%s">민주(D+) →</text>', cx + plotW / 4, top - 12, dem))
  for (i in seq_len(n)) {
    y <- top + (i - 1) * rowh + rowh / 2
    xo <- sc(r$old_margin[i]); xn <- sc(r$new_margin[i])
    ncol <- if (r$new_margin[i] >= 0) dem else rep
    # 구역명 라벨(좌측 거터)
    p <- c(p, sprintf('<text x="%d" y="%.0f" text-anchor="end" font-size="11" font-weight="700" fill="#3a3a3a">%s</text>', padL - 10, y + 4, r$district[i]))
    # 연결선
    p <- c(p, sprintf('<line x1="%.1f" y1="%.0f" x2="%.1f" y2="%.0f" stroke="%s" stroke-width="2"/>', xo, y, xn, y, gray))
    # old 점(빈 원) + new 점(채운 원)
    p <- c(p, sprintf('<circle cx="%.1f" cy="%.0f" r="5" fill="#fff" stroke="%s" stroke-width="2"/>', xo, y, gray))
    p <- c(p, sprintf('<circle cx="%.1f" cy="%.0f" r="5.5" fill="%s"/>', xn, y, ncol))
    # 값 라벨: old(작게 위), new(바깥쪽)
    p <- c(p, sprintf('<text x="%.1f" y="%.0f" text-anchor="middle" font-size="9" fill="%s">%s</text>', xo, y - 9, gray, fmtm(r$old_margin[i])))
    nx <- if (r$new_margin[i] <= r$old_margin[i]) xn - 9 else xn + 9
    anc <- if (r$new_margin[i] <= r$old_margin[i]) "end" else "start"
    p <- c(p, sprintf('<text x="%.1f" y="%.0f" text-anchor="%s" font-size="10" font-weight="700" fill="%s">%s</text>', nx, y + 4, anc, ncol, fmtm(r$new_margin[i])))
  }
  # 범례
  ly <- H - 8
  p <- c(p, sprintf('<circle cx="%d" cy="%.0f" r="5" fill="#fff" stroke="%s" stroke-width="2"/><text x="%d" y="%.0f" font-size="10" fill="#5a6672">구지도</text>', padL, ly - 4, gray, padL + 10, ly))
  p <- c(p, sprintf('<circle cx="%d" cy="%.0f" r="5.5" fill="%s"/><text x="%d" y="%.0f" font-size="10" fill="#5a6672">신지도(2024 재집계)</text>', padL + 80, ly - 4, rep, padL + 92, ly))
  paste(c(p, '</svg>'), collapse = "")
}

# ============================================================================
# 홈 컨트롤 패널 — 첫 화면 KPI 카드 + 모듈. 기존 데이터만 사용, 추정 없음.
# 데이터 이상 시 빈 문자열로 graceful degrade (빌드 안전).
# ============================================================================

# KPI 카드 4장: 다수당 확률 · 순 기대의석 · 트럼프 순지지 · 일반투표 마진.
# 각 카드에 해석 한 줄 포함. 기존 데이터만 사용(추정 없음), 오류 시 빈 문자열.
home_kpis <- function() {
  tryCatch({
    k  <- model_kpi()
    td <- .load_json("trends")
    tn <- td$weeks$trump_net[!is.na(td$weeks$trump_net)]
    gb <- td$weeks$generic[!is.na(td$weeks$generic)]
    tn <- if (length(tn)) tn[length(tn)] else NA
    gb <- if (length(gb)) gb[length(gb)] else NA
    card <- function(cls, num, lab, sub, interp)
      sprintf(paste0('<div class="kpi %s"><div class="kpi-num">%s</div>',
                     '<div class="kpi-lab">%s</div><div class="kpi-sub">%s</div>',
                     '<div class="kpi-interp">%s</div></div>'),
              cls, num, lab, sub, interp)
    paste0('<div class="kpis">',
      card("kpi-d", paste0(k$majority, "%"), "민주 다수당 탈환 확률",
           paste0("자체 모델 · ", k$as_of),
           sprintf("다수까지 순 +%d석 필요 — 모델상 경합권", k$needed)),
      card("kpi-d", paste0("+", k$net), "순 기대의석 (민주)",
           "자체 모델 기대값",
           "공화 표적 5곳 · 민주 수성 3곳의 순증"),
      card("kpi-r", ifelse(is.na(tn), "—", sprintf("%+.1f", tn)), "트럼프 순지지도",
           paste0("Silver Bulletin · ~", td$as_of),
           "낮을수록 민주 우호 — 2기 최저권"),
      card("kpi-d", .fmt_margin(gb), "일반투표 마진",
           paste0("보고 주 기준 · ~", td$as_of),
           "양수=민주 우위 — 중간선거 역풍 환경"),
    '</div>')
  }, error = function(e) "")
}
