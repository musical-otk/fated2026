"""좌석배치도 이미지를 구역별로 잘라 확대 저장한다.

한 장을 통째로 읽으면 열별 좌석번호를 놓치기 쉬워서,
블록 단위로 나눈 뒤 3배 확대해 판독 정확도를 올린다.
"""

import sys
from pathlib import Path

from PIL import Image

SRC = Path(r"d:\workspace\x-collector\data\raw\_LIVECONNECTION\2092839605913768312_4.jpg")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SCALE = 3

# (이름, left, top, right, bottom)
REGIONS = [
    ("1f_left",   95,  465,  560,  880),
    ("1f_right", 530,  465,  995,  880),
    ("2f_left",  150,  940,  560, 1115),
    ("2f_right", 540,  940,  960, 1115),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(SRC)
    print(f"원본 {SRC.name} {im.size}")

    for name, l, t, r, b in REGIONS:
        crop = im.crop((l, t, r, b))
        big = crop.resize((crop.width * SCALE, crop.height * SCALE), Image.LANCZOS)
        path = OUT / f"seat_{name}.png"
        big.save(path)
        print(f"  {path.name}  {crop.width}x{crop.height} -> {big.size}")


if __name__ == "__main__":
    main()
