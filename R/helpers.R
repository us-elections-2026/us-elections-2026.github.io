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

# 1.5 신규 여론조사 로그 ----------------------------------------------------
gt_polls_log <- function() {
  readr::read_csv(file.path("data", "polls_log.csv"), show_col_types = FALSE) |>
    arrange(desc(date)) |>
    gt() |>
    tab_header(title = "이번 주 신규 여론조사 로그",
               subtitle = "모집단(A/RV/LV)·방식·스폰서를 항상 병기") |>
    .tbl_opts()
}
