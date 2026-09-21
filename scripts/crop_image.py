"""조밀한 이미지를 구역별로 잘라 확대 저장한다.

좌석배치도·캐스팅표처럼 셀이 촘촘한 이미지를 통째로 읽으면 거의 확실히 틀린다.
구역을 나눠 확대해 읽고, 판독 결과는 반드시 독립 출처와 대조할 것.

사용:
    # 좌표를 직접 지정
    python crop_image.py seat.jpg out/ --regions "1f_left:95,465,560,880" "1f_right:530,465,995,880"

    # 좌표를 모를 때: 격자로 자동 분할해 위치를 잡는다
    python crop_image.py seat.jpg out/ --grid 2x2

좌표는 (left, top, right, bottom). 먼저 원본을 한 번 보고 눈대중으로 잡으면 된다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def parse_region(spec: str) -> tuple[str, tuple[int, int, int, int]]:
    name, _, coords = spec.partition(":")
    nums = [int(x) for x in coords.split(",")]
    if len(nums) != 4:
        raise ValueError(f"좌표는 4개여야 합니다: {spec}")
    return name, (nums[0], nums[1], nums[2], nums[3])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--regions", nargs="*", default=[],
                    help='"이름:left,top,right,bottom" 형식')
    ap.add_argument("--grid", help='"열x행" — 좌표를 모를 때 균등 분할 (예: 2x2)')
    ap.add_argument("--scale", type=int, default=3, help="확대 배율 (기본 3)")
    args = ap.parse_args()

    src = Path(args.image)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    im = Image.open(src)
    print(f"원본 {src.name} {im.size}")

    regions: list[tuple[str, tuple[int, int, int, int]]] = []
    if args.grid:
        cols, rows = (int(v) for v in args.grid.lower().split("x"))
        w, h = im.size
        # 경계에 걸친 셀이 잘리지 않도록 약간 겹쳐 자른다
        ox, oy = w // (cols * 12), h // (rows * 12)
        for r in range(rows):
            for c in range(cols):
                l = max(0, c * w // cols - ox)
                t = max(0, r * h // rows - oy)
                rt = min(w, (c + 1) * w // cols + ox)
                b = min(h, (r + 1) * h // rows + oy)
                regions.append((f"r{r+1}c{c+1}", (l, t, rt, b)))
    regions += [parse_region(s) for s in args.regions]

    if not regions:
        ap.error("--regions 또는 --grid 중 하나는 필요합니다")

    for name, box in regions:
        crop = im.crop(box)
        big = crop.resize((crop.width * args.scale, crop.height * args.scale),
                          Image.LANCZOS)
        path = out / f"{src.stem}_{name}.png"
        big.save(path)
        print(f"  {path.name}  {crop.width}x{crop.height} -> {big.size}")


if __name__ == "__main__":
    main()
