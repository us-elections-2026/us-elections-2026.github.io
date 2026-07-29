# 자체 모델 v0 — 등급·예측시장·여론조사 블렌드 + 상관 몬테카를로
#
# 방법 (methodology.qmd §2에 공개):
#   1) 주별 민주 승리확률 p_i = 가중평균( 등급 사전확률, 시장 가격, 조사 함의확률 )
#      - 등급 사전: Solid=.97/.03, Likely=.90/.10, Lean=.75/.25, Toss-up=.50 (Cook/Sabato 종합)
#      - 시장 가격: data/model_dashboard.json 의 states.prob (확인된 주만 — 현재 GA·OH)
#      - 조사 함의: 시간감쇠(반감기 21일)·당파보정(x0.5) 가중 마진 평균 m → Φ(m/σ), σ=6pt
#        (σ=6: 선거 ~100일 전 주별 상원 조사 오차의 역사적 수준 — 가정, 캘리브레이션 대상)
#      - 가중치: 등급 1.0 / 시장 1.2 / 조사 min(유효조사수,2)/2 x 1.5 (조사 많을수록 신뢰)
#   2) 상관 몬테카를로 (가우시안 코퓰러): x_i = sqrt(ρ)·δ + sqrt(1-ρ)·ε_i,  win_i = x_i < Φ⁻¹(p_i)
#      - δ = 전국 공통 충격(모든 주 공유) → "전국 파도" 시나리오가 자동 계산됨. ρ=0.5 (가정)
#      - 주변확률은 p_i 그대로 보존, 주간 상관만 주입
#   3) 민주 의석 = 47 − (민주방어 패배) + (공화방어 승리) → P(≥51) = 다수 확률
#
# 원칙: 추정으로 빈 칸을 채우지 않음 — 조사·시장이 없는 주는 등급 사전만 사용(가중 명시).
#       사퇴 후보 조사는 제외(ME: Platner 행 필터). 고정 시드 = 재현 가능.
# 실행: Rscript scripts/model/run_model.R   → data/model_v0.json
suppressPackageStartupMessages({ library(dplyr); library(readr); library(jsonlite) })

set.seed(20261103)
RUN_DATE   <- Sys.Date()
SIGMA_POLL <- 6      # 주별 조사 오차 SD (pt)
HALF_LIFE  <- 21     # 시간감쇠 반감기 (일)
RHO        <- 0.5    # 주간 상관 (전국 공통 충격 비중)
NSIM       <- 10000
W_RATING <- 1.0; W_MARKET <- 1.2; W_POLL_MAX <- 1.5

root <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])), "..", ".."))
if (!length(root) || is.na(root)) root <- getwd()
setwd(root)

races  <- fromJSON(file.path("data", "senate_races.json"))$races          # state·defense·rating
market <- fromJSON(file.path("data", "model_dashboard.json"))$states      # prob = 시장가(확인 주만)
polls  <- read_csv(file.path("data", "senate_polls.csv"), show_col_types = FALSE)

rating_prior <- function(x) {
  if (grepl("Solid D|Safe D", x)) 0.97
  else if (grepl("Likely D", x)) 0.90
  else if (grepl("Lean", x) && grepl("D", x)) 0.75
  else if (grepl("Toss", x, ignore.case = TRUE)) 0.50
  else if (grepl("Lean", x) && grepl("R", x)) 0.25
  else if (grepl("Likely R", x)) 0.10
  else if (grepl("Solid R|Safe R", x)) 0.03
  else 0.50
}

# 사퇴 후보 조사 제외 (현 후보 명단)
CURRENT_DEM <- c(ME = "Jackson")
polls <- polls |>
  filter(!is.na(end_date)) |>
  rowwise() |>
  filter(!(state %in% names(CURRENT_DEM) && dem_candidate != CURRENT_DEM[[state]])) |>
  ungroup()

per_state <- lapply(seq_len(nrow(races)), function(i) {
  st <- races$state[i]
  pr <- rating_prior(races$rating[i])
  mk <- market$prob[match(tolower(st), market$id)] / 100      # NA면 시장가 없음
  pp <- polls |> filter(state == st)
  if (nrow(pp) > 0) {
    age <- as.numeric(RUN_DATE - as.Date(pp$end_date))
    w   <- 0.5^(age / HALF_LIFE) * ifelse(is.na(pp$partisan) | pp$partisan == "none", 1, 0.5)
    m   <- sum(w * pp$margin) / sum(w)
    k   <- sum(w > 0.05)                                     # 유효 조사 수(너무 오래된 건 제외)
    p_poll <- pnorm(m / SIGMA_POLL)
    w_poll <- min(k, 2) / 2 * W_POLL_MAX
  } else { m <- NA; k <- 0; p_poll <- NA; w_poll <- 0 }
  sig <- c(pr, mk, p_poll); wgt <- c(W_RATING, ifelse(is.na(mk), 0, W_MARKET), w_poll)
  ok  <- !is.na(sig)
  p   <- sum(sig[ok] * wgt[ok]) / sum(wgt[ok])
  tibble(state = st, defense = races$defense[i], rating = races$rating[i],
         p_rating = pr, p_market = mk, poll_margin = round(m, 1), n_polls = k,
         p_poll = round(p_poll, 3), p_blend = round(p, 3))
}) |> bind_rows()

# 상관 몬테카를로 (가우시안 코퓰러)
ns <- nrow(per_state); thr <- qnorm(per_state$p_blend)
delta <- rnorm(NSIM); eps <- matrix(rnorm(NSIM * ns), NSIM, ns)
x <- sqrt(RHO) * delta + sqrt(1 - RHO) * eps
win <- sweep(x, 2, thr, "<")
dem_seats <- 47 - rowSums(win[, per_state$defense == "D", drop = FALSE] == FALSE) +
                  rowSums(win[, per_state$defense == "R", drop = FALSE])
p_majority <- mean(dem_seats >= 51)

out <- list(
  version = "v0.1", run_date = as.character(RUN_DATE), seed = 20261103, n_sims = NSIM,
  assumptions = list(sigma_poll = SIGMA_POLL, half_life_days = HALF_LIFE, rho = RHO,
                     weights = list(rating = W_RATING, market = W_MARKET, poll_max = W_POLL_MAX)),
  method_note = paste("등급(사전)+시장가+조사(시간감쇠·당파보정) 블렌드 → 가우시안 코퓰러(ρ=0.5) 1만회.",
                      "조사·시장 없는 주는 등급만 사용(MI 등). 사퇴 후보 조사 제외(ME=Jackson만).",
                      "σ·ρ·가중치는 문서화된 가정 — 11월 실측으로 캘리브레이션 예정."),
  states = per_state,
  dem_majority_prob = round(p_majority * 100, 1),
  seats = list(mean = round(mean(dem_seats), 2),
               p05 = unname(quantile(dem_seats, .05)), p25 = unname(quantile(dem_seats, .25)),
               median = unname(median(dem_seats)),
               p75 = unname(quantile(dem_seats, .75)), p95 = unname(quantile(dem_seats, .95))),
  seat_pmf = as.list(table(dem_seats) / NSIM)
)
write_json(out, file.path("data", "model_v0.json"), auto_unbox = TRUE, pretty = TRUE, digits = 4)
cat(sprintf("[model v0] 민주 다수 확률 %.1f%% · 의석 중앙값 %d (90%% 구간 %d–%d)\n",
            p_majority * 100, median(dem_seats), quantile(dem_seats, .05), quantile(dem_seats, .95)))
cat(sprintf("[model v0] wrote data/model_v0.json (states: %d, polls used: %d)\n", ns, sum(per_state$n_polls)))
