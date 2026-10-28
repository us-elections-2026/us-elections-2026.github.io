# 집계 목록 조사 (2026-10-26)

검색 도구가 집계형 공장 목록·지도를 거의 내놓지 않았고, 핵심 후보(KEI 지도, Atlas EV Hub)는 열 수 없었다. 아래는 직접 연 것만 `opened=Y`.

## 목록 (제목 / 발행처 / 날짜 / URL / 범위 / 열었는지)
| # | 제목 | 발행처 | 날짜 | URL | 범위 | opened |
|---|---|---|---|---|---|---|
| 1 | Korea IRA Investments (데이터 페이지) + "Announcing KEI's New Korean IRA Investment Map" + Korean IRA Investments 지도 페이지 | KEI | 2024-10-23(지도 공지); 데이터 페이지 날짜 없음(2026 푸터) | https://keia.org/data/ira-investments/ , https://keia.org/analysis/announcing-keis-new-korean-ira-investment-map/ , https://keia.org/korean-ira-investments/ | IRA 유발 한국 투자 500억 달러 이상·7만 개 일자리 합계(지도 제목 "Major Clean Economy Korean Investment Project Announcements Spurred by the IRA") | Y — 그러나 세 페이지 모두 사업장 단위 목록이 본문에 없음(지도는 동적 임베드, 원본 데이터 접근 못함: curl은 차단/빈 응답). 대조 불가 |
| 2 | Q1 2026 U.S.-Korea Trade, Investment, and Diplomacy Ledger | KEI | 2026-04-27 | https://keia.org/analysis/q1-2026-u-s-korea-trade-investment-and-diplomacy-ledger/ | 분기 투자 발표 표(LS일렉트릭 유타 1.68억 달러, LGES 스프링힐 ESS 7천만 달러, SK하이닉스·삼성 연구소 등) | Y |
| 3 | Q2 2026 U.S.-South Korea Trade and Investment Ledger | KEI | 2026-07-30 | https://keia.org/analysis/q2-2026-u-s-south-korea-trade-and-investment-ledger/ | 삼성중공업 루이지애나 FLNG 29억 달러 등(공장 아님) | Y |
| 4 | Q3 2026 U.S.-South Korea Trade and Investment Ledger | KEI | 2026-10-01 | https://keia.org/analysis/q3-2026-u-s-south-korea-trade-and-investment-ledger/ | 한화에어로스페이스 아칸소 군수시설 22억 달러(2026-09-21) 외 비한국기업 프로젝트 | Y |
| 5 | Seoul Searching: Korean Manufacturers Find a Home in Tennessee | Site Selection | 2026-08-05 | https://siteselection.com/foreign-direct-investment-seoul-searching-korean-manufacturers-find-a-home-in-tennessee/ | 테네시 한국 제조업체: 한국타이어(클락스빌), ALUKO, 고려아연(클락스빌·고든스빌), LG화학·LG전자·SK온·LGES·효성HICO(이름만) | Y |
| 6 | KITA, Tennessee seek to deepen ties in EV supply chains | Korea Herald | 2025-10-23 | https://www.koreaherald.com/article/10599897 | 테네시 한국 24개사 약 60억 달러·4,500명, 6개사 이름만 | Y |
| 7 | Korean Companies Speed Up U.S. Investment Plans as Semiconductor and Auto Production Accelerates | Financial News (fnnews) | 2026-08-27 | https://en.fnnews.com/news/202608271421538801 | SK하이닉스 인디애나, 삼성 테일러, 현대차그룹 260억 달러(조지아 HMGMA 증설 검토, RMAC, 로봇 공장 부지 미정) | Y |
| 8 | Battery industry of South Korea | Wikipedia | 2026-09-21 최종 편집 | https://en.wikipedia.org/wiki/Battery_industry_of_South_Korea | 한국 배터리 3사 미국 공장 표(홀랜드·커머스·워런·스프링힐·코코모·킹스턴 GA·랜싱) | Y |
| 9 | Top 10 EV Battery Plants in 2026: Investment, Capacity and Jobs | GreenTechLead | 2026-09-13 | https://greentechlead.com/?p=55356 | LGES 랜싱·애리조나, BlueOval SK 켄터키 | Y |
| 10 | Georgia Korea Connection 2024 (팩트시트) | Georgia Dept. of Economic Development | 2025-01 게시 | https://georgia.org/sites/default/files/2025-01/georgia_korea_connection_2024.pdf | 조지아 한국 사업장 110곳 이상·1.7만 명이라는 합계, 개별 공장 목록 없음(기아·HMGMA·SK온 잭슨카운티·한화큐셀 달튼만 서술) | Y (pdftotext로 전문 확인) |
| 11 | Chaebol expand investment in US | Korea Times | 2019-05-14 | https://www.koreatimes.co.kr/business/companies/20190514/chaebol-expand-investment-in-us | 롯데케미칼 레이크찰스·SK이노 조지아·LG전자 테네시·큐셀 조지아·삼성 SC (2019 시점) | Y |

열려고 했으나 실패한 것: Atlas EV Hub 배터리 공장 지도(404), Reuters 한국 기업 1,500억 달러 팩트박스(stockopedia 403, 본문 못 봄), 한국 언론 인포그래픽·KOTRA/KITA 공장 지도(검색에서 집계형 자료 발견 못함), E2 Clean Economy Works(검색 요약만, 한국 기업 항목 확인 못함 — opened=N).

## 우리 목록(current_plants.csv)에 없는 시설
- 추가(`plants_lists.csv`): L_01 한국타이어 클락스빌 공장 (목록 #5, 한국앤컴퍼니그룹 31위, TNECD 공문으로 검증).

## 미검증 후보
- 블루오벌SK 켄터키 1·2공장(SK온-포드): 목록 #9에 있음. 2025-12-11 합작 해산 발표로 켄터키 2개 공장은 포드 소유로 넘어갔다는 검색 요약(electrek·electrive 등, 직접 열지 않음)이라 SK 그룹 소유가 아님 → 보류. 우리 목록은 테네시(p15)만 보유. 소유 이전 시점과 SK온 지분 여부는 미확인.
- ALUKO(알루코) 매디슨카운티 TN 배터리 케이스 공장(목록 #5): 알루코는 top100 명단에 없음 → 범위 밖.
- 한화어드밴스드머티리얼즈 오펠라이카 공장(AL): 어떤 집계 목록에도 없었고, 검색 요약(businessfacilities·wtvm, 열람 실패 403/미열람)에서 2017년 약 2천만 달러 증설·누적 약 8천만 달러만 확인. 우리 목록엔 오펠라이카 시마론(g03)·한화디펜스(p52)만 있음. 열린 출처가 없어 CSV 제외.
- 현대모비스 앨라배마 몽고메리 모듈 공장·조지아 공장: 목록 #10·검색 요약에서만 언급, 해당 목록들에 공장 단위 정보 없음 → 다른 에이전트 범위(1~30위 상세)에 맡김.

## 우리 목록과 집계 목록 간 충돌·참고
- 한화큐셀: 우리 p49(카터스빌 가동)·p50(달튼 가동). 목록 #10(GDEcD, 2024 팩트시트)은 달튼 투자 1.5억 달러·500명으로 서술 — 우리 행의 투자·고용이 비어 있으면 보강 여지(p50 단순 비교는 하지 않음, 우리 행 투자액 열 미확인 상태).
- 현대차·SK온 합작(HSBMA): 위키(#8)는 "킹스턴, 조지아 2026" 표기, 우리 p11은 카터스빌(Bartow). 같은 카운티 인근 지명 차이로 추정(확인 필요).
- 랜싱: 위키(#8)는 2026 가동, GreenTechLead(#9)는 2026-08 생산 개시·투자 20억 달러 이상·900명 → 우리 p22와 가동 시점 일치(status_as_of 2026-08-18).
- LGES 스프링힐: KEI Q1(#2) 2026-03-17 ESS 전환 7천만 달러 발표, 우리 p21은 paused/LFP ESS 전환 중으로 기록 — 방향 일치. 투자액 7천만 달러는 우리 행에 반영 여부 미확인.
- LS일렉트릭 유타: KEI Q1(#2) 1.68억 달러(3월 18일 표기) vs 우리 p58 announced 2026-03-19(투자액 열은 "16..."로 시작, 상세 미대조) — 날짜 하루 차이.
- 한화에어로스페이스 아칸소: KEI Q3(#4) 22억 달러 군수시설, 2026-09-21 → 우리 p51 파인블러프(2026-09-21 announced)와 일치.
- 한국타이어 클락스빌 투자액: TNECD 3단계 6.12억 달러·누적 약 22억 달러 vs 보도 2·3단계 16억 달러 — 출처 간 차이(L_01 notes에 병기).
- 테네시 한국 투자 합계: Korea Herald(2025-10) 24개사 약 60억 달러 vs Site Selection(2026-08) 2019년 이후 140억 달러 초과 — 집계 기준 차이로 추정(미확인).
