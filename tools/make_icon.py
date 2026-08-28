"""生成 app.ico（纯 Python，无需 PIL/Qt）：64x64 RGBA 图标 + PNG 压缩的 ICO 封装。

图形：深蓝圆角底 + 橙色圆环 + 中心圆点，模拟 CS 风格准星。
"""

import os
import struct
import zlib

SIZE = 64
RADIUS = 14


def png_chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data +
            struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))


def encode_png(w, h, get_pixel):
    rows = []
    for y in range(h):
        row = bytearray([0])  # filter type 0
        for x in range(w):
            r, g, b, a = get_pixel(x, y)
            row += bytes((r, g, b, a))
        rows.append(bytes(row))
    raw = b''.join(rows)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw, 9)
    return (b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', ihdr) +
            png_chunk(b'IDAT', idat) + png_chunk(b'IEND', b''))


def _inside_rounded(x, y):
    r = RADIUS
    if x < r and y < r:
        return (x - r + 0.5) ** 2 + (y - r + 0.5) ** 2 <= r * r
    if x >= SIZE - r and y < r:
        return (x - (SIZE - r) + 0.5) ** 2 + (y - r + 0.5) ** 2 <= r * r
    if x < r and y >= SIZE - r:
        return (x - r + 0.5) ** 2 + (y - (SIZE - r) + 0.5) ** 2 <= r * r
    if x >= SIZE - r and y >= SIZE - r:
        return (x - (SIZE - r) + 0.5) ** 2 + (y - (SIZE - r) + 0.5) ** 2 <= r * r
    return True


def make_icon():
    cx = cy = SIZE / 2.0
    ring_r = SIZE * 0.30
    ring_t = SIZE * 0.085
    inner_r = SIZE * 0.09
    hl_r = 5.0
    hl_cx, hl_cy = SIZE * 0.24, SIZE * 0.22

    def px(x, y):
        fx, fy = x + 0.5, y + 0.5
        if not _inside_rounded(fx, fy):
            return (0, 0, 0, 0)
        t = y / SIZE
        base = (int(23 + t * 12), int(40 + t * 16), int(56 + t * 20))
        dx, dy = fx - cx, fy - cy
        dist = (dx * dx + dy * dy) ** 0.5
        if abs(dist - ring_r) <= ring_t:
            return (247, 147, 26, 255)
        if dist <= inner_r:
            return (247, 147, 26, 255)
        if (fx - hl_cx) ** 2 + (fy - hl_cy) ** 2 <= hl_r ** 2:
            return (255, 255, 255, 70)
        return (base[0], base[1], base[2], 255)

    png = encode_png(SIZE, SIZE, px)
    header = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHII', 64, 64, 0, 0, 1, 32, len(png), 22)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.ico')
    with open(out, 'wb') as f:
        f.write(header + entry + png)
    print('written:', out)


if __name__ == '__main__':
    make_icon()
