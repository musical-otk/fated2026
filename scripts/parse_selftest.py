"""headless Chrome 이 덤프한 selftest.html 결과를 읽어 콘솔에 정리한다."""

import re
import sys
from html import unescape
from pathlib import Path

path = Path(sys.argv[1])
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
