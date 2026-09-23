"""공식 포스터에서 PWA 아이콘(192/512)을 생성한다.

포스터는 세로로 길어 그대로 줄이면 제목이 뭉개진다.
정사각 크롭 위치를 조절해 제목이 살아있는 구간을 잡는다.

사용:
    python make_icons.py poster.jpg 프로젝트경로
    python make_icons.py poster.jpg . --anchor 0.45   # 더 아래쪽을 크롭
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("poster", help="원본 포스터 이미지")
    ap.add_argument("outdir", nargs="?", default=".", help="아이콘을 저장할 프로젝트 경로")
    ap.add_argument("--anchor", type=float, default=0.30,
                    help="세로 크롭 위치 0.0=최상단 ~ 1.0=최하단 (기본 0.30)")
    args = ap.parse_args()

    src = Path(args.poster)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    im = Image.open(src).convert("RGB")
    w, h = im.size
    print(f"원본 {src.name} {w}x{h}  anchor={args.anchor}")

    side = min(w, h)
    left = (w - side) // 2
    top = int((h - side) * args.anchor)
    square = im.crop((left, top, left + side, top + side))

    # 180 은 iOS 가 홈 화면 아이콘으로 쓰는 크기다 (apple-touch-icon).
    # 이 파일과 선언이 없으면 브라우저가 오리진 루트로 폴백해
    # 다른 작품 아이콘이 나온다 — pitfalls §25.
    targets = [(180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")]

    for size, fname in targets:
        icon = square.resize((size, size), Image.LANCZOS)
        # sw.js 가 아이콘을 프리캐시하므로 용량을 줄인다.
        # 아이콘 크기에서는 팔레트 양자화로 인한 화질 차이가 보이지 않는다.
        icon = icon.quantize(colors=256, method=Image.MEDIANCUT,
                             dither=Image.FLOYDSTEINBERG)
        path = out / fname
        icon.save(path, "PNG", optimize=True)
        print(f"  {path.name:22s} {size}x{size}  {path.stat().st_size / 1024:.1f}KB")

    print("""
다음을 확인할 것:
  1. index.html 의 <title> 뒤에 아이콘 선언이 있는가
       <link rel="icon" type="image/png" href="icon-192.png">
       <link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
     없으면 오리진 루트로 폴백해 다른 작품 아이콘이 나온다 (pitfalls §25).
  2. manifest.json 의 icons 에 180x180 이 있는가
  3. sw.js 의 PRECACHE_URLS 에 apple-touch-icon.png 를 넣고 CACHE_NAME 을 올렸는가

이미 홈 화면에 추가한 기기는 지우고 다시 추가해야 아이콘이 바뀐다.""")


if __name__ == "__main__":
    main()
