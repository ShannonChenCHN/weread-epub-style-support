#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""样张书 EPUB 组装（自包含，不依赖外部流水线）。

样张书的三个纯函数（xhtml / nav_ol / ncx_points）与打包写法（mimetype 首 entry
+ ZIP_STORED）刻意各留一份、不做共享复用：样张书是长期测试基准，不能挂在被测
代码上，否则主流水线改模板时基线会漂移，已填的实测结论就会对不上。

用法：
  python3 spec_build.py                 # 版本取 spec.json 的 version
  python3 spec_build.py --version 1.0   # 指定版本，输出到 <repo>/epub/
  SPEC_OUT_DIR=/tmp/out python3 spec_build.py   # 自定义输出目录
"""
import datetime
import html
import json
import os
import sys
import uuid
import zipfile
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_gen_img import gen_img, gen_cover  # noqa: E402

SPEC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SPEC_DIR)                                    # 仓库根目录
OUT_DIR = os.environ.get("SPEC_OUT_DIR") or os.path.join(BASE, "epub")
TOTAL_CH = 17

esc = html.escape
DATE = datetime.datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------- xhtml / nav
def xhtml(title, body_html, cls="", no_css=False):
    """单文件 XHTML 包装；no_css=True 用于无样式基准页。"""
    link = "" if no_css else '<link rel="stylesheet" type="text/css" href="../style.css"/>'
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"\n'
        '      xml:lang="zh-CN" lang="zh-CN">\n'
        '<head><meta charset="utf-8"/><title>%s</title>%s</head>\n'
        '<body%s>%s</body>\n</html>\n' % (esc(title), link, cls, body_html)
    )


def nav_ol(items):
    """把 (深度, 标题, 路径) 列表渲染成扁平 nav 列表。"""
    parts = ["<ol>"]
    for lv, t, href in items:
        parts.append('<li><a href="%s">%s</a></li>' % (href, esc(t)))
    parts.append("</ol>")
    return "".join(parts)


def ncx_points(items, base=1):
    """渲染 toc.ncx 的 navPoint；返回 (navPoint 串, 计数)。"""
    pts, order = [], base
    for lv, t, href in items:
        pts.append(
            '<navPoint id="np%d" playOrder="%d">'
            '<navLabel><text>%s</text></navLabel>'
            '<content src="%s"/></navPoint>' % (order, order, esc(t), href)
        )
        order += 1
    return "".join(pts), order - 1


CSS = """@charset "utf-8";
body { line-height: 1.7; margin: 0 0.6em; font-size: 1em; color: #1a1a1a; }
h1 { text-align: center; font-size: 1.7em; margin: 2.4em 0 1.5em; font-weight: normal; letter-spacing: .06em; }
h2 { font-size: 1.2em; margin: 1.9em 0 .9em; font-weight: bold; }
h3 { font-size: 1.05em; margin: 1.5em 0 .7em; font-weight: bold; }
h4 { font-size: 1em; margin: 1.2em 0 .6em; font-weight: bold; }
p { margin: 0 0 .35em; text-indent: 2em; text-align: justify; }
.px-ind { text-indent: 2em; background: #fff6c0; }
.px-flat { text-indent: 0; background: #d8f5d8; }
.lead { text-indent: 0; color: #333; background: #eef4fb; padding: .5em .7em; margin: 0 0 1.2em; }
.ch-why { text-indent: 0; font-size: .8em; color: #555; margin: 0 0 1.4em; }
.psea { text-indent: 0; background: #d0d0d0; color: #333; font-size: .78em;
        text-align: center; margin: .3em 0 1em; }
.chapter-tail { text-indent: 0; background: #ffd9e8; text-align: center;
        font-size: .78em; margin: 2.2em 0 .4em; }
/* 引文三版：结构等价，唯一变量是选择器形态 */
.bq-flat { margin: 1em 2em; padding-left: 1em; border-left: 3px solid #999; color: #444; font-size: .92em; }
.bq-noline { margin: 1em 2em; padding-left: 1em; color: #444; font-size: .92em; }
.bq-box { margin: 1em 2em; }
.bq-box .bq-in { padding-left: 1em; }
.bq-box .bq-in .bq-t { color: #444; font-size: .92em; margin: 0 0 .35em; }
/* 图片 */
figure { text-align: center; margin: 1.4em 0; }
figure img { max-width: 100%; height: auto; }
figcaption { text-indent: 0; font-size: .8em; color: #555; margin-top: .4em; }
.fl-a { float: left; margin: .4em; max-width: 40%; }
.clr { clear: both; }
/* 表格 */
.tbl { width: 100%; border-collapse: collapse; text-indent: 0; text-align: left; font-size: .8em; margin: 1em 0; }
.tb { border: 1px solid #999; padding: .3em; vertical-align: top; }
caption { text-indent: 0; font-size: .82em; color: #555; padding-bottom: .4em; text-align: left; }
.cd { font-family: monospace; font-size: .9em; }
/* 等宽与列表 */
.pre-blk { white-space: pre-wrap; font-family: monospace; background: #f4f4f4; padding: .5em;
        text-indent: 0; margin: 1em 0; font-size: .85em; }
.lst { margin: 1em 0; text-indent: 0; }
.lst li { margin: .2em 0; }
/* 选择器能力台 A/B */
.ab-flat { color: #c00; font-size: 1.5em; margin-left: 1em; }
.ab2 .ab-x { color: #c00; font-size: 1.5em; margin-left: 1em; }
.ab-letter::first-letter { font-size: 2.4em; color: #06c; }
.ab-odd p { text-indent: 0; margin: 0; }
.ab-odd p:nth-child(odd) { background: #e6e6e6; }
.ab-narrow { font-size: .8em; }
@supports (display: grid) { .ab-sup { display: grid; grid-template-columns: 2fr 1fr; } }
.ab-sup-a { background: #e8f0e8; }
.ab-sup-b { background: #f0e8f0; }
/* 危险元素台 */
.fx-a { display: flex; }
.fx-i { background: #eee; margin: .2em; }
.grid-a { display: grid; grid-template-columns: 2fr 1fr; }
.grid-i { background: #ececec; }
.abs-a { position: absolute; top: 0; right: 0; }
.rot-a { transform: rotate(-3deg); }
.shd-a { text-shadow: 1px 1px 0 #999; }
.bsh-a { box-shadow: 0 0 6px #666; margin: .8em; }
.grad-a { background: linear-gradient(#ffffff, #eeeeee); }
.col-a { column-count: 2; }
.vert-a { writing-mode: vertical-rl; }
/* 封面 / 书名页 */
.cover { text-align: center; margin: 0; padding: 0; }
.cover img { max-width: 100%; max-height: 100%; }
.titlepage { text-align: center; margin-top: 20%; }
.titlepage p { text-indent: 0; }
.tp-h { font-size: 1.6em; font-weight: bold; margin: 0 0 .6em; }
.tp-s { color: #555; margin: 0 0 2em; }
.tp-m { font-size: .9em; color: #666; }
/* ---- 常用样式扩充 ---- */
/* P02 分割线 / 上下标 */
.hr-a { border: 0; border-top: 1px solid #999; margin: 1.6em 0; }
.hr-b { border-top: 2px dashed #06c; text-align: center; padding-top: .4em; margin: 1.6em 0; }
.spu { vertical-align: super; font-size: .7em; color: #06c; }
.spd { vertical-align: sub; font-size: .7em; color: #c06; }
/* P03 标题层级 */
.h2a { text-align: center; letter-spacing: .3em; }
.h3a { letter-spacing: .1em; font-weight: normal; }
.h4a { font-weight: normal; color: #555; }
.tts { color: #c00; }
/* P04 列表 */
.ul-a { margin: 1em 0 1em 1.4em; text-indent: 0; }
.ul-b { list-style: none; margin-left: 1.4em; text-indent: 0; }
.ol-cn { list-style-type: cjk-ideographic; margin-left: 1.6em; text-indent: 0; }
.li-i { padding-left: 1em; text-indent: -1em; }
/* P08 居中 */
.ctr { text-align: center; }
/* P10 等宽与代码 */
.pre-a { white-space: pre-wrap; font-family: monospace; background: #f4f4f4; padding: .6em;
        text-indent: 0; margin: 1em 0; font-size: .85em; line-height: 1.45; }
.code-a { font-family: monospace; background: #eee; padding: 0 .2em; }
.lw-a { word-break: break-all; }
/* P11 行高与字距 */
.lh-a { line-height: 1.2; }
.lh-b { line-height: 2.4; }
.ls-a { letter-spacing: .25em; }
/* P13 分页 */
.pb-a { page-break-after: always; break-after: page; }
.bi-a { break-inside: avoid; }
/* P14 注释 */
.fn-a { font-size: .8em; color: #555; margin-top: .3em; }
/* 章末注：正文角标 + 章末注释本体（实测：角标点击不跳转） */
.noteref { color: #06c; text-decoration: none; }
.fn-h { text-indent: 0; font-size: .88em; color: #777; border-top: 1px solid #ddd;
        margin: 2.2em 0 .7em; padding-top: .7em; }
.fn-item { text-indent: 0; font-size: .8em; color: #555; margin: 0 0 .5em; }
.fn-back { color: #06c; text-decoration: none; }
/* P15 字体与单位 */
.ff-a { font-family: "PingFang SC", "Songti SC", serif; }
.u-px { font-size: 16px; }
.u-em { font-size: 1.5em; }
.u-rem { font-size: 1.5rem; }
.u-per { font-size: 150%; }
.u-pt { font-size: 12pt; }
/* P16 危险台代表 + 清单 */
.danger-list { text-indent: 0; font-size: .82em; color: #555;
               border-left: 3px solid #ddd; padding-left: 1em; margin: 1em 0; }
/* @media：真正的媒体查询包裹（对照裸规则用） */
@media (max-width: 360px) { .ab-narrow { font-size: .8em; } }
/* P17 字体族：全部扁平单类名，只动 font-family/color */
.ff-hykt { font-family: "汉仪楷体S"; }
.ff-hyqh { font-family: "汉仪旗黑 50S"; }
.ff-kaiti { font-family: "Kaiti SC", "STKaiti", KaiTi, serif; }
.ff-serif { font-family: serif; }
.ff-songti { font-family: "Songti SC", SimSun, serif; }
.ff-quote-replica { font-family: "汉仪楷体S","ETrump KaiTi","方正仿宋","FZFSJW--GB1-0","PingFang SC",-apple-system,"SF UI Text","Lucida Grande",STheiti,"Microsoft YaHei",sans-serif; color: brown; }
"""


# ---------------------------------------------------------------- 章节渲染
SENTINEL = '<p class="psea">◆ SENTINEL ◆ 应保持灰底</p>'


def fig_html(pr, imgs):
    im = imgs[pr["img"]]
    attrs = pr.get("attrs") or ""
    cap = pr.get("cap") or im.get("cap") or ""
    # 编号带进 figcaption：截图时能直接搜 T06.3 定位到这张图
    cap = "%s %s" % (pr["t"], cap)
    s = '<figure><img src="../images/%s.%s" alt="%s" %s/>' % (
        im["id"], im["fmt"], esc(cap), attrs)
    s += "<figcaption>%s</figcaption></figure>" % esc(cap)
    return s


def render_chapter(ch):
    parts = ["<h1>%s</h1>" % esc(ch["h1"])]
    if ch.get("why"):
        parts.append('<p class="ch-why">本章为什么存在：%s</p>' % esc(ch["why"]))
    for pr in ch.get("probes") or []:
        k = pr.get("k")
        if k == "p":
            body = esc(pr["t"]) + " " + esc(pr.get("s") or "")
            cls = esc(pr.get("c") or "")
            parts.append('<p class="%s">%s</p>' % (cls, body))
            parts.append('<p class="%s">%s（重复一遍：看区间重挂会不会漂移）</p>' % (cls, body))
        elif k == "fig":
            parts.append(fig_html(pr, CH_IMGS))
        else:
            parts.append(pr["h"])
        parts.append(SENTINEL)
    if ch.get("id"):
        parts.append('<p class="chapter-tail">◆ 章末哨兵 %s ◆</p>' % esc(ch["id"]))
    return "".join(parts)


# 每章最能定性的探针 / 触发条件 / 预期。md 主表与书内清单共用这一份。
# 章级粒度而不是逐探针：用户只填十几行，靠这列指回去做深挖定位。
# 章数随 spec.json 走（当前 17 章），缺一条 guide 表和 report 主表那格就会显示「—」。
KEY_PROBES = {
    "P01": ("T01.1 / T01.2", "App「正文首行缩进」开关 开/关 各一次",
            "缩不缩由 App 全局设置说了算，epub 自带 text-indent 可能被吞"),
    "P02": ("T02.1 vs T02.2", "裸 hr 标签 vs border-top 画出来的线",
            "分割线 / 折叠成空行 / 丢弃，三选一"),
    "P03": ("T03.1 ~ T03.3", "h2 居中 / h3 字距 / h4 字重 三档字号阶梯",
            "字号与字重阶梯是否整条保留"),
    "P04": ("T04.1 / T04.4", "ul 两层嵌套 vs list-style:none",
            "项目符号与层级缩进还在不在"),
    "P05": ("T05.1 vs T05.3", "同一效果分别用扁平类 / 三层嵌套选择器",
            "长得一样则选择器存活；差异大则复杂选择器被削平"),
    "P06": ("T06.1 ~ T06.6", "四张图仅 img 属性写法不同",
            "按版心宽等比缩放且不裁切"),
    "P07": ("T07.1 ~ T07.4", "竖版长图 / 固定高 / 超小 / PNG 四档",
            "极端尺寸与 PNG 通路的边界"),
    "P08": ("T08.2 / T08.3", "float+clear 绕排 vs 整段居中",
            "居中与绕排这两个最朴素手段还活不活"),
    "P09": ("T09.1 ~ T09.4", "简单表 / colspan / 12 列 / 长英文单元格",
            "整表渲染 or 退化 or 横向溢出，三选一"),
    "P10": ("T10.1 / T10.2", "pre 保行首空格 vs 行内 code",
            "空格与等宽是否保住"),
    "P11": ("T11.1 vs T11.2", "line-height 1.2 / 2.4 同文对比",
            "行距档位是否被 App 全局行距覆盖"),
    "P12": ("T12.1 ~ T12.8", "六种选择器形态配等价扁平孪生兄弟",
            "逐条判断哪种选择器形态还活着"),
    "P13": ("T13.1 / T13.2", "page-break-after vs break-inside:avoid",
            "有无分页效果，或确认只有拆文件才硬分页"),
    "P14": ("T14.4 → T14.5", "点正文 [1] 角标 → 跳到章末注释；再点注释 [1] 回跳",
            "同文件双向锚点跳转是否可用（能不能跳到章末）"),
    "P15": ("T15.1 / T15.2", "font-family 三档兜底 vs px/em/rem/%/pt 五档",
            "字体覆盖到哪一层、哪几档单位生效"),
    "P16": ("T16.1 / T16.4", "flex 代表 + 花活清单",
            "圈出黑名单边界；清单本身应完整可读"),
    "P17": ("T17.2 / T17.7", "汉仪楷体S（自家名）vs 系统楷体/serif/宋体 vs 第三方 EPUB 同款栈+棕色",
            "汉仪名显楷体 → App 认自家字体名；全部与基准无差别 → font-family 确认被覆盖"),
}


def _key_probe(cid):
    return KEY_PROBES.get(cid, ("—", "—", "—"))


def render_guide(spec):
    """书内待验证清单：与 report_<version>.md 同构（三行结论 + 每章一行）。
    逐探针明细只留在 md 附录，epub 不放 —— table 本身是高风险元素，
    把书撑成表格书会污染「真 table 能不能用」这条结论本身。"""
    h = ["<h1>使用说明与待验证清单</h1>"]
    h.append('<p class="lead">这本书是用来在微信读书里做真机渲染验证的，不是用来读的。'
             '每一段都带编号（形如 T01.1），翻到那一章可以直接用阅读器的搜索定位。</p>')
    h.append('<p class="ch-why">导入路径：微信读书 App → 底部「书架」→ 右上角「+」'
             '→「从本地导入」→ 授权文件权限 → 选中本 epub。'
             '也可以在网页版 weread.qq.com 用「导入书籍」拖拽上传，进度会同步到手机。'
             '导入后书在「本地导入」分类里。截图时请先认准封面上的版本号，别把两轮的结果混一起。</p>')
    h.append('<p class="ch-why">怎么看：<b>灰底 SENTINEL 段是哨兵</b>。'
             '每个探针后面都跟一个哨兵，正常情况哨兵永远是灰的；'
             '如果哨兵被染成探针的颜色，说明后台做「样式分离」时把样式区间切错了、向右溢出。'
             '每章末尾还有一个粉色章末哨兵，用来看样式会不会串到下一章去。</p>')
    v = spec.get("version", "v0")
    npr = sum(len(ch.get("probes") or []) for ch in spec["chapters"])
    nch = len(spec["chapters"])
    h.append('<p class="ch-why">%s 是全集：常用排版手段 %d 章分头测，'
             '花活类只留代表并附清单，以后遇到具体需求再补。'
             '最值钱的一句话先看 N01 无样式基准页：那一页不引样式表，'
             '把它和各章正文一比，就知道整份 CSS 到底有没有被吃到。</p>' % (esc(v), nch))
    h.append('<h2>本轮要你自己做的两件事</h2>')
    h.append('<p class="ch-why">一、把 App「我 → 设置 → 正文首行缩进」开关<b>开与关各测一次</b>。'
             '这一项是要双跑的：只有开了也缩、关了也缩，才能确认缩进完全由 App 全局设置决定。'
             '看的是 P01 的 T01.1 与 T01.2。除此之外不用整本双跑。</p>')
    h.append('<p class="ch-why">二、把下面这张表每章补一句话（✅ 活 / ❌ 死 / 🟡 半活 + 一句现象）。'
             '填完这份结论就是可复用的了，主流水线直接照这张表定禁用清单。</p>')

    # 主表：章级，一章一行
    h.append('<h2>逐章结论（每章填一行）</h2>')
    h.append('<table class="tbl"><caption>一章一行。「关键探针」列是给你以后按编号深挖用的定位指针；'
             '%d 个探针的逐条明细在书外的 report_%s.md 附录里，这边不摆 —— '
             'table 本身也是被测元素，摆多了会污染「真 table 能不能用」这条结论</caption>'
             % (npr, esc(v))
             + '<thead><tr><th class="tb">章</th><th class="tb">主题</th>'
             '<th class="tb">关键探针</th><th class="tb">触发条件</th>'
             '<th class="tb">预期</th><th class="tb">实测</th></tr></thead><tbody>')
    for ch in spec["chapters"]:
        kp, cond, exp = _key_probe(ch["id"])
        h.append('<tr><td class="tb">%s</td><td class="tb">%s</td><td class="tb">%s</td>'
                 '<td class="tb">%s</td><td class="tb">%s</td><td class="tb">　</td></tr>'
                 % (esc(ch["id"]), esc(ch["h1"]), esc(kp), esc(cond), esc(exp)))
    h.append('</tbody></table>')

    h.append('<h2>逐章备注</h2>')
    for ch in spec["chapters"]:
        h.append("<h3>%s</h3>" % esc(ch["h1"]))
        h.append('<p class="ch-why">为什么存在：%s</p>' % esc(ch.get("why", "—")))
        h.append('<p class="ch-why">◆ 实测观察：</p>')
    h.append('<p class="ch-why">◆ 清单结束 · 下面是一个无样式基准页 ◆</p>')
    h.append('<p class="chapter-tail">◆ 清单结束 · 下面是一个无样式基准页 ◆</p>')
    return "".join(h)


def render_title(spec):
    v = spec.get("version", "v0")
    done = len(spec["chapters"])
    return "".join([
        '<div class="titlepage">',
        '<p class="tp-h">%s</p>' % esc(spec.get("subtitle") or spec.get("title", "")),
        '<p class="tp-s">%s</p>' % esc(spec.get("title", "")),
        '<p class="tp-m">版本 %s　·　%s</p>' % (esc(v), esc(DATE)),
        '<p class="tp-m">本轮 %d 章 / 全集 %d 章</p>' % (done, TOTAL_CH),
        '<p class="tp-m">开源测试用 · 非出版物</p>',
        '<p class="tp-m">用途：把「哪些排版手段在微信读书里还活着」从猜测变成可观测的事实</p>',
        "</div>",
    ])


def render_nostyle():
    return "".join([
        "<h1>N01 无样式基准页</h1>",
        '<p class="ch-why">整本书唯一一个不引用样式表的页面：'
        '这里所有元素的长相都是微信读书自己的默认排版。'
        '把它和前面各章对照，就能判断「我的样式到底有没有被吃」——'
        '如果这一页看起来跟 P01 的正文差不多，说明样式表整体被丢了。</p>',
        "<p>这一段没有任何 class，也不引用样式表，直接看 App 默认怎么排版中文段落。</p>",
        "<p>再来一段，是普通的中文正文，用来和上面那段比一比默认的行距、字号和首行缩进。</p>",
        "<blockquote>这是默认的引用块。</blockquote>",
        "<table class=\"none\"><tr><td>这是默认的表格单元格</td><td>第二格</td></tr></table>",
        "<ul><li>默认项目符号第一项</li><li>默认项目符号第二项</li></ul>",
        "<p>再看一段带 sup 上标 1 和 sub 下标 2 的普通文字，以及一行 <code>code</code> 行内代码。</p>",
    ])


# ---------------------------------------------------------------- 回填模板
def load_filled(path):
    """从旧 report 里扒出主表每章的「实测」单元格，key = 章 id。
    判「已填」：strip 后非空、且不是单个全角空格 `　`。
    只认 cells[0] 以 P 开头的行 —— 探针编号是 T 开头，不会被误读成章 id，
    所以旧的 43 行版 report 会被自然跳过，不会把探针内容灌进章结论里。"""
    filled = {}
    if not os.path.exists(path):
        return filled
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("|") or len(line) < 8:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 6 or not cells[0].startswith("P"):
                continue
            if cells[5].replace("　", "").strip():
                filled[cells[0]] = cells[5]
    return filled


def write_report(spec, rows, path, filled=None):
    """report_<version>.md：三层结构（§0 结论 / §3 主表 / §5 明细附录）。
    filled：从旧 md 继承的已填内容，按章 id 塞回主表 ——
    重建 epub 不该把手填的实测冲成空表。返回「已保留了几条」。"""
    v = spec.get("version", "v0")
    filled = filled or {}
    L = ["# 微信读书 EPUB 排版能力测试样张 %s —— 真机实测回填" % v, "",
         "> 这本书不是用来读的，是用来截图的。填 §0 三行 + §3 每章一句话就够，§5 明细不用填。", "",
         "## 0. 结论（先写这三行 · 唯一决定全局策略的一节）", "",
         "- [ ] 微信读书到底有没有吃到 style.css？（看 N01 无样式基准页 与 P01 正文是否长得一样）",
         "      - 有吃到 → CSS 策略维持扁平 + 复杂 A/B",
         "      - 没吃到 → 全集重写成内联 style 全量兜底", "",
         "- [ ] 哪些元素「活下来了」（列清单）", "",
         "- [ ] 哪些元素「死了」（列清单，直接进主流水线的禁用表）", "",
         "## 1. 导入与操作", "",
         "- 微信读书 App → 底部「书架」→ 右上角「+」→「从本地导入」→ 授权文件权限 → 选中 epub",
         "- 备选：网页版 weread.qq.com「导入书籍」拖拽上传（单次 ≤20 本、≤200MB）",
         "- 备选：微信「文件传输助手」→「从微信导入」",
         "- 导入后书在「本地导入」分类；每章一段都带编号（T01.1 这种），可直接用搜索定位",
         "- **双跑项**：App「我 → 设置 → 正文首行缩进」开关开/关各看一次 P01 的 T01.1 / T01.2", "",
         "## 2. 怎么看一个探针", "",
         "- 灰底 `SENTINEL` 段是哨兵，正常永远是灰的",
         "- 哨兵被染成相邻探针的颜色 → 后台「样式分离」把样式区间切错了、向右溢出",
         "- 每章末尾粉色 `章末哨兵` → 看样式会不会串到下一章",
         "- 同一编号出现两遍（正文里双写）→ 看区间合并时切点是否正确", "",
         "## 3. 逐章结论（主表 · 每章填一行）", "",
         "| 章 | 主题 | 关键探针 | 触发条件 | 预期 | **实测（填这里）** |",
         "| --- | --- | --- | --- | --- | --- |"]
    for ch in spec["chapters"]:
        kp, cond, exp = _key_probe(ch["id"])
        L.append("| %s | %s | %s | %s | %s | %s |"
                 % (ch["id"], ch["h1"], kp, cond, exp, filled.get(ch["id"], "　")))
    L += ["", "## 4. 逐章备注", ""]
    for ch in spec["chapters"]:
        L += ["### %s" % ch["h1"], "",
              "**为什么存在**：%s" % ch.get("why", "—"), "",
              "> 实测观察：", "> ", "> ", ""]
    L += ["---", "",
          "## 5. 探针明细附录（自动生成 · 不用填 · 想按编号深挖再动这里）", "",
          "| 编号 | 元素 | 我的写法 | 触发条件 | 预期 | 等级 |",
          "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s |"
                 % (r["t"], r["n"], r["c"], r["q"], r["e"], r["risk"]))
    L += ["", "证据等级：A=腾讯官方工程文　B=社区实测帖　C=开源工具反推　D=本次之前的推测", "",
          "填充建议：一格 `✅ 活 / ❌ 死 / 🟡 半活` + 一句现象就够，别写长；"
          "真正要留的是「死/活」的二值判断。"
          "填表前先扫一眼灰底 SENTINEL 哨兵有没有被染色 —— 那个信号比探针本身值钱。", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return len(filled)


# ---------------------------------------------------------------- main
CH_IMGS = {}
ROWS = []


def main():
    spec_path = os.path.join(SPEC_DIR, "spec.json")
    spec = json.load(open(spec_path, encoding="utf-8"))
    version = spec.get("version", "v0")
    title = spec.get("title", "排版样张")
    CH_IMGS.update({im["id"]: im for im in spec.get("images", [])})

    files = OrderedDict()
    nav = []

    # ---- 图片（先落进 files，manifest 由扩展名推导）
    for im in spec.get("images", []):
        files["OEBPS/images/%s.%s" % (im["id"], im["fmt"])] = gen_img(im)
    files["OEBPS/images/cover.jpg"] = gen_cover(version, DATE, len(spec["chapters"]), TOTAL_CH)

    # ---- 封面页（cover.jpg 由 <meta name="cover"> 指，这里再放一次页面引用）
    files["OEBPS/text/cover.xhtml"] = xhtml(
        "封面", '<div class="cover"><img src="../images/cover.jpg" alt="封面"/></div>')
    # ---- 书名页
    files["OEBPS/text/title.xhtml"] = xhtml("书名页", render_title(spec))
    nav.append((0, spec.get("subtitle") or title, "text/title.xhtml"))

    # ---- 待验证清单
    for ch in spec["chapters"]:
        for pr in ch.get("probes") or []:
            if pr.get("n"):
                if pr.get("k") == "p":
                    c = pr.get("c") or ""
                    c = "." + c if c else "(无 class)"
                elif pr.get("k") == "fig":
                    c = "<img " + (pr.get("attrs") or "") + ">"
                else:
                    c = "自定义 HTML"
                ROWS.append({"t": pr["t"], "n": pr["n"], "c": c,
                             "q": pr.get("q") or "—", "e": pr.get("e") or "—",
                             "risk": ch.get("risk", "D")})
    files["OEBPS/text/guide.xhtml"] = xhtml("使用说明与待验证清单", render_guide(spec))
    nav.append((0, "使用说明与待验证清单", "text/guide.xhtml"))

    # ---- 章节：一章一个 xhtml，顺序即 spine 顺序
    order = ["title", "guide"]
    for i, ch in enumerate(spec["chapters"], 1):
        name = "p%02d" % i
        body = render_chapter(ch)
        files["OEBPS/text/%s.xhtml" % name] = xhtml(ch["h1"], body)
        nav.append((0, ch["h1"], "text/%s.xhtml" % name))
        order.append(name)
    # ---- 无样式基准页
    files["OEBPS/text/nostyle.xhtml"] = xhtml(spec["extra"][0]["h1"], render_nostyle(), no_css=True)
    nav.append((0, spec["extra"][0]["h1"], "text/nostyle.xhtml"))
    order.append("nostyle")

    nav.insert(0, (0, "封面", "text/cover.xhtml"))
    order.insert(0, "cover")

    # ---- 静态件
    files["OEBPS/style.css"] = CSS
    files["OEBPS/nav.xhtml"] = xhtml(
        "目录",
        '<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc" id="toc">'
        '<h1>目录</h1>%s</nav>' % nav_ol(nav))
    pts, _depth = ncx_points(nav)
    book_id = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "weread-epub-style-support-" + version))
    files["OEBPS/toc.ncx"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        '<head><meta name="dtb:uid" content="%s"/><meta name="dtb:depth" content="1"/>'
        '<meta name="dtb:totalPageCount" content="0"/>'
        '<meta name="dtb:maxPageNumber" content="0"/></head>\n'
        '<docTitle><text>%s</text></docTitle>\n<navMap>%s</navMap></ncx>\n'
        % (book_id, esc(title), pts))

    # ---- content.opf
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg"/>',
    ]
    spine = []
    for p in sorted(files):
        if p.startswith("OEBPS/text/"):
            fid = os.path.basename(p)[:-6]
            manifest.append('<item id="%s" href="%s" media-type="application/xhtml+xml"/>'
                            % (fid, p.replace("OEBPS/", "")))
            spine.append('<itemref idref="%s"/>' % fid)
        elif p.startswith("OEBPS/images/"):
            fid = os.path.basename(p)
            if fid == "cover.jpg":
                continue
            mt = "image/png" if fid.endswith(".png") else "image/jpeg"
            manifest.append('<item id="%s" href="%s" media-type="%s"/>'
                            % (fid[:-4], p.replace("OEBPS/", ""), mt))
    # spine 顺序严格 = order（封面页即 cover.xhtml，单独出图）
    spine_sorted = [s for o in order for s in spine if 'idref="%s"' % o in s]
    spine_sorted += [s for s in spine if s not in spine_sorted]

    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    files["OEBPS/content.opf"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"'
        ' xml:lang="zh-CN">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '<dc:identifier id="bookid">%s</dc:identifier>\n'
        '<dc:title>%s</dc:title>\n'
        '<dc:creator id="au">%s</dc:creator>\n'
        '<meta refines="#au" property="role" scheme="marc:relators">aut</meta>\n'
        '<dc:publisher>%s</dc:publisher>\n'
        '<dc:language>zh-CN</dc:language>\n'
        '<dc:date>%s</dc:date>\n'
        '<meta property="dcterms:modified">%s</meta>\n'
        '<meta name="cover" content="cover-image"/>\n'
        '</metadata>\n<manifest>%s</manifest>\n<spine toc="ncx">%s</spine>\n</package>\n'
        % (book_id, esc(title), esc(spec.get("author", "排版探针")),
           esc(spec.get("publisher", "weread-epub-style-support")), now, now,
           "".join(manifest), "".join(spine_sorted)))
    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '<rootfiles><rootfile full-path="OEBPS/content.opf"'
        ' media-type="application/oebps-package+xml"/></rootfiles></container>\n')

    # ---- 打包（mimetype 必须是首个 entry 且不压缩，否则不是合法 EPUB）
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "weread-epub-style-specimen-%s.epub" % version)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        for p, c in files.items():
            z.writestr(p, c, zipfile.ZIP_DEFLATED)

    if "--report" in sys.argv:
        rp = os.path.join(OUT_DIR, "report_%s.md" % version)
        # 恢复链：主表（真人手填的地方）优先；主表没了再退回 filled，双保险
        filled = load_filled(rp)
        if not filled:
            filled = load_filled(os.path.join(OUT_DIR, "report_%s_filled.md" % version))
        kept = write_report(spec, ROWS, rp, filled)
        # filled 恒等于「新骨架 + 已保留实测」，是实测的唯一真源，以后只读它
        write_report(spec, ROWS, os.path.join(OUT_DIR, "report_%s_filled.md" % version),
                     dict(filled))
        print("  主表已保留实测 %d 条" % kept)
    print("EPUB 写出: %s  %d bytes (%.2f KB)"
          % (out, os.path.getsize(out), os.path.getsize(out) / 1024.0))
    print("spine %d, nav 条目 %d, 图 %d, 探针 %d"
          % (len(spine_sorted), len(nav),
             sum(1 for p in files if p.startswith("OEBPS/images/")), len(ROWS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
