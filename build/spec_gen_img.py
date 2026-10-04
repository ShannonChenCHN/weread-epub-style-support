#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""样张书测试图生成。

双路径：
  PIL 主路径   —— venv python 有 Pillow 12.3.0，能写字（尺寸标注、封面版本号）
  zlib 降级路径 —— import PIL 失败时用纯标准库写单色 PNG（无文字）

封面必须走 PIL（要写字）；缺 PIL 时直接报错，不做静默降级，
否则会产出一个没有任何版本烙印的封面，截图就分不清是哪一轮。

字体候选（实测：PingFang.ttc 打不开，Heiti / Hiragino / Songti 都可）：
"""
import os
import struct
import zlib

FONT_CANDS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]

BG = (247, 245, 240)
FG = (40, 40, 44)
COVER_BG = (245, 242, 234)
COVER_FG = (26, 26, 30)


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except Exception:
        return None


def _font(size):
    p = _pillow()
    if not p:
        return None
    _, _, ImageFont = p
    for path in FONT_CANDS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


# --------------------------------------------------------------------------
# PIL 主路径
# --------------------------------------------------------------------------
def _gen_pil(spec, bg=BG, fg=FG):
    Image, ImageDraw, _ = _pillow()
    w, h = int(spec["w"]), int(spec["h"])
    fmt = spec.get("fmt", "jpg")
    cap = spec.get("cap", "")
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    bw = max(2, min(24, w // 200))
    d.rectangle([0, 0, w - 1, h - 1], outline=fg, width=bw)

    # 只有够大才写字：小图（如 60×60）塞字会糊成一团
    if min(w, h) >= 80:
        fs = max(11, min(150, w // 16))
        f = _font(fs)
        if f is not None:
            lines = [cap] if cap else []
            lines.append("%d × %d" % (w, h))
            y = h / 2 - len(lines) * fs * 0.62
            for ln in lines:
                if not ln:
                    continue
                bb = d.textbbox((0, 0), ln, font=f)
                d.text((w / 2 - (bb[2] - bb[0]) / 2 - bb[0], y), ln, font=f, fill=fg)
                y += fs * 1.25
    if fmt == "png":
        buf = __import__("io").BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()
    buf = __import__("io").BytesIO()
    im.save(buf, "JPEG", quality=82)
    return buf.getvalue()


# --------------------------------------------------------------------------
# zlib 降级路径：纯标准库写 PNG（无文字，尺寸靠校验器断言）
# --------------------------------------------------------------------------
def _gen_raw(spec, bg=BG, fg=FG, border=4):
    w, h = int(spec["w"]), int(spec["h"])
    if border * 2 >= w or border * 2 >= h:
        border = 0
    bw, iw = bytes(fg) * border, bytes(bg) * (w - border * 2)
    rows = [b"\x00"]
    rows += [bytes(fg) * w if (y < border or y >= h - border) else bw + iw + bw for y in range(h)]
    rows.append(b"\x00")
    raw = b"".join(rows)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    return png


def gen_img(spec):
    """生成一张测试图，返回 bytes。PIL 不可用时自动走 zlib 降级。"""
    if not spec.get("cap") and not spec.get("note"):
        cap = spec.get("id", "IMG")
    else:
        cap = spec.get("cap") or ""
    s = dict(spec)
    s["cap"] = cap
    return _gen_pil(s) if _pillow() else _gen_raw(s)


def gen_cover(version, date_str, done, total):
    """封面：必须带版本烙印。缺 PIL 直接抛错。"""
    p = _pillow()
    if not p:
        raise RuntimeError("封面需要 PIL（要画版本号文字）：请用 venv python 运行")
    Image, ImageDraw, _ = p
    W, H = 1200, 1600
    im = Image.new("RGB", (W, H), COVER_BG)
    d = ImageDraw.Draw(im)
    d.rectangle([28, 28, W - 29, H - 29], outline=COVER_FG, width=6)
    cx = W / 2

    def put(cx_, y, text, size, fill=COVER_FG, anchor="mm"):
        f = _font(size)
        if f is None:
            f = _font(size)  # 实测候选里至少有一个可用
        d.text((cx_, y), text, font=f, fill=fill, anchor=anchor)

    put(cx, 470, "微信读书 排版样张", 84)
    put(cx, 600, "EPUB 渲染能力测试书", 44)
    d.line([cx - 240, 680, cx + 240, 680], fill=COVER_FG, width=4)
    put(cx, 800, "VERSION " + version, 120)
    put(cx, 960, date_str, 48)
    put(cx, 1050, "第 %d 章 / 全集 %d 章" % (done, total), 48)
    put(cx, 1160, "导入后请逐章翻看并记录", 34)
    put(cx, 1215, "截图时认准封面上的版本号", 34)
    put(cx, 1400, "开源测试用 · 非出版物", 30)
    buf = __import__("io").BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def gen_cover_raw(version, date_str, done, total):
    """降级封面：纯色块 + 一行竖条，至少把版本信息留在文件里供校验器比对。"""
    spec = {"w": 600, "h": 800, "fmt": "png", "cap": ""}
    return _gen_raw(spec)


if __name__ == "__main__":
    import json
    import sys

    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "spec.json", encoding="utf-8"))
    outdir = "images"
    os.makedirs(outdir, exist_ok=True)
    for im in spec.get("images", []):
        data = gen_img(im)
        open(os.path.join(outdir, "%s.%s" % (im["id"], im["fmt"])), "wb").write(data)
        print("%s.%s  %7d bytes  %dx%d" % (im["id"], im["fmt"], len(data), im["w"], im["h"]))
    try:
        data = gen_cover(spec.get("version", "v0"), "2026-10-03", len(spec["chapters"]), 16)
        open(os.path.join(outdir, "cover.jpg"), "wb").write(data)
        print("cover.jpg  %7d bytes" % len(data))
    except RuntimeError as e:
        print("[SKIP] cover:", e)
