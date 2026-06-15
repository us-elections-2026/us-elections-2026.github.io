#!/usr/bin/env Rscript
# data/ 스키마·파싱 경량 검증 — Quarto render 전(로컬·CI)에서 실행.
#
# 목적: 깨진 JSON/CSV, 필수 필드 누락, 명백한 규약 위반(부호·열·범위)을
#       공개 페이지로 렌더되기 전에 잡는다. 데이터 값은 바꾸지 않는다.
# 의존성: jsonlite + base R (빌드 스택과 동일, 추가 설치 불필요).
# 종료코드: 위반 1건 이상이면 1(=CI 실패), 없으면 0.
#
# 스키마 상세는 data/README.md 참조.

suppressPackageStartupMessages(library(jsonlite))

errors <- character(0)
err  <- function(file, msg) errors[[length(errors) + 1L]] <<- sprintf("[%s] %s", file, msg)

data_dir <- "data"
jpath <- function(f) file.path(data_dir, f)

# ---- 로더 --------------------------------------------------------------------
load_json <- function(f, optional = FALSE) {
  p <- jpath(f)
  if (!file.exists(p)) {
    if (!optional) err(f, "파일 없음 (필수)")
    else cat(sprintf("  · %s 없음 — 선택 파일이라 건너뜀\n", f))
    return(NULL)
  }
  tryCatch(jsonlite::fromJSON(p),
           error = function(e) { err(f, paste("JSON 파싱 실패:", conditionMessage(e))); NULL })
}

load_csv <- function(f) {
  p <- jpath(f)
  if (!file.exists(p)) { err(f, "파일 없음 (필수)"); return(NULL) }
  tryCatch(utils::read.csv(p, stringsAsFactors = FALSE, check.names = FALSE),
           error = function(e) { err(f, paste("CSV 파싱 실패:", conditionMessage(e))); NULL })
}

# ---- 공통 체커 ---------------------------------------------------------------
require_keys <- function(f, obj, keys) {
  if (is.null(obj)) return(invisible())
  miss <- setdiff(keys, names(obj))
  if (length(miss)) err(f, paste("최상위 키 누락:", paste(miss, collapse = ", ")))
}

require_cols <- function(f, df, cols, what = "records") {
  if (is.null(df)) return(invisible())
  if (!is.data.frame(df)) { err(f, sprintf("%s가 객체 배열이 아님", what)); return(invisible()) }
  if (nrow(df) == 0)      { err(f, sprintf("%s가 비어 있음", what));       return(invisible()) }
  miss <- setdiff(cols, names(df))
  if (length(miss)) err(f, sprintf("%s 필수 컬럼 누락: %s", what, paste(miss, collapse = ", ")))
}

enum_ok <- function(f, df, col, allowed) {
  if (is.null(df) || !is.data.frame(df) || !(col %in% names(df))) return(invisible())
  bad <- setdiff(unique(stats::na.omit(df[[col]])), allowed)
  if (length(bad)) err(f, sprintf("%s는 {%s}만 허용 — 위반: %s",
                                   col, paste(allowed, collapse = "/"), paste(bad, collapse = ", ")))
}

cat("데이터 검증 시작 (", data_dir, "/) …\n", sep = "")

# ---- 전국 환경 ---------------------------------------------------------------
d <- load_json("forecast.json")
require_keys("forecast.json", d, c("as_of", "rows"))
require_cols("forecast.json", d$rows, c("source", "type"))

d <- load_json("generic_ballot.json")
require_keys("generic_ballot.json", d, c("as_of", "aggregators"))
require_cols("generic_ballot.json", d$aggregators, c("source", "dem", "rep", "margin"))

d <- load_json("approval.json")
require_keys("approval.json", d, c("as_of", "rows"))
require_cols("approval.json", d$rows, c("source", "approve", "disapprove", "net"))

d <- load_json("trends.json")
require_keys("trends.json", d, c("as_of", "weeks"))
require_cols("trends.json", d$weeks, c("date"))

d <- load_json("national_econ.json", optional = TRUE)  # fetch 실패 시 부재 가능(빌드 안전)
if (!is.null(d)) {
  require_keys("national_econ.json", d, c("as_of", "rows", "series"))
  require_cols("national_econ.json", d$rows, c("indicator", "key", "unit"))
}

# ---- 상원 --------------------------------------------------------------------
d <- load_json("senate_races.json")
require_keys("senate_races.json", d, c("as_of", "races"))
require_cols("senate_races.json", d$races, c("state", "defense", "rating"))
enum_ok("senate_races.json", d$races, "defense", c("D", "R"))

d <- load_json("senate_primaries.json")
require_keys("senate_primaries.json", d, c("as_of", "rows"))
require_cols("senate_primaries.json", d$rows, c("state", "event"))

d <- load_json("candidates.json")
require_keys("candidates.json", d, c("as_of", "candidates"))
require_cols("candidates.json", d$candidates, c("state", "party", "name"))

# ---- 자체 모델 대시보드 ------------------------------------------------------
d <- load_json("model_dashboard.json")
require_keys("model_dashboard.json", d, c("as_of", "states", "scenarios", "timeline"))
require_cols("model_dashboard.json", d$states, c("id", "name", "defense"))
if (!is.null(d$states) && is.data.frame(d$states) && "prob" %in% names(d$states)) {
  p <- suppressWarnings(as.numeric(d$states$prob))  # null → NA(=산정 전), 허용
  if (any(!is.na(p) & (p < 0 | p > 100)))
    err("model_dashboard.json", "states.prob는 0–100(%) 범위여야 함")
}

# ---- 하원 --------------------------------------------------------------------
d <- load_json("house_races.json")
require_keys("house_races.json", d, c("as_of", "races"))
require_cols("house_races.json", d$races, c("district", "party", "rating_cook"))
enum_ok("house_races.json", d$races, "party", c("D", "R"))
if (!is.null(d$races) && is.data.frame(d$races) && "margin_2024" %in% names(d$races)) {
  m <- d$races$margin_2024
  # 규약: 양수=민주 우위. 숫자 또는 null(=【수집】)만 허용. 문자열이면 파싱/타입 오류.
  if (!is.numeric(m) && !all(is.na(m)))
    err("house_races.json", sprintf("margin_2024는 숫자 또는 null이어야 함 (현재 타입: %s)", class(m)[1]))
}

# ---- 재획정 (redistricting 설명 페이지 데이터) -------------------------------
d <- load_json("redistricting_states.json")
require_keys("redistricting_states.json", d, c("as_of", "states"))
require_cols("redistricting_states.json", d$states, c("state", "category", "net_d"))
if (!is.null(d$states) && is.data.frame(d$states) && "net_d" %in% names(d$states)) {
  if (!is.numeric(d$states$net_d) && !all(is.na(d$states$net_d)))
    err("redistricting_states.json", "net_d는 숫자(양수=민주 순증) 또는 null이어야 함")
}

d <- load_json("redistricting_pres.json")
require_keys("redistricting_pres.json", d, c("as_of", "districts"))
require_cols("redistricting_pres.json", d$districts, c("district", "new_margin"))
if (!is.null(d$districts) && is.data.frame(d$districts)) {
  for (col in c("old_margin", "new_margin")) {
    if (col %in% names(d$districts)) {
      v <- d$districts[[col]]
      if (!is.numeric(v) && !all(is.na(v)))
        err("redistricting_pres.json", sprintf("%s는 숫자(양수=민주 우위) 또는 null이어야 함", col))
    }
  }
}

# ---- Korea Watch CSV (스키마 고정) -------------------------------------------
kw_cols <- c("date", "type", "actor", "affiliation", "state_or_district",
             "event", "detail", "race_link", "significance", "source_url")
kw <- load_csv("korea_watch.csv")
if (!is.null(kw)) {
  miss  <- setdiff(kw_cols, names(kw))
  extra <- setdiff(names(kw), kw_cols)
  if (length(miss))  err("korea_watch.csv", paste("필수 컬럼 누락:", paste(miss, collapse = ", ")))
  if (length(extra)) err("korea_watch.csv", paste("예상치 못한 컬럼:", paste(extra, collapse = ", ")))
  if ("significance" %in% names(kw) && nrow(kw) > 0) {
    s <- suppressWarnings(as.integer(kw$significance))
    if (any(is.na(s)))                 err("korea_watch.csv", "significance에 비정수/결측 값 존재")
    else if (any(s < 1 | s > 3))       err("korea_watch.csv", "significance는 1–3만 허용")
  }
}

# ---- polls_log CSV -----------------------------------------------------------
pl_cols <- c("date", "pollster", "sponsor", "race", "population", "n", "result", "rating")
pl <- load_csv("polls_log.csv")
if (!is.null(pl)) {
  miss <- setdiff(pl_cols, names(pl))
  if (length(miss)) err("polls_log.csv", paste("필수 컬럼 누락:", paste(miss, collapse = ", ")))
}

# ---- 결과 --------------------------------------------------------------------
if (length(errors) > 0) {
  cat(sprintf("\n✗ 데이터 검증 실패 (%d건):\n", length(errors)))
  for (e in errors) cat("  -", e, "\n")
  quit(status = 1)
} else {
  cat("\n✓ 데이터 검증 통과 — 모든 파일 파싱·필수 필드·규약 정상\n")
}
