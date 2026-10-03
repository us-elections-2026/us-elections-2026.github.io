#!/usr/bin/env python3
"""원문 일일 브리핑 → 사이트 정리본 (Anthropic API). GitHub Actions 일일 자동 발행에서 Cowork 10:15 작업을 대신한다.

사용: ANTHROPIC_API_KEY=... python3 scripts/make_site_digest.py <원문.md> <프롬프트.md> <출력 정리본.md>
동작: 프롬프트 파일(§0~§3·§2-1·§2-2)을 시스템 지시로, 원문을 사용자 메시지로 보내 정리본을 받는다.
      check_site_digest.py 로 대조해 실패하면 지적 사항을 붙여 한 번 더 요청한다. 그래도 실패하면 1 반환(원문 전재로 폴백).
모델: DIGEST_MODEL 환경변수(기본 claude-opus-5). 표준 라이브러리만 사용.
"""
from __future__ import annotations  # 호스트 python3(3.9)의 `X | None` 힌트 호환
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"


def ask(system: str, user: str, model: str) -> str:
    body = {"model": model, "max_tokens": 16000, "temperature": 0.2, "system": system,
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.load(r)
    return "".join(b.get("text", "") for b in j["content"] if b.get("type") == "text")


def strip_fence(t: str) -> str:
    t = t.strip()
    m = re.match(r"^```(?:markdown|md)?\n(.*)\n```$", t, re.S)
    return (m.group(1) if m else t).strip() + "\n"


def main() -> int:
    raw_p, prompt_p, out_p = (Path(a) for a in sys.argv[1:4])
    date = raw_p.name[:10]
    prompt = prompt_p.read_text(encoding="utf-8")
    # §4·§5(발행·보고 지시)는 Cowork용이라 뺀다 — 모델은 정리본 본문만 쓴다
    system = re.split(r"^## 4\. ", prompt, flags=re.M)[0]
    system += ("\n\n[실행 환경] 당신은 GitHub Actions 안에서 호출된 편집 모델이다. 파일을 저장하거나 스크립트를 실행하지 말고, "
               "§2 형식의 정리본 **본문만** 출력한다(설명·코드펜스 없이, 첫 줄이 `# 2026 상원 선거 일일 브리핑 — " + date + " (사이트 정리본)`).")
    raw = raw_p.read_text(encoding="utf-8")
    model = os.environ.get("DIGEST_MODEL", "claude-opus-5")
    user = f"오늘(KST) 날짜: {date}\n원문 파일: senate_daily/{raw_p.name}\n\n===== 원문 시작 =====\n{raw}\n===== 원문 끝 =====\n\n위 원문의 사이트 정리본을 작성하라."
    for attempt in (1, 2):
        text = strip_fence(ask(system, user, model))
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(text, encoding="utf-8")
        chk = subprocess.run([sys.executable, str(Path(__file__).parent / "check_site_digest.py"), str(raw_p), str(out_p)],
                             capture_output=True, text=True)
        print(chk.stdout.strip())
        if chk.returncode == 0:
            print(f"[digest] ✓ {out_p.name} ({len(text):,}자, {model}, 시도 {attempt})"); return 0
        user += ("\n\n[대조 스크립트 지적 — 고쳐서 정리본 전체를 다시 출력하라. 원문에 없는 숫자는 쓰지 말고, "
                 "지적된 숫자는 원문 표기대로 바꾸거나 지워라]\n" + chk.stdout)
    print(f"[digest] ✗ {date} 정리본 대조 2회 실패 — 폴백(원문 전재)", file=sys.stderr)
    out_p.unlink(missing_ok=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
