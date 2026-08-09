#!/usr/bin/env python3
"""공공기관 채용정보(공공데이터포털, 재정경제부_공공기관 채용정보 조회서비스)를
가져와 docs/jobs-live.json 으로 저장한다. GitHub Actions에서 매일 실행.

필요 환경변수: DATA_GO_KR_API_KEY (공공데이터포털 일반 인증키 Decoding 값)
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

KEY = os.environ.get("DATA_GO_KR_API_KEY")
if not KEY:
    sys.exit("DATA_GO_KR_API_KEY 환경변수가 없습니다.")

BASE = "https://apis.data.go.kr/1051000/recruitment/list"

params = {
    "serviceKey": KEY,
    "numOfRows": "150",
    "pageNo": "1",
    "resultType": "json",
    "ongoingYn": "Y",          # 접수 진행 중인 공고만
}
url = BASE + "?" + urllib.parse.urlencode(params)

req = urllib.request.Request(url, headers={"User-Agent": "speccheck-bot"})
with urllib.request.urlopen(req, timeout=30) as r:
    body = r.read().decode("utf-8")

try:
    data = json.loads(body)
except json.JSONDecodeError:
    sys.exit("JSON 파싱 실패 — 응답 앞부분: " + body[:500])

rows = data.get("result") or []
if not rows:
    sys.exit("공고 0건 — 응답 앞부분: " + body[:500])

def clean(v):
    return (v or "").strip()

postings = []
for row in rows:
    postings.append({
        "inst": clean(row.get("instNm")),
        "title": clean(row.get("recrutPbancTtl")),
        "region": clean(row.get("workRgnNmLst")),
        "type": clean(row.get("hireTypeNmLst")),
        "ncs": clean(row.get("ncsCdNmLst")),
        "end": clean(str(row.get("pbancEndYmd") or "")),
        "url": clean(row.get("srcUrl")),
    })

# 마감 임박순 정렬
postings.sort(key=lambda p: p["end"] or "99999999")

kst = timezone(timedelta(hours=9))
out = {
    "updated": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
    "source": "공공데이터포털 공공기관 채용정보 (재정경제부)",
    "count": len(postings),
    "postings": postings,
}

os.makedirs("docs", exist_ok=True)
with open("docs/jobs-live.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"saved docs/jobs-live.json — {len(postings)}건")
