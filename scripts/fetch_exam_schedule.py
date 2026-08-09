#!/usr/bin/env python3
"""한국산업인력공단 국가자격 시험일정 API를 가져와 docs/exam-schedule.json 저장.

필요 환경변수: DATA_GO_KR_API_KEY
"""
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, *args, **kwargs):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
socket.getaddrinfo = _ipv4_only

KEY = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
if not KEY:
    sys.exit("DATA_GO_KR_API_KEY 환경변수가 없습니다.")
if "%" in KEY:
    KEY = urllib.parse.unquote(KEY)

BASE = "apis.data.go.kr/B490007/qualExamSchd/getQualExamSchdList"
YEAR = datetime.now(timezone(timedelta(hours=9))).year


def fetch(qualgb, year):
    params = {
        "serviceKey": KEY,
        "numOfRows": "200",
        "pageNo": "1",
        "dataFormat": "json",
        "implYy": str(year),
        "qualgbCd": qualgb,
    }
    query = urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(1, 13):
        scheme = "https" if attempt % 2 == 1 else "http"
        url = f"{scheme}://{BASE}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "speccheck-bot"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            print(f"[{qualgb}] 시도 {attempt}/12 실패 ({scheme}): {e} — {detail}", flush=True)
            last_err = e
            time.sleep(10)
        except Exception as e:
            print(f"[{qualgb}] 시도 {attempt}/12 실패 ({scheme}): {e}", flush=True)
            last_err = e
            time.sleep(10)
    raise RuntimeError(f"[{qualgb}] 12회 재시도 모두 실패: {last_err}")


def parse_rows(body):
    """JSON 우선, 실패 시 XML 파싱."""
    body = body.strip()
    if body.startswith("{"):
        d = json.loads(body)
        # 응답 구조 후보들을 순서대로 탐색
        for path in [("body", "items"), ("response", "body", "items"), ("items",)]:
            cur = d
            ok = True
            for k in path:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    ok = False
                    break
            if ok:
                if isinstance(cur, dict) and "item" in cur:
                    cur = cur["item"]
                if isinstance(cur, dict):
                    cur = [cur]
                if isinstance(cur, list):
                    return cur
        print("JSON 구조 인식 실패 — 앞부분:", body[:400], flush=True)
        return []
    # XML
    root = ET.fromstring(body)
    rows = []
    for item in root.iter("item"):
        rows.append({c.tag: (c.text or "").strip() for c in item})
    if not rows:
        print("XML에 item 없음 — 앞부분:", body[:400], flush=True)
    return rows


def g(row, key):
    v = row.get(key)
    s = str(v).strip() if v is not None else ""
    return "" if s in ("None", "null") else s


events = []
for qualgb, gbname in [("T", "국가기술자격"), ("S", "국가전문자격")]:
    try:
        rows = parse_rows(fetch(qualgb, YEAR))
    except Exception as e:
        print(f"[{qualgb}] 수집 실패, 건너뜀: {e}", flush=True)
        continue
    print(f"[{qualgb}] {len(rows)}건", flush=True)
    for row in rows:
        desc = g(row, "description") or f"{g(row,'implYy')}년 {g(row,'qualgbNm')} 제{g(row,'implSeq')}회"
        qual = g(row, "qualgbNm") or gbname
        pairs = [
            ("필기 원서접수", g(row, "docRegStartDt"), g(row, "docRegEndDt")),
            ("필기시험", g(row, "docExamStartDt"), g(row, "docExamEndDt")),
            ("필기 합격발표", g(row, "docPassDt"), g(row, "docPassDt")),
            ("실기 원서접수", g(row, "pracRegStartDt"), g(row, "pracRegEndDt")),
            ("실기(면접)시험", g(row, "pracExamStartDt"), g(row, "pracExamEndDt")),
            ("최종 합격발표", g(row, "pracPassDt"), g(row, "pracPassDt")),
        ]
        for kind, start, end in pairs:
            if start and len(start) == 8:
                events.append({
                    "title": desc,
                    "qual": qual,
                    "kind": kind,
                    "start": start,
                    "end": end if (end and len(end) == 8) else start,
                })

if not events:
    sys.exit("시험일정 이벤트 0건 — 응답 구조 확인 필요")

events.sort(key=lambda e: e["start"])
kst = timezone(timedelta(hours=9))
out = {
    "updated": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
    "source": "한국산업인력공단 국가자격 시험일정 (공공데이터포털)",
    "count": len(events),
    "events": events,
}
os.makedirs("docs", exist_ok=True)
with open("docs/exam-schedule.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"saved docs/exam-schedule.json — {len(events)}건")
