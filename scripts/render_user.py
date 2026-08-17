#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多用户简历渲染助手：在 data/<用户>/ 内完成「建目录 + 渲染」，源数据与成品同处一文件夹。

用法：
    python render_user.py                        # 列出 data/ 下所有用户
    python render_user.py new <用户标识>          # 在 data/ 下建隔离目录 + 脚手架（自动归档起点）
    python render_user.py new <用户标识> --photo 照片路径
                                                  # 建目录并自动把照片拷进 data/<用户>/头像.png
    python render_user.py <用户标识>              # 渲染 data/<用户>/me.yaml → data/<用户>/（同目录）
    python render_user.py <用户标识> --scale 4    # 指定 PNG 缩放倍数（默认 3）
    python render_user.py <用户标识> --yaml cv.yaml   # 指定非默认的数据文件名

设计：
    · data/ 每个用户一个隔离子目录，全部被 .gitignore 忽略（私密、不上传）。
    · 产物与源数据同处 data/<用户>/：渲染出的 PDF/PNG/HTML 直接落在 YAML 同目录，
      一个文件夹就是「某人的完整简历包」，方便整体拷贝复用。
    · 「new」让创建简历时自动罗盘到 data/：一步建好隔离目录与脚手架，
      后续抽取出的 YAML 直接写回该目录即可，不必手动 mkdir/cp。
    · 底层渲染确定性逻辑全部复用 render_resume.py，本脚本只做「用户标识 → 路径」的映射。
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DEFAULT_YAML = 'me.yaml'
PHOTO_NAME = '头像.png'

# 自动生成的脚手架：除 name 外全部以「数据契约」注释形式给出，不编造任何简历内容。
SCAFFOLD = """\
# ============================================================
# 用户：{uid}
# 数据位置：data/{uid}/  （本目录已被 .gitignore 忽略，不会提交到公开仓库）
#{photo_note}
#
# 这是自动生成的脚手架。请按 SKILL.md「数据契约」从用户履历抽取字段填入。
# 除 name 外全部可选，缺失即整段不渲染。icon 可用值见 SKILL.md 末尾列表。
# ============================================================

name:            # 必填：用户真实姓名
{photo_field}
# title: 你的职位标题 | 副标题
#
# badges:
#   - {{icon: rocket, main: 你的核心标签, sub: 补充说明}}
#
# contact:
#   phone: ""
#   email: ""
#   location: 城市
#   extra: {{GitHub: github.com/你的名}}
#
# skills:  [技能一, 技能二]
# awards:  [奖项一, 奖项二]
#
# intro: |
#   你的自我介绍，多行会保留换行。
#
# experience:
#   - role: 工作经历分组标题（可省）
#     items:
#       - {{period: 2021-至今, text: 条目正文}}
#       - {{text: 没有时间标签的条目}}
#
# education:
#   - role: 教育背景（结构同 experience）
#     items:
#       - {{period: 2017-2021, text: 学校与专业}}
#
# projects:
#   - role: 项目经历（结构同 experience）
#     items:
#       - {{period: , text: 项目描述}}
#
# competencies:
#   - {{icon: code, title: 核心竞争力标题, text: 卡片正文}}
#
# quote: |
#   你想放在左下色块里的那句话。
"""


def _print_help() -> None:
    print(__doc__)


def list_users() -> None:
    if not DATA.exists():
        print(f'[信息] 还没有 data/ 目录（{DATA}）')
        return
    users = [d for d in sorted(DATA.iterdir())
             if d.is_dir() and not d.name.startswith('.')]
    if not users:
        print('[信息] data/ 下还没有任何用户，参考 data/README.md 新增一个。')
        return
    print(f'data/ 下的用户（共 {len(users)} 个）：')
    for d in users:
        yamls = sorted(p.name for p in d.glob('*.yaml')) + \
                sorted(p.name for p in d.glob('*.yml'))
        print(f'  · {d.name}   [{", ".join(yamls) if yamls else "无 yaml"}]')


def create_user(uid: str, photo: str | None, yaml_name: str) -> None:
    """在 data/ 下建隔离目录 + 脚手架；可选拷贝照片。用于「创建即自动归档到 data/」。"""
    udir = DATA / uid
    if udir.exists() and any(udir.glob('*.yaml')):
        print(f'[信息] 用户目录已存在：{udir}（保留现有数据，仅补缺失项）')

    udir.mkdir(parents=True, exist_ok=True)

    photo_field = '# photo: 头像.png   # 把照片放到本目录后取消注释'
    photo_note = ' 照片：放本目录下的 头像.png（photo 字段已自动指向它）'
    if photo:
        src = Path(photo)
        if not src.exists():
            sys.exit(f'[错误] 照片不存在：{src}')
        dst = udir / PHOTO_NAME
        shutil.copy(str(src), str(dst))
        photo_field = 'photo: 头像.png'
        photo_note = f' 照片：{PHOTO_NAME}（已自动拷贝进本目录）'

    yp = udir / yaml_name
    if not yp.exists():
        yp.write_text(SCAFFOLD.format(uid=uid, photo_note=photo_note,
                                      photo_field=photo_field),
                      encoding='utf-8')
        print(f'[已建] 脚手架：{yp}')
    else:
        print(f'[跳过] 已存在：{yp}')

    print(f'[完成] 隔离目录就绪：{udir}')
    print(f'        下一步：把从履历抽取出的字段写进 {yp}（name 必填），')
    print(f'              再执行  python scripts/render_user.py {uid}')


def render(uid: str, yaml_name: str, scale: int) -> None:
    udir = DATA / uid
    if not udir.is_dir():
        sys.exit(f'[错误] 找不到用户目录：{udir}\n'
                 f'       先用  python scripts/render_user.py new {uid}'
                 f' [--photo 照片路径]  在 data/ 下建好隔离目录。')
    yp = udir / yaml_name
    if not yp.exists():
        sys.exit(f'[错误] 找不到数据文件：{yp}\n'
                 f'       默认文件名是 me.yaml，可用 --yaml 指定其他文件名。')

    # 复用底层渲染脚本（它内部做一页自适应 + 文字层自检）。
    # 不传 -o：底层默认把产物输出到 YAML 同目录（data/<uid>/），
    # 源数据（me.yaml + 头像）与成品（PDF/PNG/HTML）同处一个文件夹，
    # 「某人的简历」就是 data/<uid>/ 一个目录，方便整体拷贝复用。
    import render_resume as rr
    sys.argv = ['render_resume.py', str(yp), '--scale', str(scale)]
    rr.main()


def _parse(allow_new: bool):
    """解析参数，返回 (action, uid, opts)。action ∈ {'list','new','render'}。"""
    args = sys.argv[1:]
    action = 'list'
    uid = None
    yaml_name = DEFAULT_YAML
    scale = 3
    photo = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-h', '--help'):
            _print_help()
            sys.exit(0)
        if a == 'new' and allow_new:
            action = 'new'; i += 1; continue
        if a == '--scale':
            scale = int(args[i + 1]); i += 2; continue
        if a == '--yaml':
            yaml_name = args[i + 1]; i += 2; continue
        if a == '--photo':
            photo = args[i + 1]; i += 2; continue
        if a.startswith('--scale='):
            scale = int(a.split('=', 1)[1]); i += 1; continue
        if a.startswith('--yaml='):
            yaml_name = a.split('=', 1)[1]; i += 1; continue
        if a.startswith('--photo='):
            photo = a.split('=', 1)[1]; i += 1; continue
        if uid is None:
            uid = a
        i += 1
    return action, uid, {'yaml_name': yaml_name, 'scale': scale, 'photo': photo}


def main() -> None:
    action, uid, opts = _parse(allow_new=True)
    if action == 'list':
        if uid is not None:
            # 形如 `render_user.py new` 漏写用户标识，或误把首个参数当 uid
            # 这里 action 已被 'new' 抢占，uid 为 None 才会进 list；若 uid 有值说明没有 new 关键字 → 渲染
            render(uid, opts['yaml_name'], opts['scale'])
            return
        list_users()
        return
    if action == 'new':
        if uid is None:
            sys.exit('[错误] new 需要一个用户标识，例如：'
                     'python scripts/render_user.py new 覃翘')
        create_user(uid, opts['photo'], opts['yaml_name'])
        return
    # 理论上不会到这里（无 new 且有 uid 已在 list 分支转 render）
    if uid is None:
        list_users()
    else:
        render(uid, opts['yaml_name'], opts['scale'])


if __name__ == '__main__':
    main()
