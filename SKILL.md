---
name: resume-onepager
description: 根据一张人像照片和一份人物信息，生成固定视觉风格的一页纸简历，同时输出带真实文字层的 A4 PDF 和高分辨率 PNG。适用于：做简历、生成简历、一页纸简历、个人简历、把履历做成简历、照片做成简历、更新简历、改简历内容、resume、CV、导师简介、讲师简介、人物简介、专家介绍。输入可以是 .md / .docx / 纯文本 / 零散要点，本 skill 负责把它整理成结构化数据再排版。
---

# 简历skill

把「照片 + 人物信息」渲染成一页 A4 简历。风格固定，内容可换，**同一套模板服务任何人**。

产出的 PDF **带真实文字层**——可搜索、可复制、HR 系统能解析。这是本 skill 存在的主要原因：让 AI 直接"画"一张简历图，可提取文字为 0，改一个字要做逐像素字形替换。

## 何时使用

用户给出人像照片 + 任何形式的个人信息，希望产出简历 / 个人介绍页时。也包括「改简历里某处内容」——改 YAML 重跑即可，秒级出片。

## 前置条件

```bash
pip install -r requirements.txt      # playwright jinja2 pyyaml pymupdf pillow
playwright install chromium          # 首次需要，约 150MB
```

- 照片：人像，纯色或简洁背景最佳。**不需要抠图**——裁切由 CSS 完成
- **不要用 weasyprint 代替 playwright**：它在多数环境缺 libpango，且对 CSS flex 支持不全
- 没有照片也能跑，左栏会自动省掉照片区

## 工作流程

1. **读取素材** —— 用户给的 md / docx / 文本全部读一遍。docx 用 `python-docx`
2. **抽取成 YAML** —— 按下方数据契约整理。**这一步是语义判断，不要写解析器**：挑哪三条够格当徽章、把长 bullet 压成卡片两行、判断哪三项算「核心竞争力」，都是判断题
   - **事实不得编造或美化**。原始材料里没有的，字段留空；数字、奖项名称、公司名逐字照抄
   - 材料自相矛盾时**问用户**，不要自己选一个
3. **渲染**
   ```bash
   python scripts/render_resume.py 数据.yaml -o 输出目录
   ```
4. **亲自看一遍** —— 用 Read 工具打开生成的 PNG，确认没跑版、没截断、照片构图正常。**不要跑完脚本就说做完了**
5. **报告** —— 给出 PDF / PNG 路径，说明自检结果（页数、文字层字符数、缩放比例）

## 数据契约

除 `name` 外全部可选，**缺失即整段不渲染**（不留空标题、不留空白块）。

```yaml
name: 林知远                     # 必填，唯一必填项
alias: 阿远                      # 姓名后的括号
title: 资深后端架构师 | 高并发系统与技术团队负责人

photo: assets/photo.png          # 相对本 YAML 所在目录
photo_style: panel               # panel（默认）=左栏顶部出血大图，保留照片里的场景
                                 # circle       =圆形头像
photo_focus: [50, 40]            # 裁切焦点百分比 [x,y]，默认 [50,50]
photo_zoom: 1.6                  # 再放大倍数，仅当原图人物太小时需要
photo_height: 26rem              # 仅 panel：大图高度
photo_size: 16rem                # 仅 circle：圆直径

badges:                          # 0–3 个，为空则整行不渲染
  # main 控制在 8 个汉字 / 20 个拉丁字符以内。三个徽章横向三等分，
  # 超了会折成两三行，很难看。
  - {icon: rocket, main: 11年后端研发, sub: 电商/支付/中台}

contact:                         # 子项可缺
  phone: "138-0000-0000"
  email: "a@b.com"
  location: 杭州
  extra: {GitHub: github.com/x}  # 额外自定义行

skills:  [分布式系统与微服务架构, Go / Java / Kubernetes]
awards:  [公司年度技术突破奖 两届]

intro: |
  自我介绍，多行会保留换行

experience:                      # 时间轴，可多组
  - role: 资深架构师 / 技术负责人    # 组标题，可省
    items:
      - {period: 2021-至今, text: 条目正文}
      - {text: 没有时间标签的条目}

education:                       # 结构同 experience，应届生常用
projects:                        # 结构同 experience

competencies:                    # 1–3 张卡
  - {icon: code, title: 技术深度, text: 卡片正文}

quote: |                         # 左下深蓝色块内的白字
  好的架构是演进出来的，
  不是一次设计出来的。

labels:                          # 覆盖段落标题，做英文简历时整块重写
  intro_cn: PROFILE
  intro_en: ""
  sep: ": "                      # 标签与值之间的分隔符，默认全角「：」
                                 # 英文简历要显式写成 ": "，否则会是中文冒号
```

段落渲染顺序固定：自我介绍 → 工作经历 → 教育背景 → 项目经历 → 核心竞争力。

可用 `icon` 值：`person phone mail pin star trophy diamond code chart pencil rocket robot bank briefcase`

## 排版约束

**一页是硬上限。** 脚本双向自适应：

- 内容多 → 逐级缩小整体字号到 0.85。缩到底仍装不下会**报错退出**，并打印各段实际高度、指出最长的几段。此时**必须回头删减内容**，不要提高缩放下限、不要截断文字
- 内容少 → 逐级放大到 1.20，再把余量分摊到两栏的段间距。若右栏仍不足页高 78%，
  脚本会打印提示——那是内容量问题，**补内容**，不要试图靠排版掩盖

左栏和徽章的字号只跟随缩小、不跟随放大（`min(--fit, 1)`）。它们横向受限，
跟着放大只会把电话、邮箱、徽章文案挤到折行。

## 调照片构图

照片先按 `object-fit: cover` 填满容器，再按 `photo_zoom` 以 `photo_focus` 为原点放大。

- **人脸被裁掉一半** → 调 `photo_focus`，人脸偏上就减小 y
- **人物在圆里位置偏低**（想让头部落在上三分之一）→ **增大** `photo_focus` 的 y。焦点往下移，人物在框内相对上移
- **只剩一张脸、看不到肩膀** → 减小 `photo_zoom`
- **头像太小** → panel 版加大 `photo_height`；circle 版加大 `photo_size`
- **横构图照片** → 必须用 `circle`。panel 是竖长版面，横图会被裁成中间一小块，
  人脸经常直接切掉。脚本检测到横图 + panel 会打印提示

只要原图是标准人像取景（头部在画幅上三分之一），默认值就是对的，三个参数都不用写。

## 换风格 / 调样式

- 配色、左栏宽度：只改 `template/style.css` 的 `:root`
- 版面结构：`template/resume.html.j2`
- 图标：`template/icons.html`（内联 SVG sprite，零网络依赖）
- **改完样式后重新渲染 `examples/full.yaml` 和 `examples/minimal.yaml` 做回归**，肉眼比对不应跑版

## 常见问题

- **中文显示成方框** → 系统缺中文字体。Linux 装 `fonts-noto-cjk`
- **整页变成衬线体（宋体 / Times）** → 说明注入的 CSS 被 HTML 转义了，
  `font-family` 整条被浏览器丢弃。模板里必须写 `{{ css | safe }}`。
  脚本已加硬校验，出现这种情况会直接报错退出
- **左栏下半部空一大块** → 加 `quote`，或补几条 `skills` / `awards`。脚本能分摊段间距，补不出内容
- **邮箱在左栏折行** → 左栏只有整页 30% 宽，超过约 19 个字符的邮箱必然折行
- **中文打印乱码** → 脚本已设 `sys.stdout` 为 UTF-8；自己另写脚本时记得加
- **自检报「文字层过少」** → 说明 PDF 退化成图片了，检查是否误用了截图转 PDF 的路径
