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

# 1.4c-2 주별 여론조사 표 (State Focus용) ------------------------------------
# data/senate_polls.csv 를 그대로 렌더 — 프로즈에 수치를 박지 않고 데이터에서 끌어오므로
# 주간 발행 때 조사가 추가되면 각 주 페이지가 자동으로 최신화된다.
gt_state_polls <- function(code) {
  p <- readr::read_csv(file.path("data", "senate_polls.csv"), show_col_types = FALSE)
  p <- p[p$state == code, ]
  if (nrow(p) == 0) {
    return(gt(tibble(안내 = "이 주의 본선 여론조사가 아직 데이터베이스에 없습니다(추정으로 채우지 않음).")) |>
             tab_header(title = "최신 여론조사") |> .tbl_opts())
  }
  p <- p[order(p$end_date, decreasing = TRUE), ]
  fld <- function(x, alt = "—") ifelse(is.na(x) | x == "", alt, as.character(x))
  period <- ifelse(is.na(p$start_date) | p$start_date == "",
                   paste0("~", fld(p$end_date)),
                   paste0(fld(p$start_date), " ~ ", fld(p$end_date)))
  house <- ifelse(is.na(p$partisan) | p$partisan == "none", "",
                  paste0(" (", p$partisan, " 성향)"))
  res <- paste0(fld(p$dem_candidate), " ", fld(p$dem_pct), " – ",
                fld(p$rep_pct), " ", fld(p$rep_candidate))
  tibble(
    조사기관 = paste0(p$pollster, house),
    실사기간 = period,
    모집단 = fld(p$population),
    표본 = fld(p$n),
    결과 = res,
    마진 = .fmt_margin(suppressWarnings(as.numeric(p$margin))),
    비고 = fld(p$note, "")
  ) |>
    gt() |>
    tab_header(title = "최신 여론조사",
               subtitle = paste0("최신순 · ", nrow(p), "건 · 양수 = 민주 우위(D+)")) |>
    tab_source_note(paste0(
      "출처 URL은 `data/senate_polls.csv`에 행별로 보관합니다. 당파 후원(D/R 성향) 조사는 공개 선택 편향이 있으니 ",
      "단일 조사보다 여러 조사의 방향을 함께 보세요. 표는 데이터에서 자동 렌더되며 새 조사가 들어오면 갱신됩니다.")) |>
    .tbl_opts()
}

# 최신 자금 상황 한 줄 (senate_races.json의 cash_on_hand — 매주 자동 갱신되는 값)
state_money_html <- function(code) {
  d <- .load_json("senate_races")
  r <- d$races[d$races$state == code, ]
  v <- if (nrow(r) && !is.na(r$cash_on_hand)) r$cash_on_hand else NA
  body <- if (is.na(v))
    "이 주의 최신 분기 자금 요약은 아직 데이터에 없습니다(【수집】 — 추정으로 채우지 않음)."
  else v
  paste0('<div class="lookfor"><p><b>최신 자금 상황</b> (기준 ', d$as_of, ') — ', body, '</p></div>')
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
    `시장 가격(D)` = ifelse(is.na(s$prob), "미확인", paste0(s$prob, "%")),
    등급 = s$rating,
    `핵심 변수` = s$key_var
  ) |>
    gt() |>
    tab_header(
      title = "경합주 판세 — 외부 예측 종합 (등급·예측시장)",
      subtitle = paste0(d$source_label, " · 확률 기준 ", d$as_of, " · 사실 ", d$facts_updated)
    ) |>
    tab_source_note(d$provenance_note) |>
    .tbl_opts()
}

# 등급 변동 매트릭스 — 기관(Cook/Sabato) × 주 × 월. 굵은 테두리 = 그 달의 등급 이동.
# 데이터: data/rating_history.json (status: confirmed/derived/unknown — 추정으로 채우지 않음)
rating_matrix_html <- function() {
  d <- .load_json("rating_history")
  cls <- function(r) {
    if (is.null(r) || is.na(r) || r == "") return("rmx-unk")
    if (grepl("Solid D|Safe D", r)) "rmx-sd"
    else if (grepl("Likely D", r)) "rmx-kd"
    else if (grepl("Lean D", r)) "rmx-ld"
    else if (grepl("Toss", r, ignore.case = TRUE)) "rmx-tu"
    else if (grepl("Lean R", r)) "rmx-lr"
    else if (grepl("Likely R", r)) "rmx-kr"
    else if (grepl("Solid R|Safe R", r)) "rmx-sr"
    else "rmx-unk"
  }
  months <- d$months
  panels <- vapply(seq_len(nrow(d$agencies)), function(ai) {
    ag <- d$agencies[ai, ]
    rows <- ag$rows[[1]]
    head <- paste0('<div class="rmx-corner"></div>',
                   paste0('<div class="rmx-mon">', months, '</div>', collapse = ""))
    body <- vapply(seq_len(nrow(rows)), function(ri) {
      cells <- rows$cells[[ri]]
      tds <- vapply(seq_len(nrow(cells)), function(ci) {
        st <- cells$status[ci]
        r  <- if (is.na(cells$r[ci])) "" else cells$r[ci]
        lab <- if (st == "unknown" || r == "") "미확인" else r
        chg <- !is.na(cells$changed[ci]) && isTRUE(cells$changed[ci])
        note <- if (!is.null(cells$note) && !is.na(cells$note[ci])) cells$note[ci] else ""
        sprintf('<div class="rmx-cell %s%s%s" title="%s">%s%s</div>',
                cls(if (st == "unknown") "" else r),
                if (chg) " rmx-chg" else "",
                if (st == "derived") " rmx-drv" else "",
                htmltools::htmlEscape(note), lab,
                if (st == "derived") '<span class="rmx-drv-m">*</span>' else "")
      }, character(1))
      paste0('<div class="rmx-state" title="', rows$name[ri], '">', rows$state[ri], '</div>',
             paste(tds, collapse = ""))
    }, character(1))
    sprintf('<div class="rmx-panel"><div class="rmx-title">%s</div><div class="rmx-grid">%s%s</div></div>',
            ag$name, head, paste(body, collapse = ""))
  }, character(1))

  legend <- paste0(
    '<div class="rmx-legend">',
    '<span class="rmx-key rmx-ld"></span>Lean D',
    '<span class="rmx-key rmx-kd"></span>Likely D',
    '<span class="rmx-key rmx-tu"></span>Toss-up',
    '<span class="rmx-key rmx-lr"></span>Lean R',
    '<span class="rmx-key rmx-kr"></span>Likely R',
    '<span class="rmx-key rmx-sr"></span>Safe/Solid R',
    '<span class="rmx-key rmx-chg-key"></span>굵은 테두리 = 그 달 이동',
    '<span class="rmx-drv-m">*</span>= 역산(이후 이동 서술의 이전 등급)',
    '</div>')
  note <- paste0(
    '<p class="rmx-note">각 칸은 <b>해당 월말 기준</b> 등급입니다. ',
    '등급은 확률이 아닌 서수적 판단이며, 기관은 상시 갱신하므로 <b>아카이브에서 확인된 것만</b> 표기하고 ',
    '기록이 없으면 <b>미확인</b>으로 둡니다(추정으로 채우지 않음). ',
    '주요 이동: <b>4/13</b> Cook GA·NC를 Lean D로, OH를 Toss-up으로 · <b>5/31</b> Cook TX Likely R→Lean R(팩스턴 경선승) · ',
    '<b>6/11</b> Sabato NC Lean D·AK/OH Toss-up 일괄 이동 · <b>6월 하순</b> Cook OH Lean R 회귀 · <b>7/1</b> Cook AK Toss-up. ',
    '기준 ', d$as_of, '.</p>')
  paste0('<div class="rmx-wrap">', paste(panels, collapse = ""), "</div>", legend, note)
}

# 1.6b 타일 격자 지도 (상원·주지사) -------------------------------------------
# 지리 지도는 RI·DE·NH 같은 작은 주가 보이지 않아 선거 지도로 부적합하다.
# 각 주를 같은 크기 칸으로 배치하는 타일 격자(tile grid)로 그려 모든 주를 동등하게 읽게 한다.
# 외부 CDN·토폴로지 의존 없음(인라인 SVG) — 오프라인·인쇄에서도 동일하게 렌더된다.
.TILE <- list(
  AK=c(0,0), ME=c(0,10),
  VT=c(1,9), NH=c(1,10),
  WA=c(2,0), ID=c(2,1), MT=c(2,2), ND=c(2,3), MN=c(2,4), IL=c(2,5), WI=c(2,6), MI=c(2,7), NY=c(2,8), RI=c(2,9), MA=c(2,10),
  OR=c(3,0), NV=c(3,1), WY=c(3,2), SD=c(3,3), IA=c(3,4), IN=c(3,5), OH=c(3,6), PA=c(3,7), NJ=c(3,8), CT=c(3,9),
  CA=c(4,0), UT=c(4,1), CO=c(4,2), NE=c(4,3), MO=c(4,4), KY=c(4,5), WV=c(4,6), VA=c(4,7), MD=c(4,8), DE=c(4,9),
  AZ=c(5,1), NM=c(5,2), KS=c(5,3), AR=c(5,4), TN=c(5,5), NC=c(5,6), SC=c(5,7),
  OK=c(6,3), LA=c(6,4), MS=c(6,5), AL=c(6,6), GA=c(6,7),
  HI=c(7,0), TX=c(7,3), FL=c(7,8)
)
# 9단계 — Tilt는 Lean보다 **좁은**(더 접전인) 등급이라 Lean과 Toss-up 사이에 놓는다.
# Inside Elections·RaceToTheWH·Kalshi가 이 눈금을 쓴다(Cook·Sabato는 쓰지 않는다).
.RATING_FILL <- c("Solid D" = "#2166ac", "Likely D" = "#6ba3d6", "Lean D" = "#b9d9ee",
                  "Tilt D" = "#dceaf5", "Toss-up" = "#e5e7eb", "Tilt R" = "#fce0d2",
                  "Lean R" = "#f6b89c", "Likely R" = "#d6604d", "Solid R" = "#b2182b")
.RATING_INK <- c("Solid D" = "#ffffff", "Likely D" = "#0c2c47", "Lean D" = "#123a5c",
                 "Tilt D" = "#1d4a70", "Toss-up" = "#374151", "Tilt R" = "#6b2d12",
                 "Lean R" = "#6b2d12", "Likely R" = "#ffffff", "Solid R" = "#ffffff")

# kind: "senate" | "governor" · 등급 원천은 270towin 재게시 피드(자동 취득)
us_tile_map_html <- function(kind = c("senate", "governor"),
                             primary = "270toWin Consensus") {
  kind <- match.arg(kind)
  d <- .load_json(if (kind == "senate") "senate_ratings_feed" else "governor_ratings")
  src <- d$sources; rt <- src$ratings
  ip <- which(src$label == primary)
  if (!length(ip)) ip <- 1
  ip <- ip[1]
  get1 <- function(i, ab) {
    if (is.na(i) || !(ab %in% names(rt))) return(NA_character_)
    v <- rt[i, ab]; if (is.null(v) || length(v) == 0 || is.na(v)) NA_character_ else as.character(v)
  }
  i_cook <- which(src$label == "Cook Political Report"); i_cook <- if (length(i_cook)) i_cook[1] else NA
  i_sab <- which(grepl("Sabato", src$label)); i_sab <- if (length(i_sab)) i_sab[1] else NA

  S <- 46; G <- 5; PAD <- 6            # 타일 크기·간격·여백
  W <- PAD * 2 + 11 * S + 10 * G
  H <- PAD * 2 + 8 * S + 7 * G
  tiles <- character(0)
  n_race <- 0
  for (ab in names(.TILE)) {
    rc <- .TILE[[ab]]
    x <- PAD + rc[2] * (S + G); y <- PAD + rc[1] * (S + G)
    r <- get1(ip, ab)
    has <- !is.na(r)
    if (has) n_race <- n_race + 1
    fill <- if (has && r %in% names(.RATING_FILL)) .RATING_FILL[[r]] else "#f7f7f6"
    ink <- if (has && r %in% names(.RATING_INK)) .RATING_INK[[r]] else "#b9b9b6"
    ck <- get1(i_cook, ab); sb <- get1(i_sab, ab)
    tip <- if (!has) paste0(ab, " — 2026 ", if (kind == "senate") "상원" else "주지사", " 선거 없음")
           else paste0(ab, " · ", primary, ": ", r,
                       if (!is.na(ck)) paste0(" · Cook: ", ck) else "",
                       if (!is.na(sb)) paste0(" · Sabato: ", sb) else "")
    stroke <- if (has) "#ffffff" else "#ececeb"
    tiles <- c(tiles, sprintf(
      paste0('<g><title>%s</title>',
             '<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="1.5"/>',
             '<text x="%d" y="%d" text-anchor="middle" font-size="13" font-weight="700" fill="%s">%s</text>',
             '</g>'),
      htmltools::htmlEscape(tip), x, y, S, S, fill, stroke,
      x + S %/% 2, y + S %/% 2 + 5L, ink, ab))
  }
  legend <- paste0('<div class="tilemap-legend">',
    paste0(vapply(names(.RATING_FILL), function(k)
      sprintf('<span class="tm-key"><i style="background:%s"></i>%s</span>', .RATING_FILL[[k]], k),
      character(1)), collapse = ""),
    '<span class="tm-key"><i style="background:#f7f7f6;border:1px solid #e1e0d9"></i>선거 없음</span></div>')
  as_of <- src$as_of[ip]
  cap <- sprintf(paste0('<p class="tilemap-cap">각 칸 = 한 개 주(면적이 아닌 <b>같은 크기</b>로 그려 작은 주도 동등하게 보이게 함). ',
                        '색은 <b>%s</b> 등급(기준 %s) · 칸에 마우스를 올리면 Cook·Sabato 등급이 함께 표시됩니다. ',
                        '2026년 선거가 있는 주 <b>%d곳</b>. 등급은 확률이 아닙니다.</p>'),
                 primary, as_of, n_race)
  sprintf(paste0('<div class="tilemap"><svg viewBox="0 0 %d %d" width="100%%" style="height:auto;display:block;',
                 'font-family:\'IBM Plex Sans KR\',sans-serif;" role="img" aria-label="%s 2026 선거 타일 지도 — %s 등급 기준 %s">%s</svg></div>%s%s'),
          W, H, if (kind == "senate") "상원" else "주지사", primary, as_of,
          paste(tiles, collapse = ""), legend, cap)
}

# 예측시장(Kalshi) 원가격 ------------------------------------------------------
# 270towin은 Kalshi 가격을 Cook과 같은 7단계로 '환산'해 재게시한다. 환산값만 보면
# 91¢가 'Solid D'로 보여 등급과 구분되지 않으므로, 사이트는 원가격을 직접 싣는다.
# 파일이 없으면 NULL — 호출부는 표를 그리지 않고 안내문을 낸다(빌드 안전).
.kalshi <- function() {
  p <- file.path("data", "kalshi_prices.json")
  if (!file.exists(p)) return(NULL)
  jsonlite::read_json(p, simplifyVector = TRUE)
}

# 특정 주의 민주 가격(%) — 없으면 NA
.kalshi_dem <- function(k, kind, ab) {
  if (is.null(k)) return(NA_real_)
  m <- k[[kind]]
  if (is.null(m) || !(ab %in% names(m))) return(NA_real_)
  v <- m[[ab]]$dem
  if (is.null(v) || length(v) == 0 || is.na(v)) NA_real_ else as.numeric(v)
}

.fmt_price <- function(x) ifelse(is.na(x), "—", paste0(round(x), "¢"))

# 상원 다수 시장 — 모델 전망과 나란히 놓아 '같은 질문, 다른 답'을 드러낸다.
kalshi_control_html <- function() {
  k <- .kalshi()
  if (is.null(k) || is.null(k$senate_control)) {
    return('<p class="note">예측시장 상원 다수 가격 【수집】 — <code>scripts/fetch_kalshi_prices.py</code> 실행 필요.</p>')
  }
  c0 <- k$senate_control
  md <- .load_json("model_dashboard")
  model_p <- suppressWarnings(as.numeric(md$dem_majority_prob))
  sprintf(paste0(
    '<div class="mkt-control">',
    '<div class="mkt-row"><span class="mkt-lab">예측시장 <b>Kalshi</b> — 민주 상원 다수</span>',
    '<span class="mkt-val mkt-d">%s%%</span></div>',
    '<div class="mkt-bar"><i style="width:%s%%"></i></div>',
    '<div class="mkt-row mkt-sub"><span>같은 질문에 대한 외부 <b>모델</b> 전망</span><span class="mkt-val">%s</span></div>',
    '<p class="mkt-note">시장은 <b>가격</b>(확률의 근사·유동성과 편향 혼입), 모델은 <b>방법론의 산출물</b>입니다. ',
    '두 값의 격차 자체가 이번 사이클의 핵심 쟁점입니다 — 시장은 개별 주에서 민주를 모델보다 후하게 봅니다. ',
    '계약: “%s” · 거래액 $%s · 미결제약정 $%s · 기준 %s(UTC). ',
    '<a href="%s" rel="nofollow">Kalshi 원장</a></p></div>'),
    format(c0$dem, nsmall = 0), format(c0$dem, nsmall = 0),
    if (is.na(model_p)) "—" else paste0(model_p, "%"),
    htmltools::htmlEscape(c0$question %||% ""),
    format(c0$volume, big.mark = ","), format(c0$open_interest, big.mark = ","),
    k$fetched_at_utc, c0$url)
}

`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

# 예측시장 가격표 — 상원/주지사 공용. 등급표와 **분리**해 잣대 혼동을 막는다.
gt_kalshi_races <- function(kind = c("senate", "governor"), states = NULL, min_dem = NULL) {
  kind <- match.arg(kind)
  k <- .kalshi()
  if (is.null(k)) return(invisible(NULL))
  m <- k[[kind]]
  ab <- names(m)
  if (!is.null(states)) ab <- intersect(states, ab)
  dem <- vapply(ab, function(a) .kalshi_dem(k, kind, a), numeric(1))
  if (!is.null(min_dem)) ab <- ab[!is.na(dem) & dem >= min_dem[1] & dem <= min_dem[2]]
  if (!length(ab)) return(invisible(NULL))
  kr <- if (kind == "governor") .load_json("governor_ratings")$state_names_kr else NULL
  nm <- vapply(ab, function(a) if (!is.null(kr) && !is.null(kr[[a]])) paste0(kr[[a]], " (", a, ")") else a,
               character(1))
  d <- vapply(ab, function(a) m[[a]]$dem %||% NA_real_, numeric(1))
  r <- vapply(ab, function(a) m[[a]]$rep %||% NA_real_, numeric(1))
  lab <- vapply(ab, function(a) {
    dl <- m[[a]]$dem_label; rl <- m[[a]]$rep_label
    if (is.null(dl) || is.null(rl) || is.na(dl) || is.na(rl) ||
        grepl("party", dl, ignore.case = TRUE)) "—" else paste0(dl, " vs ", rl)
  }, character(1))
  vol <- vapply(ab, function(a) as.numeric(m[[a]]$volume %||% 0), numeric(1))
  tibble(주 = nm, 대진 = lab,
         `민주 가격` = .fmt_price(d), `공화 가격` = .fmt_price(r),
         `누적 거래액` = paste0("$", format(round(vol), big.mark = ","))) |>
    arrange(desc(d)) |>
    gt() |>
    tab_header(title = paste0("예측시장 Kalshi — ", if (kind == "senate") "상원" else "주지사", " 원가격"),
               subtitle = paste0("기준 ", k$fetched_at_utc, " · 가격(센트)은 확률의 근사일 뿐 확률이 아님")) |>
    tab_source_note(paste0(
      "각 칸은 '해당 정당이 이긴다'는 계약의 마지막 체결가입니다. ",
      "민주·공화 값은 서로 다른 계약이라 합이 100¢가 아닐 수 있으며(호가 스프레드), 정규화하지 않고 원값을 싣습니다. ",
      "거래액이 작은 시장의 가격은 소수 거래에 흔들리므로 함께 표시했습니다. ",
      "Cook·Sabato 등급과 같은 잣대로 비교하지 마세요. 취득: scripts/fetch_kalshi_prices.py")) |>
    .tbl_opts()
}

# 상원 감시 8주 — 기관별 등급을 한 표에 (Kalshi 행만 원가격) (270towin 재게시 피드 자동 취득)
gt_senate_rating_sources <- function() {
  d <- .load_json("senate_ratings_feed"); src <- d$sources
  rt <- src$ratings   # data.frame: 행=기관, 열=주 약자
  key <- c("GA", "NC", "NH", "MI", "ME", "AK", "OH", "TX")
  kr <- c(GA = "조지아", NC = "NC", NH = "NH", MI = "미시간", ME = "메인",
          AK = "알래스카", OH = "오하이오", TX = "텍사스")
  is_mkt <- grepl("Kalshi|예측시장", src$label)
  kal <- .kalshi()
  cell <- function(i, ab) {
    # 예측시장 행은 270towin의 '등급 환산값' 대신 Kalshi 원가격을 싣는다 —
    # 환산값(91¢→"Solid D")은 전문가 등급과 구분이 안 돼 오독을 부른다.
    if (is_mkt[i]) {
      p <- .kalshi_dem(kal, "senate", ab)
      return(if (is.na(p)) "—" else paste0("민주 ", round(p), "¢"))
    }
    if (!(ab %in% names(rt))) return("—")
    v <- rt[i, ab]
    if (is.null(v) || length(v) == 0 || is.na(v)) return("—")
    as.character(v)
  }
  cols <- lapply(key, function(ab) vapply(seq_len(nrow(src)), cell, character(1), ab = ab))
  names(cols) <- kr[key]
  lbl <- ifelse(is_mkt, paste0(src$label, " ※"), src$label)
  as_of <- ifelse(is_mkt & !is.null(kal), substr(kal$fetched_at_utc %||% "", 1, 10), src$as_of)
  bind_cols(tibble(예측기관 = lbl, 기준일 = as_of), as_tibble(cols)) |>
    gt() |>
    tab_header(title = "상원 감시 8주 — 기관별 등급",
               subtitle = "270towin 재게시 피드 자동 취득 · 등급은 확률이 아님") |>
    tab_source_note(paste0(
      "같은 주를 기관마다 어떻게 보는지 비교합니다. ",
      "※ Kalshi 행만 성격이 다릅니다 — 전문가 등급이 아니라 **예측시장 가격**(민주 승리 계약의 마지막 체결가)이며, ",
      "Kalshi 공개 API에서 원가격을 직접 받아 싣습니다. 가격은 확률의 근사일 뿐이고(유동성·편향 혼입), ",
      "Cook·Sabato의 서수적 등급과 같은 잣대로 비교하지 마세요. ",
      "'Tilt'는 Lean보다 좁은 등급으로 Inside Elections·RaceToTheWH가 씁니다. ",
      "'—'는 해당 기관이 경합으로 분류하지 않았거나 시장이 없는 칸(추정으로 채우지 않음). ",
      "취득: scripts/fetch_senate_ratings.py · scripts/fetch_kalshi_prices.py")) |>
    .tbl_opts()
}

# 1.7 주지사·주의회 -----------------------------------------------------------
# 주지사 경합주 — Cook·Sabato 등급을 나란히, 기관이 갈리는 곳을 드러낸다.
gt_governor_races <- function() {
  d <- .load_json("governor_ratings")
  src <- d$sources
  # ratings는 data.frame(행=기관, 열=주 약자)으로 역직렬화된다
  rt <- src$ratings
  row_of <- function(name) { i <- which(src$label == name); if (length(i)) i[1] else NA_integer_ }
  ic <- row_of("Cook Political Report"); is_ <- row_of("Sabato's Crystal Ball")
  if (is.na(ic) || is.na(is_)) return(invisible(NULL))
  kr <- d$state_names_kr
  g <- function(i, ab) {
    if (!(ab %in% names(rt))) return("—")
    v <- rt[i, ab]; if (is.null(v) || length(v) == 0 || is.na(v)) "—" else as.character(v)
  }
  abbrs <- names(rt)
  is_comp <- function(i) abbrs[vapply(abbrs, function(a) grepl("Toss|Lean|Tilt", g(i, a)), logical(1))]
  states <- sort(union(is_comp(ic), is_comp(is_)))
  ck_v <- vapply(states, function(a) g(ic, a), character(1))
  sb_v <- vapply(states, function(a) g(is_, a), character(1))
  ck <- list(as_of = src$as_of[ic]); sb <- list(as_of = src$as_of[is_])
  tibble(
    주 = vapply(states, function(a) paste0(kr[[a]], " (", a, ")"), character(1)),
    Cook = ck_v,
    Sabato = sb_v,
    `기관 분기` = ifelse(ck_v == sb_v, "", "◆ 갈림")
  ) |>
    gt() |>
    tab_header(title = "2026 주지사 경합주 — Cook · Sabato",
               subtitle = paste0("Cook 기준 ", ck$as_of, " · Sabato 기준 ", sb$as_of,
                                 " · 등급은 확률이 아님")) |>
    tab_source_note(paste0("총 ", d$n_races, "개 주지사 선거 중 두 기관 어느 한 쪽이라도 Toss-up/Lean으로 본 주만 표시. ",
                           "'◆ 갈림'은 두 기관 평가가 다른 곳 — 판세 해석이 갈리는 지점입니다. ",
                           "출처: 270towin 재게시분 자동 취득(scripts/fetch_governor_ratings.py).")) |>
    .tbl_opts()
}

# 주지사 — 8개 기관 등급 비교(경합주 한정)
gt_governor_sources <- function() {
  d <- .load_json("governor_ratings"); src <- d$sources; kr <- d$state_names_kr
  key <- c("AZ", "GA", "IA", "KS", "MI", "NV", "OH", "WI")
  rt <- src$ratings   # data.frame: 행=기관, 열=주 약자
  is_mkt <- grepl("Kalshi|예측시장", src$label)
  kal <- .kalshi()
  cell <- function(i, ab) {
    if (is_mkt[i]) {   # 등급 환산값 대신 Kalshi 원가격 (상원 표와 같은 규칙)
      p <- .kalshi_dem(kal, "governor", ab)
      return(if (is.na(p)) "—" else paste0("민주 ", round(p), "¢"))
    }
    if (!(ab %in% names(rt))) return("—")
    v <- rt[i, ab]; if (is.null(v) || length(v) == 0 || is.na(v)) "—" else as.character(v)
  }
  cols <- lapply(key, function(ab) vapply(seq_len(nrow(src)), cell, character(1), ab = ab))
  names(cols) <- vapply(key, function(a) kr[[a]], character(1))
  lbl <- ifelse(is_mkt, paste0(src$label, " ※"), src$label)
  as_of <- ifelse(is_mkt & !is.null(kal), substr(kal$fetched_at_utc %||% "", 1, 10), src$as_of)
  bind_cols(tibble(예측기관 = lbl, 기준일 = as_of), as_tibble(cols)) |>
    gt() |>
    tab_header(title = "주지사 경합 8주 — 기관별 등급",
               subtitle = "같은 주를 기관마다 어떻게 보는지 (등급은 확률이 아님)") |>
    tab_source_note(paste0(
      "※ Kalshi 행만 성격이 다릅니다 — 등급이 아니라 **예측시장 가격**(민주 승리 계약의 마지막 체결가)이며 ",
      "공개 API에서 원가격을 직접 받아 싣습니다. 등급과 같은 잣대로 비교하지 마세요. ",
      "'Tilt'는 Lean보다 좁은 등급으로 Inside Elections·RaceToTheWH가 씁니다. ",
      "'—'는 경합으로 분류하지 않았거나 해당 시장이 없는 칸(추정으로 채우지 않음).")) |>
    .tbl_opts()
}

# 주지사 등급 변동 이력 — snapshot_ratings.py가 쌓은 스냅샷에서 '바뀐 것만' 표시.
# 축적 초기에는 스냅샷이 1건뿐이라 안내문만 렌더한다(빈 표를 만들지 않음).
governor_history_html <- function() {
  p <- file.path("data", "history", "governor_rating_snapshots.json")
  if (!file.exists(p)) return("")
  h <- jsonlite::read_json(p, simplifyVector = FALSE)
  snaps <- h$snapshots
  n <- length(snaps)
  if (n <= 1) {
    return(paste0(
      '<div class="caveat"><p><b>등급 변동 이력 — 축적 중</b>. 주지사 등급은 ',
      snaps[[1]]$captured,
      ' 첫 스냅샷을 기록했습니다. 이후 <b>등급이 실제로 바뀐 주만</b> 이 자리에 시점과 함께 쌓입니다',
      '(매주 자동 확인, 변동이 없으면 기록하지 않음). 상원과 같은 월별 변동 매트릭스는 ',
      '이력이 몇 주 쌓인 뒤 제공합니다 — 지금 만들면 과거를 추정으로 채워야 하므로 그렇게 하지 않습니다.</p></div>'))
  }
  items <- character(0)
  for (i in seq(n, 2)) {
    ch <- unlist(snaps[[i]]$changes)
    if (!length(ch)) next
    items <- c(items, paste0(
      '<li><b>', snaps[[i]]$captured, '</b> — ',
      paste0(vapply(ch, function(x) paste0("<code>", x, "</code>"), character(1)), collapse = " · "),
      '</li>'))
  }
  if (!length(items)) return("")
  paste0('<div class="gov-hist"><p><b>등급 변동 이력</b> (바뀐 시점만 기록)</p><ul>',
         paste(items, collapse = ""), '</ul></div>')
}

# 주의회 — 경합 의회(수동 큐레이션)
gt_state_legislatures <- function() {
  d <- .load_json("state_legislatures"); c_ <- d$chambers
  tibble(
    주 = c_$state,
    의회 = c_$chamber,
    `현 통제` = c_$control,
    등급 = c_$rating,
    메모 = c_$trifecta_note
  ) |>
    gt() |>
    tab_header(title = "2026 주의회 — 경합 의회",
               subtitle = paste0("Sabato 초기 등급 기준 · 토스업 ", d$competitive_summary$tossup_chambers,
                                 "개 의회(", d$competitive_summary$tossup_states, "개 주) · 기준 ", d$as_of)) |>
    tab_source_note(paste0(d$provenance_note, " 출처: ",
                           paste(d$sources$label, collapse = " · "))) |>
    .tbl_opts()
}

# Cook 현행 토스업 명단(자동 취득) + 사이트 상시 추적구와의 차집합을 함께 표기.
# 두 목록이 다른 이유를 숨기지 않는 것이 목적 — 독자가 트래커를 'Cook 토스업'으로 오해하지 않게.
gt_cook_tossups <- function() {
  d <- .load_json("house_cook_districts")
  ts <- d$districts[d$districts$key == "tossup", ]
  tracked <- .load_json("house_races")$races$district
  norm <- function(x) sub("^([A-Z]{2})-0*(\\d+)$", "\\1-\\2", x)   # PA-07 -> PA-7
  ts$tracked <- ifelse(norm(ts$district) %in% norm(tracked), "○ 추적 중", "— 미추적")
  inc <- if (!is.null(ts$incumbent)) ifelse(is.na(ts$incumbent), "—", ts$incumbent) else rep("—", nrow(ts))
  only_tracked <- setdiff(norm(tracked), norm(ts$district))
  tibble(
    지역구 = ts$district,
    `현역/공석` = inc,
    `사이트 추적` = ts$tracked
  ) |>
    gt() |>
    tab_header(
      title = paste0("Cook 현행 토스업 ", nrow(ts), "개구"),
      subtitle = paste0("자동 취득 · 기준 ", d$as_of, " · 등급은 확률이 아님")
    ) |>
    tab_source_note(paste0(
      "‘사이트 추적’은 아래 트래커(6월 초 토스업 출발선)에 포함돼 있는지 여부입니다. ",
      "반대로 트래커에는 있으나 Cook 현행 토스업이 아닌 곳: ",
      paste(only_tracked, collapse = " · "), " — 이들은 이후 Lean/Likely로 이동했거나 명단에서 빠진 구입니다.")) |>
    .tbl_opts()
}

gt_model_scenarios <- function() {
  d <- .load_json("model_dashboard")
  s <- d$scenarios
  tibble(
    예측기관 = paste0(s$name, " (", s$subname, ")"),
    수치 = ifelse(is.na(s$prob), s$prob_label, paste0(s$prob, "%")),
    `의석 결과` = s$seats,
    다수당 = s$majority,
    설명 = s$desc
  ) |>
    gt() |>
    tab_header(title = "외부 예측기관 비교 — 상원 다수",
               subtitle = paste0("민주 다수 확률 ", d$dem_majority_prob, "% (", d$majority_note, ")")) |>
    .tbl_opts()
}

# 등급 → 버킷 분류 (Solid D / Lean D / Toss-up / Lean R / Solid R)
.rating_bucket <- function(x) {
  # Tilt(Lean보다 좁은 등급)는 5칸 타일 지도에서 Lean과 같은 칸에 넣는다 —
  # 방향은 같고 확신만 더 약하므로 Toss-up으로 밀면 방향 정보가 사라진다.
  if (grepl("Solid D|Safe D|Likely D", x, ignore.case = TRUE)) "Solid D"
  else if (grepl("Lean|Tilt", x, ignore.case = TRUE) && grepl("D", x)) "Lean D"
  else if (grepl("Toss", x, ignore.case = TRUE)) "Toss-up"
  else if (grepl("Lean|Tilt", x, ignore.case = TRUE) && grepl("R", x)) "Lean R"
  else if (grepl("Solid R|Safe R|Likely R", x, ignore.case = TRUE)) "Solid R"
  else "기타"
}

# 분류용 '단일 출처' 등급 벡터. 병기 문자열("Lean D (Cook) / Likely D (Sabato)")을 그대로
# 버킷에 넣으면 오분류되므로(2026-08-03 조지아 사례), 컨센서스 → Cook 순으로 하나만 고른다.
.single_rating <- function(s) {
  cons <- tryCatch({
    f <- .load_json("senate_ratings_feed")
    i <- which(f$sources$label == "270toWin Consensus")
    if (length(i)) list(rt = f$sources$ratings, i = i[1]) else NULL
  }, error = function(e) NULL)
  vapply(seq_len(nrow(s)), function(k) {
    ab <- toupper(s$id[k])
    if (!is.null(cons) && ab %in% names(cons$rt)) {
      v <- cons$rt[cons$i, ab]
      if (!is.null(v) && !is.na(v)) return(as.character(v))
    }
    if (!is.null(s$rating_cook) && !is.na(s$rating_cook[k])) return(sub(" \\(.*", "", s$rating_cook[k]))
    s$rating[k]
  }, character(1))
}

model_rating_counts <- function() {
  d <- .load_json("model_dashboard")
  b <- vapply(.single_rating(d$states), .rating_bucket, character(1))
  cats <- c("Solid D", "Lean D", "Toss-up", "Lean R", "Solid R")
  setNames(vapply(cats, function(k) sum(b == k), integer(1)), cats)
}

# 등급 분포를 5개 타일 HTML로 (각 타일에 해당 주 명칭 + 링크)
rating_tiles_html <- function() {
  d <- .load_json("model_dashboard"); s <- d$states
  # 분류 기준은 **단일 출처**를 쓴다. 과거에 "Lean D (Cook) / Likely D (Sabato)" 같은
  # 병기 문자열을 그대로 버킷에 넣어 조지아가 Solid 그룹으로 잘못 들어간 적이 있다(2026-08-03 수정).
  # 지도(us_tile_map_html)와 같은 270toWin 컨센서스를 1순위로, 없으면 Cook 개별 등급으로 폴백.
  cons <- tryCatch({
    f <- .load_json("senate_ratings_feed")
    i <- which(f$sources$label == "270toWin Consensus")
    if (length(i)) list(rt = f$sources$ratings, i = i[1], as_of = f$sources$as_of[i[1]]) else NULL
  }, error = function(e) NULL)
  b <- vapply(.single_rating(s), .rating_bucket, character(1))
  # Cook과 Sabato가 갈리는 주는 타일에 표시해, 단일 등급으로 보이지 않게 한다.
  diverge <- rep(FALSE, nrow(s))
  if (!is.null(s$rating_cook) && !is.null(s$rating_sabato)) {
    ck <- sub(" \\(.*", "", s$rating_cook); sb <- s$rating_sabato
    diverge <- !is.na(ck) & !is.na(sb) & sb != "—" & ck != sb
  }
  defs <- list(c("Solid D", "rt-sd", "Solid·Likely D"), c("Lean D", "rt-ld", "Lean D"),
               c("Toss-up", "rt-tu", "Toss-up"), c("Lean R", "rt-lr", "Lean R"),
               c("Solid R", "rt-sr", "Solid·Likely R"))
  tiles <- vapply(defs, function(x) {
    idx <- which(b == x[1])
    states <- if (length(idx) == 0) '<span class="rt-empty">—</span>' else
      paste0(vapply(idx, function(i) sprintf(
        '<div class="rt-st"><a href="/states/%s.html">%s%s</a><span class="rt-hold rt-hold-%s">%s</span></div>',
        s$id[i], s$name[i], if (diverge[i]) '<span class="rt-div" title="Cook과 Sabato 평가가 갈림">◆</span>' else "",
        tolower(s$defense[i]), s$defense[i]), character(1)),
        collapse = "")
    sprintf('<div class="rtile %s"><div class="rt-num">%d</div><div class="rt-lab">%s</div><div class="rt-states">%s</div></div>',
            x[2], length(idx), x[3], states)
  }, character(1))
  src <- if (!is.null(cons))
    sprintf('<p class="rt-src">분류 기준: <b>270toWin 컨센서스</b>(기준 %s) — 상원 지도와 같은 출처. ◆는 Cook과 Sabato 평가가 갈리는 주로, 개별 등급은 <a href="/senate.html#races">경합주 표</a>와 <a href="/dashboard.html">대시보드</a>에서 확인하세요.</p>', cons$as_of)
  else ""
  paste0('<div class="rating-tiles">', paste(tiles, collapse = ""), "</div>", src)
}

# 현 보유 정당 요약 (defense 기준) + 탈환 표적
holder_note_html <- function() {
  d <- .load_json("model_dashboard"); s <- d$states
  dh <- s$name[s$defense == "D"]; rh <- s$name[s$defense == "R"]
  b <- vapply(.single_rating(s), .rating_bucket, character(1))
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
    net_display = if (!is.null(d$net_display)) d$net_display else paste0("+", d$net_expected_seats),
    majority_note = if (!is.null(d$majority_note)) d$majority_note else "",
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

# 2.0 Cook 하원 등급 토플라인 — 가로 누적 막대 (수동 갱신, 하원 페이지 맨 위) ---
# data/house_cook_ratings.json — 270towin Cook 페이지 수치를 사람이 주기적으로 옮김.
# 색은 270towin 원본 팔레트(styles-responsive.css의 fill-d1/d2/d3/t/r1/r2/r3)에 맞춤.
house_cook_bar_html <- function() {
  d <- .load_json("house_cook_ratings")
  cg <- d$categories
  # 270towin 원본 팔레트(map.class.js: D4/D3/D2/T/R2/R3/R4). 종전 solid 자리에
  # Tilt 색(D1 #949BB3 · R1 #CF8980)이 들어가 양 끝이 가장 흐리게 칠해졌다 — 2026-08-06 정정.
  pal <- c(solid_d = "#244999", likely_d = "#577CCC", lean_d = "#8AAFFF",
           tossup = "#C9C09B", lean_r = "#FF8B98", likely_r = "#FF5865", solid_r = "#D22532")
  seats <- cg$seats; keys <- cg$key; labs <- cg$label
  total <- sum(seats); maj <- d$majority
  dfav <- sum(seats[cg$party == "D"]); rfav <- sum(seats[cg$party == "R"])
  W <- 720; padx <- 10; barW <- W - 2 * padx; barY <- 34L; barH <- 34L
  sc <- barW / total
  x <- padx; rects <- character(0); inlab <- character(0)
  for (i in seq_along(seats)) {
    w <- seats[i] * sc; col <- pal[[keys[i]]]
    rects <- c(rects, sprintf('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"/>',
                              x, barY, w, barH, col))
    if (w >= 26) inlab <- c(inlab, sprintf(
      '<text x="%.1f" y="%d" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">%d</text>',
      x + w / 2, barY + barH / 2 + 5L, seats[i]))
    x <- x + w
  }
  majx <- padx + maj * sc
  marker <- sprintf(paste0(
    '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#212529" stroke-width="1.5" stroke-dasharray="3,2"/>',
    '<text x="%.1f" y="%d" text-anchor="middle" font-size="11" fill="#212529">과반 %d</text>'),
    majx, barY - 6L, majx, barY + barH + 6L, majx, barY - 11L, maj)
  ends <- sprintf(paste0(
    '<text x="%d" y="%d" text-anchor="start" font-size="12" font-weight="700" fill="#1971c2">민주 우세 %d</text>',
    '<text x="%d" y="%d" text-anchor="end" font-size="12" font-weight="700" fill="#c92a2a">공화 우세 %d</text>'),
    padx, barY - 11L, dfav, W - padx, barY - 11L, rfav)
  svg <- sprintf(paste0(
    '<svg viewBox="0 0 %d 84" width="100%%" style="height:auto;display:block;margin:6px 0;',
    'font-family:\'IBM Plex Sans KR\',sans-serif;" role="img" ',
    'aria-label="Cook 하원 등급 가로 막대 — 민주 우세 %d, Toss-up %d, 공화 우세 %d">%s%s%s%s</svg>'),
    W, dfav, total - dfav - rfav, rfav, paste(rects, collapse = ""),
    paste(inlab, collapse = ""), ends, marker)
  legitems <- sprintf('<span class="cook-leg"><i style="background:%s"></i>%s <b>%d</b></span>',
                      vapply(keys, function(k) pal[[k]], ""), labs, seats)
  legend <- paste0('<div class="cook-legend">', paste(legitems, collapse = ""), '</div>')
  src <- sprintf(paste0('<p class="cook-src">출처: <a href="%s">%s</a> · 기준일 %s · ',
                        '등급은 확률이 아닙니다. 435개 지역구 등급을 <code>scripts/fetch_cook_house.py</code>가 주 1회 자동 취득해 집계합니다.</p>'),
                 d$source_url, d$source_label, d$as_of)
  paste0('<figure class="cook-bar-wrap">', svg, legend, src, '</figure>')
}

# 2.1 하원 경합구 트래커 ------------------------------------------------------
# data/house_races.json — Cook 토스업 명단 중심. 빈 값은 — / 【수집】 렌더.
gt_house_races <- function() {
  d <- .load_json("house_races")
  r <- d$races
  # Cook 등급 정규화 → 스펙트럼 순서·색(270towin 팔레트와 동일)
  norm_rating <- function(x) {
    x <- gsub("Leans", "Lean", x)
    x <- gsub("Toss[ -]?Up", "Toss-up", x, ignore.case = TRUE)
    trimws(x)
  }
  spec <- c("Solid D" = 1, "Likely D" = 2, "Lean D" = 3, "Toss-up" = 4,
            "Lean R" = 5, "Likely R" = 6, "Solid R" = 7)
  # 270towin 원본 팔레트(map.class.js). 종전 Solid D/R 자리에 Tilt 색(#949BB3·#CF8980)이
  # 들어가 있어 가장 안전한 구가 가장 흐리게 칠해졌다 — 2026-08-06 원본 대조로 정정.
  rcol <- c("Solid D" = "#244999", "Likely D" = "#577CCC", "Lean D" = "#8AAFFF",
            "Toss-up" = "#C9C09B", "Lean R" = "#FF8B98", "Likely R" = "#FF5865",
            "Solid R" = "#D22532")
  ck  <- norm_rating(r$rating_cook)
  ord <- ifelse(ck %in% names(spec), spec[ck], 99L)
  tib <- tibble(
    .ck = ck, .ord = as.integer(ord),
    지역구 = r$district,
    `현역` = r$incumbent,
    보유 = ifelse(r$party == "D", "민주", "공화"),
    `등급(Cook)` = r$rating_cook,
    `등급(Sabato)` = ifelse(is.na(r$rating_sabato), "【수집】", r$rating_sabato),
    `전주 대비` = ifelse(is.na(r$rating_delta), "—", r$rating_delta),
    `2024 마진` = ifelse(is.na(r$margin_2024), "【수집】", .fmt_margin(r$margin_2024)),
    비고 = ifelse(is.na(r$note), "—", r$note)
  ) |>
    arrange(.ord, 지역구)
  g <- tib |>
    gt() |>
    cols_hide(c(".ck", ".ord")) |>
    tab_header(
      title = "하원 경합구 트래커 — Lean D → Toss-up → Lean R 순",
      subtitle = paste0("기준 ", d$as_of, " · ", d$cook_outlook, " · ", d$source_label)
    ) |>
    .tbl_opts()
  # 등급(Cook) 셀을 등급 색으로 채움 (Lean·Likely 등 밝은 색이라 본문 텍스트 유지)
  for (rt in names(rcol)) {
    rows <- which(tib$.ck == rt)
    if (length(rows))
      g <- g |> tab_style(style = cell_fill(color = rcol[[rt]]),
                          locations = cells_body(columns = "등급(Cook)", rows = rows))
  }
  g
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
           paste0("외부 모델 RaceToTheWH · ", k$as_of),
           sprintf("다수까지 순 +%d석 필요 — DDHQ는 50–50 이견", k$needed)),
      card("kpi-d", k$net_display, "순증 컨센서스 (민주)",
           "Inside Elections",
           "공화 표적 5곳 · 민주 수성 3곳의 순증 — 문턱 +4 미달"),
      card("kpi-r", ifelse(is.na(tn), "—", sprintf("%+.1f", tn)), "트럼프 순지지도",
           paste0("Silver Bulletin · ~", td$as_of),
           "낮을수록 민주 우호 — 2기 최저권"),
      card("kpi-d", .fmt_margin(gb), "일반투표 마진",
           paste0("보고 주 기준 · ~", td$as_of),
           "양수=민주 우위 — 중간선거 역풍 환경"),
    '</div>')
  }, error = function(e) "")
}
