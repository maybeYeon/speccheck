#!/usr/bin/env python3
"""공공기관 채용정보(공공데이터포털, 재정경제부_공공기관 채용정보 조회서비스)를
가져와 docs/jobs-live.json 으로 저장한다. GitHub Actions에서 매일 실행.

필요 환경변수: DATA_GO_KR_API_KEY (공공데이터포털 일반 인증키 Decoding 값)
"""
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

# GitHub 러너에서 IPv6 경로가 데이터포털과 안 맞아 타임아웃 나는 경우가 있어 IPv4 강제
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, *args, **kwargs):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
socket.getaddrinfo = _ipv4_only

KEY = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
if not KEY:
    sys.exit("DATA_GO_KR_API_KEY 환경변수가 없습니다.")
# Encoding 키(%가 포함된 값)를 등록한 경우 디코딩해서 이중 인코딩 방지
if "%" in KEY:
    KEY = urllib.parse.unquote(KEY)

params = {
    "serviceKey": KEY,
    "numOfRows": "150",
    "pageNo": "1",
    "resultType": "json",
    "ongoingYn": "Y",          # 접수 진행 중인 공고만
}
query = urllib.parse.urlencode(params)

# 해외 러너에서 접속이 불안정하므로 http/https를 번갈아 총 12회 재시도
body = None
last_err = None
TRIES = 12
for attempt in range(1, TRIES + 1):
    scheme = "https" if attempt % 2 == 1 else "http"
    url = f"{scheme}://apis.data.go.kr/1051000/recruitment/list?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "speccheck-bot"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8")
        break
    except urllib.error.HTTPError as e:
        last_err = e
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        print(f"시도 {attempt}/{TRIES} 실패 ({scheme}): {e} — {detail}", flush=True)
        time.sleep(10)
    except Exception as e:
        last_err = e
        print(f"시도 {attempt}/{TRIES} 실패 ({scheme}): {e}", flush=True)
        time.sleep(10)
if body is None:
    sys.exit(f"{TRIES}회 재시도 모두 실패: {last_err}")

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
