#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""冒烟测试：程序化生成一批人物，全部渲染，断言 + 拼版供肉眼复核。

    python tests/smoke.py              # 跑全部
    python tests/smoke.py --keep       # 保留中间产物

为什么要有这个：本项目最严重的两个缺陷（注入的 CSS 被 HTML 转义导致整套规则失效、
头像被渲染成椭圆）都是**看图**发现的，不是靠读代码推理出来的。所以这里除了断言，
还会把所有产物拼成一张 contact sheet —— 断言保证不崩，拼版保证不丑。

覆盖两类用例：
  · 正常路径（PASS 组）—— 字段数量、照片样式、内容密度的组合矩阵
  · 错误路径（FAIL 组）—— 必须以特定非零退出码失败，且打印可操作的信息
"""
import argparse
import io
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
RENDER = ROOT / 'scripts' / 'render_resume.py'
PHOTO = ROOT / 'examples' / 'assets' / 'placeholder.png'

LOREM_CN = ('负责该方向的整体设计与落地推进，覆盖需求梳理、方案选型与上线验证，'
            '相关指标较上一年度有明显改善。')


def person(name, *, style='panel', n_badges=3, n_skills=6, n_awards=5,
           n_exp=4, n_comp=3, quote=True, photo=True, intro_len=2,
           long_values=False, icon=None, n_groups=1):
    """按参数拼一份 YAML 数据。字段数量全部可调，用来铺满组合矩阵。"""
    d = {'name': name, 'title': '某方向负责人 | 团队管理'}
    if photo:
        d['photo'] = str(PHOTO).replace('\\', '/')
        d['photo_style'] = style
    if n_badges:
        d['badges'] = [{'icon': icon or 'rocket', 'main': f'徽章{i + 1}文案',
                        'sub': '副标题'} for i in range(n_badges)]
    d['contact'] = {'phone': '138-0000-0000', 'location': '某市'}
    if long_values:
        d['contact']['email'] = 'a.very.long.address@an-extremely-long-domain-name.com.cn'
    else:
        d['contact']['email'] = 'a@b.com'
    if n_skills:
        d['skills'] = [f'技能条目{i + 1}' for i in range(n_skills)]
    if n_awards:
        d['awards'] = [f'某项奖励或认证 {i + 1}' for i in range(n_awards)]
    d['intro'] = '自我介绍正文。' + LOREM_CN * intro_len
    if n_exp:
        d['experience'] = [{
            'role': f'第{g + 1}组组标题',
            'items': [{'period': f'20{10 + i}-20{12 + i}年', 'text': LOREM_CN}
                      for i in range(n_exp)],
        } for g in range(n_groups)]
    if n_comp:
        d['competencies'] = [{'icon': icon or 'code', 'title': f'竞争力{i + 1}',
                              'text': LOREM_CN} for i in range(n_comp)]
    if quote:
        d['quote'] = '一句话主张，\n分成两行。'
    return d


# ── 正常路径矩阵 ──────────────────────────────────────────────
# 每一项都是一个「该出得来、且该好看」的组合。
CASES = [
    ('01-典型-panel',      person('典型一号')),
    ('02-典型-circle',     person('典型二号', style='circle')),
    ('03-无照片',          person('无照片', photo=False)),
    ('04-单徽章',          person('单徽章', n_badges=1)),
    ('05-零徽章',          person('零徽章', n_badges=0)),
    ('06-单卡片',          person('单卡片', n_comp=1)),
    ('07-无引言',          person('无引言', quote=False)),
    ('08-无奖项',          person('无奖项', n_awards=0)),
    ('09-极简',            person('极简', n_badges=1, n_skills=2, n_awards=0,
                                  n_exp=1, n_comp=1, intro_len=1)),
    ('10-长值',            person('长值', long_values=True)),
    ('11-双组时间轴',      person('双组时间轴', n_exp=3, n_groups=2, intro_len=1)),
    ('12-长姓名',          person('欧阳锦程博尔济吉特')),
    ('13-满字段',          person('满字段', n_skills=8, n_awards=6, n_exp=3,
                                  n_groups=2, n_comp=3, intro_len=1)),
]

# ── 错误路径 ─────────────────────────────────────────────────
# (名字, 数据, 期望退出码, 输出里必须出现的关键词)
FAIL_CASES = [
    ('E1-缺name',    {'title': '没有名字'},                       1, '缺少必填字段 name'),
    ('E2-照片不存在', {'name': '坏路径', 'photo': 'no/such.png'},  1, '照片不存在'),
    # 未知 icon 名不会让渲染失败，只会画一个空框——断言抓不到，必须提前拦
    ('E3-未知图标',   person('未知图标', icon='no-such-icon'),     1, '不存在的图标'),
    ('E4-内容超一页', person('超长', n_skills=14, n_awards=12, n_exp=9,
                             n_groups=3, n_comp=3, intro_len=6),  2, '仍超出一页'),
]


def run(yaml_path: Path, out_dir: Path):
    r = subprocess.run([sys.executable, str(RENDER), str(yaml_path), '-o', str(out_dir),
                        '--scale', '1'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=str(ROOT / 'out' / 'smoke'),
                    help='产物目录，默认 <仓库>/out/smoke（已在 .gitignore 里）')
    a = ap.parse_args()

    import yaml as _yaml
    from PIL import Image

    work = Path(a.out).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    print(f'产物目录 {work}\n')

    rows, pngs, failed = [], [], 0

    print('── 正常路径 ' + '─' * 46)
    for label, data in CASES:
        yp = work / f'{label}.yaml'
        yp.write_text(_yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                      encoding='utf-8')
        code, log = run(yp, work / label)
        png = next((work / label).glob('*.png'), None)

        problems = []
        if code != 0:
            problems.append(f'退出码 {code}')
        if not png:
            problems.append('没有产出 PNG')
        elif Image.open(png).size != (794, 1123):
            problems.append(f'尺寸异常 {Image.open(png).size}')
        if '自检通过' not in log:
            problems.append('自检未通过')

        fit = next((s for s in log.splitlines() if '缩放至' in s or '放大至' in s), '')
        note = fit.strip().split('，')[-1] if fit else '100%'
        advis = [s.strip() for s in log.splitlines() if s.strip().startswith('[提示]')]

        ok = not problems
        failed += not ok
        rows.append((label, ok, note, problems, advis))
        print(f'{"✓" if ok else "✗"} {label:<16} {note:<18} '
              f'{"; ".join(problems) or ("提示×%d" % len(advis) if advis else "")}')
        if png:
            pngs.append((label, png))

    print('\n── 错误路径（必须失败，且失败得有用）' + '─' * 20)
    for label, data, want_code, want_text in FAIL_CASES:
        yp = work / f'{label}.yaml'
        yp.write_text(_yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                      encoding='utf-8')
        code, log = run(yp, work / label)
        ok = code == want_code and want_text in log
        failed += not ok
        detail = f'退出码 {code}（期望 {want_code}）'
        if want_text not in log:
            detail += f'，输出里没有「{want_text}」'
        print(f'{"✓" if ok else "✗"} {label:<16} {detail}')

    # ── 护栏：静默变丑的两类故障必须被拦住 ──
    # 这两条都不会让渲染崩掉，只会让产物安静地变错，所以必须靠护栏而不是断言。
    print('\n── 护栏 ' + '─' * 50)
    guards = 0
    yp = work / 'guard.yaml'
    yp.write_text(_yaml.safe_dump(CASES[0][1], allow_unicode=True, sort_keys=False),
                  encoding='utf-8')

    # 1) 注入的 CSS 被 HTML 转义 → font-family、content:"" 等整条失效
    tpl = ROOT / 'template' / 'resume.html.j2'
    orig = tpl.read_text(encoding='utf-8')
    try:
        tpl.write_text(orig.replace('{{ css | safe }}', '{{ css }}'), encoding='utf-8')
        code, log = run(yp, work / 'guard-css')
        ok = code == 1 and '被 HTML 转义' in log
        failed += not ok
        guards += 1
        print(f'{"✓" if ok else "✗"} CSS 被转义        退出码 {code}（期望 1）')
    finally:
        tpl.write_text(orig, encoding='utf-8')

    # 2) sprite 里缺图标 → <use> 指向空 id，画出空框
    ico = ROOT / 'template' / 'icons.html'
    orig_ico = ico.read_text(encoding='utf-8')
    try:
        import re as _re
        broken = _re.sub(r'<symbol[^>]*\bid="i-briefcase".*?</symbol>', '',
                         orig_ico, flags=_re.S)
        assert broken != orig_ico, 'icons.html 里没找到 i-briefcase，护栏用例需更新'
        ico.write_text(broken, encoding='utf-8')
        code, log = run(yp, work / 'guard-icon')
        ok = code == 1 and 'briefcase' in log
        failed += not ok
        guards += 1
        print(f'{"✓" if ok else "✗"} sprite 缺图标      退出码 {code}（期望 1）')
    finally:
        ico.write_text(orig_ico, encoding='utf-8')

    # ── 拼版：断言保证不崩，这张图保证不丑 ──
    if pngs:
        from PIL import ImageDraw, ImageFont
        cols, thumb_w, cap_h = 5, 300, 26
        thumb_h = round(thumb_w * 1123 / 794)
        rowsn = (len(pngs) + cols - 1) // cols
        cell_h = thumb_h + cap_h
        sheet = Image.new('RGB', (cols * thumb_w, rowsn * cell_h), (250, 250, 252))
        d = ImageDraw.Draw(sheet)

        font = None
        for cand in (r'C:\Windows\Fonts\msyh.ttc',                     # Windows
                     '/System/Library/Fonts/PingFang.ttc',             # macOS
                     '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'):
            if Path(cand).exists():
                try:
                    font = ImageFont.truetype(cand, 15)
                    break
                except Exception:
                    pass

        for i, (label, p) in enumerate(pngs):
            x, y = (i % cols) * thumb_w, (i // cols) * cell_h
            sheet.paste(Image.open(p).resize((thumb_w, thumb_h), Image.LANCZOS), (x, y))
            d.text((x + 8, y + thumb_h + 5), label, fill=(90, 97, 114), font=font)

        sheet_path = work / 'contact-sheet.png'
        sheet.save(sheet_path, optimize=True)
        print(f'\n拼版 → {sheet_path}')
        print('（断言只能保证不崩；版面好不好看，必须打开这张图看）')

    total = len(CASES) + len(FAIL_CASES) + guards
    print(f'\n合计 {total} 项，失败 {failed} 项。')
    print(f'全部产物（含每份的 PDF/PNG/HTML）在 {work}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
