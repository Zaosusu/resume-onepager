#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 examples/assets/placeholder.png —— 一张合成的占位人像。

为什么不用网上找的照片：仓库要能公开分发，任何真人照片都有肖像权和授权问题。
这张图完全由代码画出来，MIT 许可下随仓库分发没有任何负担。

构图刻意做成标准人像取景：头部中心在画幅 30% 高度处。这样 photo_style 无论
panel 还是 circle，都不需要额外的 photo_focus / photo_zoom 就能得到正确构图——
新用户第一次渲染就该是对的。
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw

W, H = 600, 800
SS = 4                                  # 超采样倍数，用于抗锯齿

BG_TOP, BG_BOTTOM = (222, 229, 241), (196, 209, 230)
FIGURE = (140, 160, 192)


def main() -> None:
    w, h = W * SS, H * SS
    im = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(im)

    # 背景竖向渐变
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    cx = w // 2
    head_cy = round(0.30 * h)            # 头部中心 → 画幅 30% 高度
    head_r = round(0.115 * h)

    # 肩与躯干：一个大圆角矩形，顶端塞在头下方，底部出画
    torso_half = round(0.30 * w)
    torso_top = head_cy + round(head_r * 1.30)
    d.rounded_rectangle([cx - torso_half, torso_top, cx + torso_half, h + torso_half],
                        radius=round(torso_half * 0.8), fill=FIGURE)

    # 颈部：补上头与躯干之间的空隙
    neck_half = round(head_r * 0.42)
    d.rectangle([cx - neck_half, head_cy, cx + neck_half, torso_top + 10], fill=FIGURE)

    # 头部（最后画，盖住颈部接缝）
    d.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=FIGURE)

    out = Path(__file__).resolve().parent.parent / 'examples' / 'assets' / 'placeholder.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    im.resize((W, H), Image.LANCZOS).save(out, optimize=True)
    print(f'占位人像 → {out}  ({W}×{H})')


if __name__ == '__main__':
    main()
