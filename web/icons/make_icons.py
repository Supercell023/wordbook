#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词书 PWA 图标生成器 —— 纯标准库，不需要 Pillow / cairosvg。

用法（在仓库根目录）：
    python3 web/icons/make_icons.py            # 生成 / 覆盖全部图标
    python3 web/icons/make_icons.py --check    # 只校验现有 PNG 的真实像素尺寸

产物（都写在本文件所在目录）：
    icon-192.png          192x192  普通图标（圆角米色底）
    icon-512.png          512x512  普通图标
    maskable-512.png      512x512  maskable（满幅底色 + 图形收在 80% 安全区）
    apple-touch-icon.png  180x180  iOS 主屏图标（满幅方底，圆角由 iOS 自己切）
    favicon-32.png         32x32   浏览器标签页图标（简化线稿）

配色和站点一致：米色纸感 #f4efe4 / 墨蓝 #2d4a74 / 书签金 #c08a2e。
"""
import argparse
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

BG = (244, 239, 228)    # #f4efe4 纸感米色
CARD = (255, 253, 247)  # #fffdf7 纸页
INK = (45, 74, 116)     # #2d4a74 墨蓝（封面）
INK2 = (36, 64, 95)     # #24405f 书脊（压深一档）
GOLD = (192, 138, 46)   # #c08a2e 书签

SS = 4  # 超采样倍数（先画大图再盒式缩小 = 抗锯齿）


# --------------------------------------------------------------------------- #
# 形状判定：都是 (x, y) -> bool，坐标是 0..1 的归一化值
# --------------------------------------------------------------------------- #
def rrect(x0, y0, x1, y1, r):
    r = max(0.0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))

    def inside(x, y):
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        cx0, cy0, cx1, cy1 = x0 + r, y0 + r, x1 - r, y1 - r
        dx = cx0 - x if x < cx0 else (x - cx1 if x > cx1 else 0.0)
        dy = cy0 - y if y < cy0 else (y - cy1 if y > cy1 else 0.0)
        return dx * dx + dy * dy <= r * r

    return inside


def poly(points):
    def inside(x, y):
        hit = False
        n = len(points)
        j = n - 1
        for i in range(n):
            xi, yi = points[i]
            xj, yj = points[j]
            if (yi > y) != (yj > y):
                xc = xi + (y - yi) * (xj - xi) / (yj - yi)
                if x < xc:
                    hit = not hit
            j = i
        return hit

    return inside


def bbox_of(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------- #
# 画布
# --------------------------------------------------------------------------- #
class Canvas(object):
    def __init__(self, size):
        self.size = size
        self.w = size * SS
        self.px = bytearray(self.w * self.w * 4)

    def paint(self, inside, color, bbox=(0.0, 0.0, 1.0, 1.0)):
        W = self.w
        px = self.px
        r, g, b = color
        x0 = max(0, int(bbox[0] * W) - 1)
        y0 = max(0, int(bbox[1] * W) - 1)
        x1 = min(W, int(bbox[2] * W) + 2)
        y1 = min(W, int(bbox[3] * W) + 2)
        for y in range(y0, y1):
            fy = (y + 0.5) / W
            row = y * W * 4
            for x in range(x0, x1):
                if inside((x + 0.5) / W, fy):
                    i = row + x * 4
                    px[i] = r
                    px[i + 1] = g
                    px[i + 2] = b
                    px[i + 3] = 255

    def rgba(self):
        """盒式降采样到目标尺寸；透明像素不参与颜色平均，避免黑边。"""
        W, S = self.w, self.size
        px = self.px
        out = bytearray(S * S * 4)
        total = SS * SS
        for y in range(S):
            for x in range(S):
                rs = gs = bs = 0
                cover = 0
                for dy in range(SS):
                    base = ((y * SS + dy) * W + x * SS) * 4
                    for dx in range(SS):
                        i = base + dx * 4
                        if px[i + 3]:
                            rs += px[i]
                            gs += px[i + 1]
                            bs += px[i + 2]
                            cover += 1
                o = (y * S + x) * 4
                if cover:
                    out[o] = rs // cover
                    out[o + 1] = gs // cover
                    out[o + 2] = bs // cover
                out[o + 3] = int(round(255.0 * cover / total))
        return bytes(out)


# --------------------------------------------------------------------------- #
# 图形：一本合着的书（封面 + 书脊 + 三条字行 + 金色书签）
# --------------------------------------------------------------------------- #
def draw_icon(size, maskable=False, square=False, simple=False):
    c = Canvas(size)

    if maskable:
        c.paint(rrect(0.0, 0.0, 1.0, 1.0, 0.0), BG)
        bx0, by0, bx1, by1 = 0.22, 0.22, 0.78, 0.78
    elif square:
        c.paint(rrect(0.0, 0.0, 1.0, 1.0, 0.0), BG)
        bx0, by0, bx1, by1 = 0.20, 0.21, 0.80, 0.79
    else:
        c.paint(rrect(0.0, 0.0, 1.0, 1.0, 0.225), BG)
        bx0, by0, bx1, by1 = 0.175, 0.19, 0.825, 0.81

    w = bx1 - bx0
    h = by1 - by0

    # 封面
    c.paint(rrect(bx0, by0, bx1, by1, 0.06 * w), INK)
    # 书脊：靠左一条压深的竖带（内缩，避免顶到圆角）
    c.paint(rrect(bx0 + 0.055 * w, by0 + 0.075 * h,
                  bx0 + 0.195 * w, by1 - 0.075 * h, 0.05 * w), INK2)

    # 字行
    lx0 = bx0 + 0.30 * w
    lx1 = bx1 - 0.34 * w
    if simple:
        rows = [(0.28, 0.145), (0.57, 0.145)]
    else:
        rows = [(0.185, 0.085), (0.385, 0.085), (0.585, 0.085)]
    for top, lh in rows:
        c.paint(rrect(lx0, by0 + top * h, lx1, by0 + (top + lh) * h,
                      lh * h / 2.0), CARD)

    # 金色书签（从封面顶部垂下，底部开 V 口）
    rx0 = bx1 - 0.30 * w
    rx1 = bx1 - 0.10 * w
    ry0 = by0
    ry1 = by0 + 0.38 * h
    notch = (ry1 - ry0) * 0.30
    pts = [(rx0, ry0), (rx1, ry0), (rx1, ry1),
           ((rx0 + rx1) / 2.0, ry1 - notch), (rx0, ry1)]
    c.paint(poly(pts), GOLD, bbox_of(pts))

    return c.rgba()


# --------------------------------------------------------------------------- #
# PNG 写出 / 读取
# --------------------------------------------------------------------------- #
def write_png(path, size, rgba):
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)  # filter type 0
        raw.extend(rgba[y * stride:(y + 1) * stride])

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data +
                struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
           chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', head[16:24])


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
TARGETS = [
    ('icon-192.png', 192, dict()),
    ('icon-512.png', 512, dict()),
    ('maskable-512.png', 512, dict(maskable=True)),
    ('apple-touch-icon.png', 180, dict(square=True)),
    ('favicon-32.png', 32, dict(simple=True)),
]


def check():
    bad = 0
    for name, size, _ in TARGETS:
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            print('  ✗ %-22s 缺失' % name)
            bad += 1
            continue
        got = png_size(path)
        ok = got == (size, size)
        print('  %s %-22s 期望 %dx%d  实际 %s' % (
            '✓' if ok else '✗', name, size, size,
            '%dx%d' % got if got else '不是 PNG'))
        if not ok:
            bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser(description='生成词书 PWA 图标（纯标准库）')
    ap.add_argument('--check', action='store_true', help='只校验现有 PNG 尺寸')
    args = ap.parse_args()

    if args.check:
        bad = check()
        print('图标校验：%s' % ('全部正确' if not bad else '%d 个有问题' % bad))
        return 1 if bad else 0

    for name, size, opts in TARGETS:
        path = os.path.join(HERE, name)
        write_png(path, size, draw_icon(size, **opts))
        print('  ✓ %-22s %3dx%-3d %6d B' % (name, size, size, os.path.getsize(path)))

    bad = check()
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
