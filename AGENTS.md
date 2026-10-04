# AGENTS.md —— 给 AI/脚本的操作指令

本仓库提供**微信读书 App 对 EPUB/CSS 的真实支持边界**（真机实测）。
如果你是 AI agent，正在为「导入微信读书阅读」的 EPUB 生成或审查 CSS，请按下述规则工作。

## 1. 先读机器可读规则

优先读取 **`docs/style-support.json`**（唯一结构化真源）：

- `rules[]`：每条含 `id / feature / css / status / reason / alternative / evidence`
- `status` 取值：`allowed`（放心用）、`gray`（不稳定，用 `alternative` 兜底）、`dead`（不要用，必须走 `alternative`）
- `font_stacks.kaiti_replica`：引语换楷体时整串复制的字体栈
- `checklist`：交付前逐条自检

人类可读的完整依据见 `docs/weread-epub-style-support.md`（含活/死/灰清单与逐项边界）。

## 2. 硬性生成规则（违反即会被微信读书吃掉）

**必须做**

- 样式一律写成**扁平单类名**（如 `.quote`、`.note`），一个类对应一条规则
- 字号用相对单位：`em` / `rem` / `%` / `pt`
- 需要换行分页的位置：**拆成独立 spine 文件**（一章一文件）
- 图片：尺寸与位置**在出图阶段定死像素**，要居中就直接把内容画在图片中央
- 注释：短注用**行内小字夹注**；长注放**章末**，正文角标只作视觉标记
- 表格：直接用原生 HTML（`table / caption / colspan`）

**禁止做（`status: dead`）**

| 禁止 | 改用 |
| --- | --- |
| `text-indent` | 交给 App 全局「正文首行缩进」 |
| `line-height` | 交给 App 全局「行距」 |
| `px` 字号 | `em / rem / % / pt` |
| 内联 `style="…"` | 扁平单类名 |
| 后代 / 伪类 / 伪元素 / `@media` 选择器 | 扁平单类名 |
| `img` 的 style 定宽/限宽/定高 | 出图时定死像素 |
| `figure` 居中 / `margin:0 auto` | 居中画进图片 |
| `float` 图文绕排 | 上下排列 |
| `page-break-after` / `break-inside` | 拆 spine 文件 |
| `epub:type="footnote"` 弹注、`href="#id"` 章内跳转 | 行内小字注 / 章末注且不做跳转 |
| `flex` / `transform` / `text-shadow` / `small-caps` | 普通块级 + 扁平类名 |
| CJK 扩展 B 区生僻字 | 避免使用或转图片 |

**需要兜底（`status: gray`）**

- 后代/嵌套选择器：一律改写扁平单类名
- `font-family`：不要指望系统字体名；要换楷体时整串复制 `font_stacks.kaiti_replica`
- `float` 绕排、`figure` 居中：按 `alternative` 处理

## 3. 输出 CSS 的最小模板

```css
/* 只用扁平单类名；不用 text-indent / line-height / px 字号 / 内联 style */
.para      { color: #222; }
.center    { text-align: center; }
.highlight { background: #f6f6f6; letter-spacing: .05em; }
.quote     { font-family: "汉仪楷体S","ETrump KaiTi","方正仿宋","FZFSJW--GB1-0","PingFang SC",-apple-system,"SF UI Text","Lucida Grande",STheiti,"Microsoft YaHei",sans-serif; color: brown; }
.note      { font-size: .85em; color: #666; }
```

## 4. 交付前自检

逐条核对 `docs/style-support.json` 的 `checklist`，任何一条不通过就不要交付。

## 5. 结论的边界

- 结论来自**真机逐屏实测**，针对**特定版本**的微信读书 App；App 更新后可能变化。
- 结论**不是官方文档**。若与官方文档冲突，以官方为准，并欢迎用仓库内样张书复现后开 issue。
- 需要复核某条结论：把 `epub/weread-epub-style-specimen-1.0.epub` 导入微信读书，按探针编号（如 `T01.1`）搜索定位，对照 `docs/weread-epub-style-support.md` 的预期结果判断。
