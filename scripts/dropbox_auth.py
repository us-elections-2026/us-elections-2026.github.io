#!/usr/bin/env python3
"""Dropbox refresh 토큰 1회 발급 (사람이 로컬에서 한 번 실행).
1) https://www.dropbox.com/developers/apps → Create app → Scoped access → Full Dropbox → 이름 임의
   Permissions 탭에서 files.metadata.read · files.content.read · files.content.write 체크 후 Submit.
2) 아래 실행 → 출력된 URL을 브라우저에서 열어 승인 → 코드 붙여넣기 → 출력된 세 값을 GitHub Secrets에 등록:
   gh secret set DROPBOX_APP_KEY / DROPBOX_APP_SECRET / DROPBOX_REFRESH_TOKEN
"""
import json, sys, urllib.parse, urllib.request
key = input("App key: ").strip(); secret = input("App secret: ").strip()
print("\n브라우저에서 열기:\nhttps://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode(
    {"client_id": key, "response_type": "code", "token_access_type": "offline"}))
code = input("\n승인 코드: ").strip()
data = urllib.parse.urlencode({"code": code, "grant_type": "authorization_code", "client_id": key, "client_secret": secret}).encode()
with urllib.request.urlopen(urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=data), timeout=60) as r:
    j = json.load(r)
print("\nDROPBOX_APP_KEY=" + key + "\nDROPBOX_APP_SECRET=" + secret + "\nDROPBOX_REFRESH_TOKEN=" + j["refresh_token"])
