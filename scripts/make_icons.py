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

    for size in (192, 512):
        icon = square.resize((size, size), Image.LANCZOS)
        # sw.js 가 아이콘을 프리캐시하므로 용량을 줄인다.
        # 아이콘 크기에서는 팔레트 양자화로 인한 화질 차이가 보이지 않는다.
        icon = icon.quantize(colors=256, method=Image.MEDIANCUT,
                             dither=Image.FLOYDSTEINBERG)
        path = out / f"icon-{size}.png"
        icon.save(path, "PNG", optimize=True)
        print(f"  {path.name}  {size}x{size}  {path.stat().st_size / 1024:.1f}KB")

    print("\n아이콘을 바꿨으면 sw.js 의 CACHE_NAME 을 올려야 기존 사용자에게 반영된다.")


if __name__ == "__main__":
    main()
