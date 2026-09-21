"""headless Chrome 이 덤프한 selftest.html 결과를 읽어 콘솔에 정리한다."""

import re
import sys
from html import unescape
from pathlib import Path

# 출력 인코딩은 호출자가 정한다 (run_tests.ps1 이 PYTHONIOENCODING 과
# [Console]::OutputEncoding 을 함께 UTF-8 로 맞춘다). 여기서 encoding 을 강제하면
# cp949 콘솔에서 한글이 전부 깨진다.
# 다만 '—'(em-dash)처럼 cp949 에 없는 글자 하나 때문에 검사가 통째로 죽는 일은 막는다.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

if len(sys.argv) < 2:
    print("사용: python parse_selftest.py <selftest 덤프.html>")
    raise SystemExit(2)

path = Path(sys.argv[1])
if not path.exists():
    print(f"덤프 파일이 없습니다: {path}")
    raise SystemExit(2)
html = path.read_text(encoding="utf-8", errors="replace")

summary = re.search(r'id="summary"[^>]*>([^<]*)<', html)
rows = re.findall(
    r'<span class="tag (p|f)">(PASS|FAIL)</span>'
    r'<span class="name">(.*?)</span>',
    html, re.S)
groups = re.findall(r'<div class="grp">([^<]*)</div>', html)

def clean(s: str) -> str:
    s = re.sub(r'<div class="detail">(.*?)</div>', r'  ↳ \1', s, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", "", s)).strip()

print(f"요약: {summary.group(1).strip() if summary else '(없음)'}")
print(f"그룹 {len(groups)}개 / 검사 {len(rows)}건\n")

fails = 0
for _, verdict, name in rows:
    mark = "PASS" if verdict == "PASS" else "FAIL"
    if verdict == "FAIL":
        fails += 1
    print(f"  [{mark}] {clean(name)}")

print()
if fails:
    print(f"실패 {fails}건")
    sys.exit(1)
print("전체 통과")
