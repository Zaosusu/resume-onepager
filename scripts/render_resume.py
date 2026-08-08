#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YAML + 照片 → 一页纸简历（带真实文字层的 A4 PDF + 高分 PNG）。

用法：
    python render_resume.py <数据.yaml> [-o 输出目录] [--scale 3]

设计要点：
  · 渲染确定性：同一份 YAML 必然产出同样的 PDF。自由格式材料 → YAML 的语义抽取
    交给人或模型完成，本脚本不做解析。
  · 一页硬约束，双向自适应：
      内容多 → 逐级缩小整体字号（下限 0.85），到底仍溢出就**报错退出**并指出最长的
               几段，绝不静默截断。
      内容少 → 逐级放大（上限 1.20），仍有剩余高度则把余量分摊到段间距，
               避免下半页一大片空白。
  · 自检：输出后校验 PDF 恰好 1 页且文字层可提取——这正是"AI 生成图片式简历"的硬伤。
"""
import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

A4_W, A4_H = 794, 1123          # A4 @96dpi，单位 px

SHRINK_STEPS = [1.0, 0.97, 0.94, 0.91, 0.88, 0.85]
GROW_STEPS = [1.04, 1.08, 1.12, 1.16, 1.20]
GROW_TRIGGER = 0.94             # 内容不足页高的这个比例时才考虑放大
SEC_EXTRA_CAP = 30              # 右栏单个段间距最多补多少 px，防止段落散架
SIDE_EXTRA_CAP = 46             # 左栏段落少、每段更高，上限可以放宽些

TPL_DIR = Path(__file__).resolve().parent.parent / 'template'


def build_html(data: dict, yaml_dir: Path) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    # autoescape 只该作用于 YAML 里的用户数据（防止 & < > 破坏 HTML）。
    # css / icons 是我们自己的静态资源，必须用 | safe 注入——否则 CSS 里的引号会被
    # 转成 &#34;、子选择器的 > 会被转成 &gt;，整条规则被浏览器静默丢弃：
    # font-family 失效 → 退回浏览器默认字体，中文页面看不出来，英文页面变成衬线体。
    env = Environment(
        loader=FileSystemLoader(str(TPL_DIR), encoding='utf-8'),
        autoescape=select_autoescape(['html', 'j2']),
    )
    photo_uri = ''
    if data.get('photo'):
        p = (yaml_dir / str(data['photo'])).resolve()
        if not p.exists():
            sys.exit(f'[错误] 照片不存在：{p}')
        photo_uri = p.as_uri()
        _advise_photo(p, data)

    icons_html = (TPL_DIR / 'icons.html').read_text(encoding='utf-8')

    html = env.get_template('resume.html.j2').render(
        d=data,
        css=(TPL_DIR / 'style.css').read_text(encoding='utf-8'),
        icons=icons_html,
        photo_uri=photo_uri,
    )

    _check_icons(html)

    # 静态资源被转义会让整条 CSS 规则失效，而页面照样渲染得出来——这类故障不会报错，
    # 只会安静地变丑。所以在这里硬校验一次。
    style = html[html.find('<style>'):html.find('</style>')]
    for bad in ('&#34;', '&quot;', '&gt;', '&amp;'):
        if bad in style:
            sys.exit(f'[错误] 注入的 CSS 被 HTML 转义了（发现 {bad}），'
                     f'font-family 等规则会被浏览器丢弃。模板里应写 {{{{ css | safe }}}}。')
    return html


def _check_icons(html: str) -> None:
    """校验渲染结果里每一个 <use href="#i-xxx"> 都能在 sprite 里找到。

    `<use>` 指向不存在的 id 不会报错，只会画一个空框——徽章的圆圈和卡片的方框
    里空空如也。渲染成功、自检通过、断言全绿，只有看图才发现是空的。

    在**渲染后的完整 HTML** 上查，而不是只查 YAML 里的 icon 字段：模板里还硬编码了
    十来个图标（#i-person、#i-briefcase、#i-bank…），sprite 少了任何一个，
    症状完全一样。查最终产物才能两种都覆盖。
    """
    import re
    # 先剥掉 HTML 注释：icons.html 的注释里写着示例 <use href="#i-xxx">，
    # 不剥就会把它当成真引用，于是每次渲染都报「图标 xxx 不存在」。
    body = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    declared = set(re.findall(r'<symbol[^>]*\bid="i-([\w-]+)"', body))
    used = set(re.findall(r'<use[^>]*\bhref="#i-([\w-]+)"', body))
    missing = sorted(used - declared)
    if missing:
        sys.exit(f'[错误] 引用了 sprite 里不存在的图标：{", ".join(missing)}\n'
                 f'       会渲染成空框。可用值：{" ".join(sorted(declared))}')


def _advise_photo(path: Path, data: dict) -> None:
    """照片构图与 photo_style 明显不匹配时给出提示。

    panel 容器是竖长的（约 0.7 的宽高比）。横构图照片按 cover 填进去，会被放大到
    只剩中间一小块，人脸经常直接被切掉——渲染不会报错，出来的图却没法用。
    """
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return

    style = data.get('photo_style') or 'panel'
    if style != 'circle' and w > h:
        print(f'[提示] 照片是横构图（{w}×{h}），但 photo_style=panel 是竖长版面，'
              f'会被裁成中间一小块。\n'
              f'       建议改用 photo_style: circle，或换一张竖构图/方形的人像。',
              flush=True)


def _advise_density(main_h: int) -> None:
    """右栏内容撑不起一页时明确说出来，而不是交付一张下半页空白的简历。"""
    ratio = main_h / A4_H
    if ratio >= 0.78:
        return
    print(f'\n[提示] 右栏内容只占页面高度的 {ratio:.0%}，下半页会明显空白。\n'
          f'       字号已放大到上限、段间距也已分摊，剩下的是内容量问题：\n'
          f'       建议补充 experience / projects 条目，或给 competencies 的正文多写一句。\n'
          f'       内容确实就这么少的话，一页 A4 可能不是合适的载体。', flush=True)



def _page_h(page) -> int:
    """.page 的 scrollHeight —— **分页的权威判据**。

    .page 有 min-height: 297mm，所以它恒 >= 1123：内容装得下时它就等于 1123，
    装不下时才变大。用来判断「会不会溢出成第二页」是准确的，用来判断「还剩多少
    空间」则完全无效（永远读不到小于 1123 的值）。
    """
    return page.evaluate('() => document.querySelector(".page").scrollHeight')


def _col_heights(page):
    """左栏、右栏各自的自然内容高度 —— 只用来估算**剩余空间**。

    把每栏的 padding 与子元素高度＋外边距累加。这是个代理值，实测比真实布局高度
    偏小约 3%（外边距折叠、亚像素舍入）。所以它只能用来决定「值不值得尝试放大」，
    每一步放大是否安全必须回头用 _page_h 校验——否则会越界，PDF 悄悄变成 2 页。

    .quote 用 margin-top: auto 顶到栏底，Chrome 的 getComputedStyle 对 auto 外边距
    返回的是解析后的实际像素值（不是 0），照单累加会让左栏恒等于满页高，
    同样估不出剩余空间。所以这里显式把它当 0。
    """
    return page.evaluate("""() => {
        const natural = el => {
            const cs = getComputedStyle(el);
            let h = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
            for (const c of el.children) {
                const s = getComputedStyle(c);
                const mt = c.classList.contains('quote') ? 0 : parseFloat(s.marginTop);
                h += c.getBoundingClientRect().height + mt + parseFloat(s.marginBottom);
            }
            return Math.round(h);
        };
        return [natural(document.querySelector('.side')),
                natural(document.querySelector('.main'))];
    }""")


def _spread(page, var: str, selector: str, slack: int, cap: int) -> None:
    """把剩余高度分摊到某一栏的段间距上。分摊后用权威判据复核，越界就回退。"""
    gaps = page.evaluate(f'() => document.querySelectorAll("{selector}").length') - 1
    if slack <= 12 or gaps <= 0:
        return
    extra = min(slack / gaps, cap)
    _set(page, var, f'{extra:.1f}px')
    if _page_h(page) > A4_H:
        _set(page, var, '0px')
    else:
        print(f'  {selector} 余下约 {slack}px 空白已分摊到 {gaps} 处段间距'
              f'（每处 +{extra:.0f}px）', flush=True)


def _set(page, name: str, value) -> None:
    page.evaluate('([n, v]) => document.documentElement.style.setProperty(n, v)',
                  [name, str(value)])
    page.wait_for_timeout(60)


def fit_one_page(page) -> float:
    """把内容调整到大致一页，返回选定的缩放系数。装不下则报错退出。

    这里只做**屏幕布局**上的预调；是否真的只有一页，由 render() 数 PDF 页数定夺。
    _col_heights 只用于估算剩余空间，不用来判定安全：它比真实布局高度偏小约 3%。
    """
    # ── 内容多：往下缩 ──
    chosen = None
    for fit in SHRINK_STEPS:
        _set(page, '--fit', fit)
        h = _page_h(page)
        print(f'  --fit {fit:.2f} → 页高 {h}px / 上限 {A4_H}px', flush=True)
        if h <= A4_H:
            chosen = fit
            break

    if chosen is None:
        # 不静默截断：报告各段实际高度，让调用者回头删内容
        secs = page.evaluate("""() => [...document.querySelectorAll('.sec, .side-sec')]
            .map(e => ({t: (e.querySelector('.cn, .side-h')?.innerText || '?').trim(),
                        h: Math.round(e.getBoundingClientRect().height)}))
            .sort((a, b) => b.h - a.h)""")
        over = _page_h(page) - A4_H
        print('\n[失败] 缩到下限 %.2f 仍超出一页 %d px。各段高度（降序）：'
              % (SHRINK_STEPS[-1], over), file=sys.stderr)
        for s in secs:
            print(f'    {s["h"]:>5}px  {s["t"]}', file=sys.stderr)
        print('\n请删减最长的一到两段内容后重跑——本脚本不会替你截断。', file=sys.stderr)
        sys.exit(2)

    if chosen < 1.0:
        print(f'  内容偏多，已整体缩放至 {chosen:.0%}', flush=True)
        return chosen

    # ── 内容少：先放大字号。用列高估剩余空间，用 _page_h 判每一步是否安全 ──
    if max(_col_heights(page)) >= A4_H * GROW_TRIGGER:
        return chosen                           # 本来就差不多满页，不动

    for fit in GROW_STEPS:
        _set(page, '--fit', fit)
        if _page_h(page) > A4_H:
            _set(page, '--fit', chosen)         # 回退到上一档
            break
        chosen = fit
    if chosen > 1.0:
        print(f'  内容偏少，已整体放大至 {chosen:.0%}', flush=True)

    # ── 仍有剩余：两栏各自把余量分摊到段间距 ──
    side_h, main_h = _col_heights(page)
    _spread(page, '--sec-extra', '.main .sec', A4_H - main_h, SEC_EXTRA_CAP)
    _spread(page, '--side-extra', '.side .side-sec', A4_H - side_h, SIDE_EXTRA_CAP)
    _advise_density(_col_heights(page)[1])
    return chosen


def _pdf_pages(path: Path) -> int:
    import fitz
    doc = fitz.open(str(path))
    n = doc.page_count
    doc.close()
    return n


def render(html_path: Path, pdf_path: Path, png_path: Path, scale: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(device_scale_factor=scale,
                                  viewport={'width': A4_W, 'height': A4_H})
        page = ctx.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state('load')

        try:
            fit = fit_one_page(page)
        except SystemExit:
            browser.close()
            raise

        def emit_pdf():
            page.pdf(path=str(pdf_path), format='A4', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
                     prefer_css_page_size=True)

        # 屏幕布局预测不了分页：page.pdf() 会按打印媒介重新排版，字体度量与屏幕
        # 略有差异，屏幕上"正好装下"的内容在 PDF 里可能溢出成第二页。
        # 所以真相只有 PDF 自己知道——数它的页数，超了就降一档重出。
        emit_pdf()
        if _pdf_pages(pdf_path) > 1:
            ladder = [f for f in reversed(GROW_STEPS) if f < fit] + \
                     [f for f in SHRINK_STEPS if f < fit]
            for f in ladder:
                print(f'  PDF 溢出成 {_pdf_pages(pdf_path)} 页，回退到 {f:.0%} 重出',
                      flush=True)
                _set(page, '--fit', f)
                _set(page, '--sec-extra', '0px')      # 补白按旧字号算的，一并清掉
                _set(page, '--side-extra', '0px')
                emit_pdf()
                if _pdf_pages(pdf_path) == 1:
                    fit = f
                    break
            else:
                browser.close()
                print(f'\n[失败] 降到下限 {SHRINK_STEPS[-1]:.0%} 后 PDF 仍不止一页。',
                      file=sys.stderr)
                sys.exit(2)

        page.screenshot(path=str(png_path),
                        clip={'x': 0, 'y': 0, 'width': A4_W, 'height': A4_H})
        browser.close()


def self_check(pdf_path: Path, png_path: Path) -> None:
    import fitz
    doc = fitz.open(str(pdf_path))
    text = ''.join(p.get_text() for p in doc).strip()
    pages = doc.page_count
    rect = doc[0].rect
    doc.close()

    from PIL import Image
    size = Image.open(str(png_path)).size

    print(f'\n自检：PDF {pages} 页，{rect.width:.0f}×{rect.height:.0f}pt，'
          f'可提取文字 {len(text)} 字符；PNG {size[0]}×{size[1]}')
    problems = []
    if pages != 1:
        problems.append(f'PDF 不是 1 页（{pages} 页）')
    if len(text) < 200:
        problems.append(f'文字层过少（{len(text)} 字符），PDF 可能退化成图片')
    if problems:
        for p in problems:
            print(f'[失败] {p}', file=sys.stderr)
        sys.exit(3)
    print('自检通过。')


def main() -> None:
    ap = argparse.ArgumentParser(description='YAML → 一页纸简历 PDF + PNG')
    ap.add_argument('yaml', help='简历数据 YAML')
    ap.add_argument('-o', '--out', help='输出目录（默认与 YAML 同目录）')
    ap.add_argument('--scale', type=int, default=3, help='PNG 缩放倍数，默认 3')
    a = ap.parse_args()

    import yaml as _yaml
    yp = Path(a.yaml).resolve()
    if not yp.exists():
        sys.exit(f'[错误] 找不到 {yp}')
    data = _yaml.safe_load(yp.read_text(encoding='utf-8')) or {}
    if not data.get('name'):
        sys.exit('[错误] YAML 缺少必填字段 name')

    out = Path(a.out).resolve() if a.out else yp.parent
    out.mkdir(parents=True, exist_ok=True)

    stem = f"{data['name']}_简历"
    html_p, pdf_p, png_p = out / '_resume.html', out / f'{stem}.pdf', out / f'{stem}.png'

    html_p.write_text(build_html(data, yp.parent), encoding='utf-8')
    print(f'HTML  → {html_p}')
    render(html_p, pdf_p, png_p, a.scale)
    print(f'PDF   → {pdf_p}')
    print(f'PNG   → {png_p}')
    self_check(pdf_p, png_p)


if __name__ == '__main__':
    main()
