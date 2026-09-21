"""L1 데이터 검증 — schedule / events / seating 을 show-info 기준으로 검사한다.

사용:
    python scripts/validate.py            # 프로젝트 루트 기준
    python validate.py <프로젝트경로>

show-info.json 에 아래가 있으면 그 값으로 검사하고, 없으면 데이터에서 역산한다.

    "expectedShowtimes": { "화": ["20:00"], "토": ["14:00","18:00"] },
    "holidays": { "2026-10-09": "한글날" }

seating.json 은 두 형태를 모두 받는다.
    구간형   { "row":"A", "first":3, "last":24, "unavailable":[3,4] }
    구역형   { "row":"A", "l":[4,6], "m":[7,13], "r":[14,19] }
"""

from __future__ import annotations

import collections
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
WEEK = "월화수목금토일"

# 출력 인코딩은 호출자가 정한다 (run_tests.ps1 이 PYTHONIOENCODING 과
# [Console]::OutputEncoding 을 함께 UTF-8 로 맞춘다). 여기서 encoding 을 강제하면
# cp949 콘솔에서 한글이 전부 깨진다.
# 다만 '—'(em-dash)처럼 cp949 에 없는 글자 하나 때문에 검사가 통째로 죽는 일은 막는다.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass


def load(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else None


info = load("show-info.json")
schedule = load("schedule.json") or []
events = load("events.json") or []
seating = load("seating.json")

if not info:
    print("show-info.json 이 없습니다")
    raise SystemExit(1)

roles = {r["key"]: set(r["actors"]) for r in info["roles"]}
start = date.fromisoformat(info["startDate"])
end = date.fromisoformat(info["endDate"])
holidays = info.get("holidays", {})

errors: list[str] = []
warnings: list[str] = []

# ── 공연시간 기준 ────────────────────────────────────────
# 선언값이 있으면 그것으로 검사한다. 없으면 역산만 하고 시간 검사는 건너뛴다
# (작품마다 요일별 시간이 크게 달라 고정 표를 강요하면 오탐만 늘어난다).
declared = info.get("expectedShowtimes")
expected: dict[int, set[str]] = {}
if declared:
    for k, times in declared.items():
        if k in WEEK:
            expected[WEEK.index(k)] = set(times)

# ── 회차 검증 ────────────────────────────────────────────
seen: set[tuple] = set()
for i, s in enumerate(schedule, 1):
    tag = f"[{i}] {s.get('date')} {s.get('time')}"
    try:
        d = date.fromisoformat(s["date"])
    except (KeyError, ValueError):
        errors.append(f"{tag} 날짜 형식 오류")
        continue

    if not (start <= d <= end):
        errors.append(f"{tag} 공연기간({start}~{end}) 밖")

    key = (s["date"], s["time"])
    if key in seen:
        errors.append(f"{tag} 중복 회차")
    seen.add(key)

    if declared:
        is_holiday = s["date"] in holidays
        allowed = expected.get(6 if is_holiday else d.weekday(), set())
        why = f"공휴일({holidays[s['date']]})" if is_holiday else f"{WEEK[d.weekday()]}요일"
        if allowed and s["time"] not in allowed:
            warnings.append(f"{tag} {why} 예상 시간 {sorted(allowed)} 와 불일치")

    for rk, cast in roles.items():
        actor = s.get(rk)
        if not actor:
            errors.append(f"{tag} 배역 '{rk}' 누락")
        elif actor not in cast:
            errors.append(f"{tag} '{rk}' = '{actor}' 는 캐스팅 목록에 없음")

    extra = set(s) - {"date", "time"} - set(roles)
    if extra:
        errors.append(f"{tag} 알 수 없는 필드: {sorted(extra)}")

# 1회만 나타나는 시간 — 판독 오류 후보
times = collections.Counter(s["time"] for s in schedule if "time" in s)
rare = [t for t, n in times.items() if n == 1]
if rare:
    warnings.append(f"1회만 나타나는 시간 {rare} — 원본 이미지와 대조할 것")

# ── 이벤트 ───────────────────────────────────────────────
for i, e in enumerate(events, 1):
    try:
        s0, e0 = date.fromisoformat(e["startDate"]), date.fromisoformat(e["endDate"])
    except (KeyError, ValueError):
        errors.append(f"[event {i}] 날짜 형식 오류")
        continue
    if s0 > e0:
        errors.append(f"[event {i}] {e['name']}: 시작일이 종료일보다 늦음")
    if not e.get("color", "").startswith("#"):
        errors.append(f"[event {i}] {e.get('name')}: color 형식 오류")

# ── 좌석 ─────────────────────────────────────────────────
grand = 0
if seating:
    seen_rows: set[str] = set()
    for floor in seating["floors"]:
        total = 0
        for r in floor["rows"]:
            row = r["row"]
            if row in seen_rows:
                errors.append(f"[좌석] 열 '{row}' 중복")
            seen_rows.add(row)

            if "first" in r:                       # 구간형
                spans = [(r["first"], r["last"])]
            else:                                  # 구역형
                spans = [tuple(r[z]) for z in ("l", "m", "r") if r.get(z)]

            for lo, hi in spans:
                if lo > hi:
                    errors.append(f"[좌석] {row}열 구간 오류 {lo}~{hi}")
                else:
                    total += hi - lo + 1
            total += r.get("wheelchair", 0)

            nums = {n for lo, hi in spans if lo <= hi for n in range(lo, hi + 1)}
            for u in r.get("unavailable", []):
                if u not in nums:
                    errors.append(f"[좌석] {row}열 비판매석 {u} 이 좌석 범위 밖")

        if "seatCount" in floor and total != floor["seatCount"]:
            errors.append(f"[좌석] {floor['name']} 합계 {total} != 선언값 {floor['seatCount']}")
        grand += total

    if "totalSeats" in seating and grand != seating["totalSeats"]:
        errors.append(f"[좌석] 전체 합계 {grand} != 선언값 {seating['totalSeats']}")

# ── 결과 ─────────────────────────────────────────────────
print(f"공연 회차 {len(schedule)}건 / 이벤트 {len(events)}건")
if seating:
    blocked = sum(len(r.get("unavailable", [])) for f in seating["floors"] for r in f["rows"])
    chairs = sum(r.get("wheelchair", 0) for f in seating["floors"] for r in f["rows"])
    print("좌석 {}석 ".format(grand) + " · ".join(
        f"{f['name']} {f.get('seatCount','?')}({f.get('grade','')})" for f in seating["floors"]))
    if blocked or chairs:
        print(f"  비판매석 {blocked}석 · 휠체어석 {chairs}석 · 실판매 {grand - blocked - chairs}석")

print(f"공연일 {len({s['date'] for s in schedule if 'date' in s})}일")
mondays = sorted({s["date"] for s in schedule
                  if "date" in s and date.fromisoformat(s["date"]).weekday() == 0})
print(f"월요일 공연: {mondays or '없음'}")

for rk, cast in roles.items():
    counts = {a: sum(1 for s in schedule if s.get(rk) == a) for a in sorted(cast)}
    label = next(r["label"] for r in info["roles"] if r["key"] == rk)
    print(f"  {label:4s} " + " · ".join(f"{a} {n}" for a, n in counts.items()))

if warnings:
    print("\n[경고]")
    for w in warnings:
        print("  " + w)

if errors:
    print("\n[오류]")
    for e in errors:
        print("  " + e)
    raise SystemExit(1)

print("\n검증 통과 — 오류 없음")
