#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""样张书专用校验器（独立于任何成品流水线）。

搬 70_validate.py 已验证有效的 [1][2][3][4][5][7]，替换掉与样张书无关的 [6][8]，
新增 4 条样张专属断言：
  [6] 探针编号自检（与 spec.json 双向完全相等）
  [7] spine 顺序快照（一章一文件是本方案的地基）
  [8] 图片真实尺寸断言（从 PNG/JPEG 头解析，证明测的是我以为的那张图）
  [9] 每章恰好一个 h1 且在 body 首个子元素、单文件 < 40KB

用法：python3 spec_validate.py --epub ../epub/weread-epub-style-specimen-1.0.epub
"""
import json
import os
import posixpath
import re
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

SPEC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SPEC_DIR)          # 仓库根目录

FAILED = []
WARNED = []


def check(cond, msg):
    if cond:
        print("  [OK]   %s" % msg)
    else:
        print("  [FAIL] %s" % msg)
        FAILED.append(msg)


def soft(cond, msg):
    if cond:
        print("  [OK]   %s" % msg)
    else:
        print("  [WARN] %s" % msg)
        WARNED.append(msg)


# ---------------------------------------------------------------- 图片头解析
def img_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            ln = struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return int(w), int(h)
            i += 2 + ln
    return None


def main():
    epub = sys.argv[sys.argv.index("--epub") + 1] if "--epub" in sys.argv else None
    spec = json.load(open(os.path.join(SPEC_DIR, "spec.json"), encoding="utf-8"))
    z = zipfile.ZipFile(epub)
    names = z.namelist()

    print("\n[1] 结构与完整性")
    check(len(names) > 0, "文件数 = %d" % len(names))
    check(z.testzip() is None, "zip 完整性 (testzip)")
    infos = z.infolist()
    check(infos[0].filename == "mimetype", "第一个 entry 是 mimetype（实际 %s）" % infos[0].filename)
    check(infos[0].compress_type == zipfile.ZIP_STORED,
          "mimetype 未压缩（compress_type=%d）" % infos[0].compress_type)
    check(z.read("mimetype") == b"application/epub+zip", "mimetype 内容正确")

    print("\n[2] XML well-formed")
    for n in names:
        if re.search(r"\.(xhtml|opf|ncx|xml)$", n):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                check(False, "%s 解析失败: %s" % (n, e))
    soft(not FAILED, "全部 XML 可解析（[FAIL] 上面若出现即为不通过）")

    print("\n[3] href 死链")
    # (基准目录, href)：opf 与 nav.xhtml 的 href 相对 OEBPS/；正文 xhtml 相对自身目录
    refs = []
    for n in names:
        if n.endswith(".opf"):
            for h in re.findall(r'href="([^"]+)"', z.read(n).decode("utf-8")):
                refs.append(("OEBPS", h))
    for n in names:
        if n.endswith("nav.xhtml"):
            for h in re.findall(r'<a href="([^"]+)"', z.read(n).decode("utf-8")):
                refs.append(("OEBPS", h))
    for n in names:
        if n.endswith(".xhtml") and not n.endswith("nav.xhtml"):
            s = z.read(n).decode("utf-8")
            base = posixpath.dirname(n)
            for h in re.findall(r'<img[^>]*\ssrc="([^"]+)"', s):
                refs.append((base, h))
            for h in re.findall(r'<link[^>]*\shref="([^"]+)"', s):
                refs.append((base, h))
    bad = []
    for base, h in refs:
        tgt = posixpath.normpath(posixpath.join(base, h))
        if tgt not in names:
            bad.append((h, tgt))
    check(not bad, "所有 href 都有对应文件（缺失: %s）" % (bad or "无"))

    print("\n[4] 图片注册一致（manifest 集合 = 正文引用集合）")
    opf = z.read("OEBPS/content.opf").decode("utf-8")
    man_imgs = set(re.findall(r'<item[^>]*href="images/([^"]+)"', opf))
    used = set()
    for n in names:
        if n.endswith(".xhtml"):
            used |= {posixpath.basename(s) for s in
                     re.findall(r'<img[^>]*\ssrc="([^"]+)"', z.read(n).decode("utf-8"))}
    check(not (used - man_imgs), "所有被引用的图都已在 manifest 注册（漏: %s）" % (used - man_imgs or "无"))
    check(not (man_imgs - used), "manifest 里的图都被引用（多余: %s）" % (man_imgs - used or "无"))

    print("\n[5] 文本质量")
    joined = "".join(n for n in names if n.endswith(".xhtml"))
    total = "".join(z.read(n).decode("utf-8", "ignore") for n in names if n.endswith(".xhtml"))
    check("&amp;quot;" not in total, "无 &amp;quot; 双重转义残留")
    check(total.count("“") == total.count("”"),
          "“ 与 ” 配平（%d vs %d）" % (total.count("“"), total.count("”")))
    han = len(re.findall(r"[一-鿿]", total))
    print("  [info] 汉字 %d 个, 总字符 %d, 汉字占比 %.1f%%" % (han, len(total), 100.0 * han / max(1, len(total))))
    soft(han > 3000, "样本字数足够（当前 %d）" % han)

    print("\n[6] 探针编号自检（vs spec.json）")
    # 编号不只出现在顶层 t 里：分组 HTML 内部也会带子编号（如 T12.4 容器里含 T12.5/T12.6）
    want = []
    for ch in spec["chapters"]:
        for pr in ch.get("probes") or []:
            want += re.findall(r"T\d{2}\.\d{1,2}(?!\d)", json.dumps(pr, ensure_ascii=False))
    got = []
    for n in names:
        # 只数章节文件：guide.xhtml 里的两张清单表会把每个编号再算一遍
        if re.match(r"OEBPS/text/p\d+\.xhtml$", n):
            got += re.findall(r"T\d{2}\.\d{1,2}(?!\d)", z.read(n).decode("utf-8"))
    want_set = set(want)
    check(want_set <= set(got), "spec.json 声明的探针都出现在正文（缺: %s）" % (want_set - set(got) or "无"))
    check(set(got) <= want_set, "正文没有 spec.json 之外的探针（多: %s）" % (set(got) - want_set or "无"))
    # 探针按设计双写（p/raw 类写两遍看区间重挂），出现两次以上才是真的写错了
    over = {t: got.count(t) for t in set(got) if got.count(t) > 2}
    check(not over, "没有探针编号写了两遍以上（异常: %s）" % (over or "无"))
    print("  [info] 声明探针 %d，正文出现 %d 次（双写探针 %d 个）"
          % (len(want), len(got), len({t for t in got if got.count(t) == 2})))

    # 探针自身的 HTML 必须能独立解析（上一轮就是靠这条抓到块级标签没闭合）
    bad_html = []
    for ch in spec["chapters"]:
        for pr in ch.get("probes") or []:
            if pr.get("k") in ("raw", "one") and pr.get("h"):
                try:
                    # 探针片段会被单独解析，epub 前缀得就地声明，
                    # 否则整页里合法的 epub:type 在这里会误报 unbound prefix
                    ET.fromstring('<div xmlns:epub="http://www.idpf.org/2007/ops">%s</div>'
                                  % pr["h"])
                except ET.ParseError as e:
                    bad_html.append((pr["t"], str(e)))
    check(not bad_html, "所有 raw/one 探针的 HTML 标签闭合（错误: %s）" % (bad_html or "无"))

    print("\n[7] spine 顺序快照")
    spine_ids = re.findall(r'<itemref idref="([^"]+)"/>', opf)
    expect = ["cover", "title", "guide"] + ["p%02d" % i for i in range(1, len(spec["chapters"]) + 1)]
    expect.append("nostyle")
    check(spine_ids == expect, "spine 顺序 == 声明顺序（实际 %s）" % spine_ids)
    for must in ("nav", "ncx", "css"):
        check(must not in spine_ids, "%s 不在 spine 里" % must)
    check(len(spine_ids) == len(expect),
          "正文文件数 == spine 数（%d）" % len(spine_ids))

    print("\n[8] 图片真实尺寸断言")
    imgs = {im["id"]: im for im in spec.get("images", [])}
    for im in spec.get("images", []):
        key = "OEBPS/images/%s.%s" % (im["id"], im["fmt"])
        if key not in names:
            check(False, "%s 不在包里" % key)
            continue
        got_sz = img_size(z.read(key))
        check(got_sz == (int(im["w"]), int(im["h"])),
              "%s 真实尺寸 %s == 声明 %dx%d" % (im["id"], got_sz, im["w"], im["h"]))
    cover = "OEBPS/images/cover.jpg"
    if cover in names:
        print("  [info] cover.jpg %d bytes, %s" % (z.getinfo(cover).file_size, img_size(z.read(cover))))

    print("\n[9] 章节结构（h1 锚点 + 单文件体积）")
    for i, ch in enumerate(spec["chapters"], 1):
        name = "OEBPS/text/p%02d.xhtml" % i
        if name not in names:
            check(False, "%s 缺失" % name)
            continue
        root = ET.fromstring(z.read(name))
        body = root.find("{%s}body" % "http://www.w3.org/1999/xhtml")
        kids = list(body) if body is not None else []
        h1s = [k for k in kids if k.tag.endswith("h1")]
        check(len(h1s) == 1, "%s 恰好一个 h1（实际 %d）" % (name, len(h1s)))
        check(bool(kids) and kids[0].tag.endswith("h1"),
              "%s 的 h1 是 body 首个子元素" % name)
        sz = z.getinfo(name).file_size
        check(sz < 40960, "%s 单文件 %d bytes < 40KB" % (name, sz))

    v = spec.get("version", "v0")
    print("\n[10] 回填表（report_%s.md）" % v)
    OUT_DIR = os.environ.get("SPEC_OUT_DIR") or os.path.join(BASE, "epub")
    want_ids = sorted(ch["id"] for ch in spec["chapters"])
    md_ids, filled_n = [], 0
    for p in (os.path.join(OUT_DIR, "report_%s.md" % v),
              os.path.join(OUT_DIR, "report_%s_filled.md" % v)):
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("|") or len(line) < 8:
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 6 or not cells[0].startswith("P"):
                    continue
                if cells[0] not in md_ids:
                    md_ids.append(cells[0])
                if cells[5].replace("　", "").strip():
                    filled_n += 1
    if not md_ids:
        soft(False, "report_%s.md 未生成或主表为空（可选：spec_build.py --report）" % v)
    else:
        # 主表章 id 必须和 spec 对齐，否则手填的实测会落错行
        check(sorted(md_ids) == want_ids,
              "report 主表章 id 与 spec.json 一致（report %s / spec %s）" % (sorted(md_ids), want_ids))
    print("  [info] 主表已填 %d 条（还没开测就是 0，属正常）" % filled_n)

    print("\n[12] 每章规模上限（防后台二次切分把探针劈到两页）")
    over_ch = []
    for i, ch in enumerate(spec["chapters"], 1):
        nm = "OEBPS/text/p%02d.xhtml" % i
        if nm not in names:
            continue
        s = z.read(nm).decode("utf-8")
        nchar = len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", s)))
        npr = len(ch.get("probes") or [])
        if nchar > 2500 or npr > 40:
            over_ch.append("%s=%d字/%d块" % (ch["id"], nchar, npr))
    check(not over_ch, "每章 ≤2500 字且 ≤40 探针块（越界: %s）" % (over_ch or "无"))

    print("\n[13] KEY_PROBES 完整性（缺一条会让 guide 表与 report 主表那格显示「—」）")
    _KP = None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from spec_build import KEY_PROBES as _KP
    except Exception as e:            # 不该发生；发生了说明断言失去了意义
        check(False, "无法 import spec_build.KEY_PROBES（%s）—— 本项无法验证" % e)
    if _KP:
        chk_ids = {c["id"] for c in spec["chapters"]}
        miss = [c["id"] for c in spec["chapters"] if c["id"] not in _KP]
        check(not miss, "每章都有 KEY_PROBES 条目（缺: %s）" % (miss or "无"))
        extra = [k for k in _KP if k not in chk_ids]
        check(not extra, "没有多余的 KEY_PROBES 条目（多: %s）" % (extra or "无"))
        print("  [info] 章节 %d 条 / KEY_PROBES %d 条"
              % (len(chk_ids), len(_KP)))

    print("\n[11] 体积")
    tot = os.path.getsize(epub)
    check(tot < 400 * 1024, "体积 < 400KB（实际 %.2f KB）" % (tot / 1024.0))
    print("  [info] %d bytes (%.2f KB / %.2f MB)" % (tot, tot / 1024.0, tot / 1e6))
    ext = {}
    for n in names:
        ext[n.rsplit(".", 1)[-1]] = ext.get(n.rsplit(".", 1)[-1], 0) + z.getinfo(n).file_size
    for k in sorted(ext):
        print("    .%-10s %8d" % (k, ext[k]))

    print("\n==== FAIL %d, WARN %d ====" % (len(FAILED), len(WARNED)))
    for m in FAILED:
        print("  FAIL: %s" % m)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
