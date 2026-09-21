"""L2 정적 점검 — 브라우저 없이 앱 파일을 검사한다.

  1) 베이스 작품 잔재 — **배포되는 앱 파일 전부** (index.html 만이 아니다)
  2) getElementById 참조 대비 실제 id  (배역 축소 후 필수)
  3) ROLES / SHORT / calFilter 키 정합성
  4) 외부 링크 인벤토리 — 허용 목록에 없으면 물음표
  5) theme-color 메타 == manifest.json 의 theme_color
  6) 허브 연동 — openFromHub 딥링크와 sw.js 오프라인 폴백
  7) 양도 처리 — 관람으로 치지 않는지 (빠지면 숫자가 조용히 틀린다)
  8) 캐스팅 재동기화 — schedule.json 변경이 D-day·예정 목록에 반영되는지

사용:
    python check_html.py [프로젝트경로]

설정은 프로젝트 루트의 check-config.json 을 쓰고,
없으면 스킬의 templates/legacy-terms.json 을 쓴다.
"""

from __future__ import annotations

import json
import re
import sys
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

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
HTML = ROOT / "index.html"
SKILL = Path(__file__).resolve().parent.parent

# 잔재·링크 검사 대상 — 배포되는 파일 전부.
# index.html 만 보다가 guide.html 이 통째로 베이스 작품인 걸 놓친 적이 있다.
SCAN_FILES = ("index.html", "guide.html", "manifest.json", "sw.js")

# 개발 도구는 제외 (하네스·설정에는 베이스 이름이 남아도 된다)
# selftest.html, _shots.html, check-config.json, TEST_SCENARIOS.md

# 동적으로 만들어지는 id 는 정적 검사에서 제외
DYNAMIC_PREFIXES = ("combo-", "board-", "stamp-", "rec-photo-")


def load_config() -> dict:
    for p in (ROOT / "check-config.json", SKILL / "templates" / "legacy-terms.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8-sig"))
    return {}


def main() -> int:
    if not HTML.exists():
        print(f"index.html 을 찾을 수 없습니다: {HTML}")
        return 1

    cfg = load_config()
    text = HTML.read_text(encoding="utf-8-sig")
    errors: list[str] = []

    # ── 1. 잔재 — 배포 파일 전부 ──────────────────────────
    # 단어경계 필수: 'abel' 이 'label' 에 걸리고, 배우 이름이 두 작품에 겹칠 수 있다
    parts = []
    if cfg.get("word_terms"):
        parts.append(r"\b(" + "|".join(map(re.escape, cfg["word_terms"])) + r")\b")
    if cfg.get("raw_terms"):
        parts.append("|".join(map(re.escape, cfg["raw_terms"])))

    scanned = []
    if parts:
        residue_re = re.compile("|".join(parts))
        for name in cfg.get("scan_files", SCAN_FILES):
            p = ROOT / name
            if not p.exists():
                continue
            scanned.append(name)
            body = p.read_text(encoding="utf-8-sig")
            hits = [(i, ln.strip()) for i, ln in enumerate(body.splitlines(), 1)
                    if residue_re.search(ln)]
            if hits:
                errors.append(f"{name} — 베이스 작품 잔재 {len(hits)}줄")
                for i, ln in hits[:8]:
                    errors.append(f"    L{i}: {ln[:88]}")
                if len(hits) > 8:
                    errors.append(f"    ... {len(hits) - 8}줄 더")

    # ── 2. id 정합성 ─────────────────────────────────────
    defined = set(re.findall(r"""\bid=["']([^"']+)["']""", text))
    referenced = set(re.findall(r"""getElementById\(\s*['"]([^'"]+)['"]\s*\)""", text))
    missing = {r for r in referenced - defined if not r.startswith(DYNAMIC_PREFIXES)}
    if missing:
        errors.append(f"HTML 에 없는 id 를 JS 가 참조 {len(missing)}건")
        for m in sorted(missing):
            errors.append(f"    #{m}")

    # ── 3. 배역 키 정합성 ────────────────────────────────
    keys: list[str] = []
    block = re.search(r"const ROLES = \[(.*?)\];", text, re.S)
    if not block:
        errors.append("ROLES 배열을 찾지 못함")
    else:
        keys = re.findall(r"key:\s*'([^']+)'", block.group(1))
        expected = cfg.get("expected_roles")
        if expected and keys != expected:
            errors.append(f"ROLES 키 불일치: {keys} != {expected}")

    for key in keys:
        if f'id="rec-{key}"' not in text:
            errors.append(f"배역 '{key}' 의 입력 요소 #rec-{key} 없음")

    for name, pattern in (("SHORT", r"const SHORT = \{(.*?)\};"),
                          ("calFilter", r"let calFilter = \{(.*?)\};")):
        m = re.search(pattern, text, re.S)
        if not m:
            errors.append(f"{name} 를 찾지 못함")
            continue
        found = re.findall(r"(\w+)\s*:", m.group(1))
        if sorted(found) != sorted(keys):
            errors.append(f"{name} 키 불일치: {found} != {keys}")

    # ── 4. 외부 참조 인벤토리 — 배포 파일 전부 ────────────
    # 블랙리스트만으로는 낯선 고유명사(제작사 계정 등)를 못 잡는다.
    allowed = cfg.get("allowed_urls", [])
    urls: set[str] = set()
    for name in cfg.get("scan_files", SCAN_FILES):
        p = ROOT / name
        if p.exists():
            urls |= set(re.findall(r"https?://([^\s\"'<>)]+)",
                                   p.read_text(encoding="utf-8-sig")))
    unknown = sorted(u for u in urls if not any(a in u for a in allowed))

    # ── 5. 테마 색상 정합성 ───────────────────────────────
    # theme-color 메타가 모바일 브라우저 주소창 색을 결정한다.
    # manifest 만 고치고 이걸 놓치면 앱 색과 브라우저 UI 색이 어긋난다.
    meta = re.search(r'<meta name="theme-color" content="([^"]+)"', text)
    meta_color = meta.group(1) if meta else None
    manifest_path = ROOT / "manifest.json"
    manifest_color = None
    if manifest_path.exists():
        manifest_color = json.loads(
            manifest_path.read_text(encoding="utf-8-sig")).get("theme_color")
    if not meta_color:
        errors.append("index.html 에 theme-color 메타가 없음")
    elif manifest_color and meta_color.lower() != manifest_color.lower():
        errors.append(
            f"theme-color 불일치: index.html {meta_color} != manifest.json {manifest_color}")

    # ── 6. 허브 연동 ──────────────────────────────────────
    # otk-schedule 은 앱에 deepLink 표시가 없으면 지원한다고 본다.
    # 개조하다 지워버리면 '앱에서 보기' 가 회차가 아니라 첫 화면만 연다.
    deeplink_ok = True
    if "function openFromHub" not in text:
        errors.append("openFromHub 가 없음 — 허브에서 회차로 못 들어온다")
        deeplink_ok = False
    elif not re.search(r"\n\s*openFromHub\(\);", text):
        errors.append("openFromHub 가 정의만 되고 init() 에서 호출되지 않음")
        deeplink_ok = False

    sw_path = ROOT / "sw.js"
    if sw_path.exists():
        sw = sw_path.read_text(encoding="utf-8-sig")
        # ?date=... 는 캐시 키가 달라 precache 한 '/' 와 안 맞는다.
        # 폴백이 없으면 오프라인에서 딥링크로 들어올 때 화면이 아예 안 뜬다.
        if "navigate" not in sw:
            errors.append("sw.js 에 화면 이동 폴백이 없음 — 오프라인 딥링크가 깨진다")
        if re.search(r"caches\.match\([^)]*\)\s*\.then\(cached\s*=>\s*\{\s*if\s*\(cached\)", sw):
            errors.append("sw.js 가 HTML 을 캐시 우선으로 내준다 — 배포해도 갱신이 안 된다")

    # ── 7. 양도 처리 ──────────────────────────────────────
    # 양도(표는 있었지만 안 본 회차)는 관람으로 치지 않아야 한다.
    # 빠져도 에러가 안 나고 화면도 멀쩡하다 — 숫자만 조용히 틀린다.
    # 할인권이 안 돌아오고, 도장판 개수가 어긋나고, 통계에 섞인다.
    transfer_ok = True

    def fail_transfer(msg: str) -> None:
        nonlocal transfer_ok
        errors.append(msg)
        transfer_ok = False

    if "function isTransferred" not in text:
        fail_transfer("양도 처리(isTransferred/watchedOnly)가 없음")
    else:
        # 폼 — 배역 축소 때 form-group 을 지우다 같이 날아가기 쉽다
        for el in ("rec-transferred", "rec-transfer-to"):
            if f'id="{el}"' not in text:
                fail_transfer(f"양도 입력 #{el} 없음 — 폼을 지울 때 함께 날아간 듯")
        if "function onRecTransferredChange" not in text:
            fail_transfer("onRecTransferredChange 없음")
        if "function removeStampsForRecord" not in text:
            fail_transfer("removeStampsForRecord 없음 — 양도해도 도장이 회수되지 않는다")
        if "status:" not in text or "transferTo:" not in text:
            fail_transfer("기록에 status/transferTo 를 저장하지 않음")

        # 집계 함수가 양도를 빼고 있는지. 작품마다 할인권·도장 구조가 달라
        # 이 함수들을 다시 쓰는 것이 개조의 핵심 작업이고, 그때 빠지기 쉽다.
        def body_of(fn: str) -> str | None:
            m = re.search(rf"^(?:async )?function {fn}\s*\(", text, re.M)
            if not m:
                return None
            nxt = re.search(r"^(?:async )?function \w+\s*\(", text[m.end():], re.M)
            return text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]

        # 없는 함수는 건너뛴다 (쿠폰 구조가 다르면 아예 없는 작품이 있다)
        for fn in ("calcCouponCount", "renderStats", "queryPairStats", "renderHeatmap",
                   "renderCouponList", "renderCouponAllHistory",
                   "useDoubleStamp", "scanPastRecordsForCouponPacks"):
            body = body_of(fn)
            if body is None:
                continue
            if "getRecords()" in body and "watchedOnly" not in body:
                fail_transfer(f"{fn} 이 양도를 걸러내지 않음 — 숫자가 조용히 틀린다")

    # ── 8. 캐스팅 재동기화 ────────────────────────────────
    # 기록은 만들 때 스케줄에서 캐스팅을 복사해 넣는다.
    # 캘린더는 스케줄을 직접 읽어 바뀌지만 D-day 카드·예정 목록·상세는
    # 기록을 읽으므로, 재동기화가 없으면 schedule.json 을 새로 올려도
    # 이미 예매해 둔 회차에 옛 배우가 계속 보인다.
    casting_ok = True
    if "function syncCastingFromSchedule" not in text:
        errors.append("syncCastingFromSchedule 이 없음 — 캐스팅을 바꿔도 D-day 가 안 바뀐다")
        casting_ok = False
    elif not re.search(r"\n\s*syncCastingFromSchedule\(\);", text):
        errors.append("syncCastingFromSchedule 이 정의만 되고 스케줄 수신 뒤에 불리지 않음")
        casting_ok = False
    else:
        m8 = re.search(r"function syncCastingFromSchedule\b(.*?)\n\}", text, re.S)
        b8 = m8.group(1) if m8 else ""
        # 지난 회차는 실제로 본 캐스팅이라 덮어쓰면 안 된다
        # 캐스팅은 관찰값이 아니라 스케줄의 복사본이므로 지난 회차도 맞춘다.
        # 다만 폼에서 스케줄과 다르게 적은 기록(castManual)은 지켜야 한다.
        if "castManual" not in b8:
            errors.append("syncCastingFromSchedule 이 castManual 을 안 봄 — 직접 적은 캐스팅을 덮어쓴다")
            casting_ok = False

    # ── 결과 ─────────────────────────────────────────────
    print(f"캐스팅 재동기화: {'있음' if casting_ok else '없음/불완전'}")
    print(f"양도 처리: {'있음' if transfer_ok else '없음/불완전'}")
    print(f"허브 딥링크: {'있음' if deeplink_ok else '없음'}")
    print(f"잔재 검사 대상: {', '.join(scanned) if scanned else '(없음)'}")
    print(f"정의된 id {len(defined)}개 / JS 참조 {len(referenced)}개")
    print(f"ROLES 키: {keys}")
    print(f"테마 색상: {meta_color}")
    print(f"외부 링크 {len(urls)}개 (미확인 {len(unknown)}개)")
    for u in unknown:
        print(f"    ? {u[:100]}")

    if errors:
        print("\n[실패]")
        for e in errors:
            print("  " + e)
        return 1

    print("\n정적 점검 통과 — 오류 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
