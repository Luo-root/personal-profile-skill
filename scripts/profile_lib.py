"""画像的公共操作：文件发现、空判定、原子写、索引生成、模板初始化。

`validate.py` 和 `profile_write.py` 都从这里取，避免「检查时一套、写入时另一套」。

为什么要生成索引：Agent 判断「哪份填了、要不要展开」，不该去读六份文件才知道。
索引由脚本生成、不手写——手写的索引一定会漂。

为什么要分两个根：
  **引擎根**（skill_root）——技能本体：SKILL.md、scripts/、templates/、modules/。
    可以公开、可以随便重装、可以随时重构。
  **数据根**（data_root）——你的画像：profile/、inbox.md、resident-layer.md、哈希基线。
    跟技能结构无关，路径不变就不会被结构变更牵连。

数据根怎么找（优先级从高到低）：
  1. 命令行 `--root`
  2. 引擎根里的 `.profile-root` 指针文件（内容是数据根的绝对路径）
  3. 引擎根本身（单目录布局：画像和技能放一起的老用法，照旧能跑）

这样技能结构怎么改都不影响画像的位置，而画像也不进任何公开仓库。
"""

from __future__ import annotations

import datetime
import os
import re
import tempfile
from pathlib import Path

PROFILE_DIR = "profile"
INDEX_NAME = "_index.md"
RESIDENT = "resident-layer.md"
SKILL_DOC = "SKILL.md"
# 空壳模板所在目录：相对引擎根
TEMPLATE_DIR = "templates/profile"
TEMPLATE_RESIDENT = "templates/resident-layer.md"
# 数据根指针文件：相对引擎根，内容是数据根的绝对路径。本机文件，不进仓库。
DATA_POINTER = ".profile-root"

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
FILLER_RE = re.compile(r"^[\s|:\-]+$")
VERSION_RE = re.compile(r"^version:\s*(\S+)", re.M)
RESIDENT_VERSION_RE = re.compile(r"常驻层\s*(v[\d.]+)")
# 索引里的展示顺序：先「我是谁」，再「不能越的线」，其余按熟悉度
ORDER = [
    "who-i-am",
    "boundaries",
    "how-to-talk",
    "my-setup",
    "restore-my-access",
    "personal-life",
]


def profile_dir(root: Path) -> Path:
    return root / PROFILE_DIR


def profile_files(root: Path) -> list[Path]:
    """profile/ 下的数据文件，按下刀顺序排（先身份、再边界，其余按字母）。

    下划线开头的是派生物（索引），不算画像。
    """
    directory = profile_dir(root)
    if not directory.is_dir():
        return []

    def order(path: Path):
        stem = path.stem
        rank = ORDER.index(stem) if stem in ORDER else len(ORDER)
        return (rank, stem)

    return sorted(
        (p for p in directory.glob("*.md") if not p.name.startswith("_")),
        key=order,
    )


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


# ---------------------------------------------------------------- 两个根


def resolve_data_root(skill_root: Path, override: str | None = None) -> Path:
    """找到数据根：命令行 > `.profile-root` 指针 > 引擎根本身。

    指针文件读不到、路径不存在、或者指的地方是空的，都退回引擎根——
    单目录布局（画像和技能放一起）继续照旧能跑。
    """
    if override:
        return Path(override).expanduser().resolve()
    pointer = skill_root / DATA_POINTER
    if pointer.is_file():
        try:
            text = pointer.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            text = ""
        if text:
            candidate = Path(text).expanduser()
            if candidate.is_dir():
                return candidate.resolve()
    return skill_root


def data_pointer_path(skill_root: Path) -> Path:
    return skill_root / DATA_POINTER


def write_data_pointer(skill_root: Path, data_root: Path) -> Path:
    """写指针文件：告诉这个技能实例「画像在哪儿」。"""
    pointer = data_pointer_path(skill_root)
    write_atomic(pointer, str(data_root.resolve()) + "\n")
    return pointer


# ---------------------------------------------------------------- 模板初始化


def bootstrap_profile(skill_root: Path, data_root: Path) -> list[str]:
    """新工作区初始化：把引擎根 `templates/profile/` 的空壳复制到数据根 `profile/`。

    只在「全新」时做——`profile/` 不存在，或里面一份画像都没有。
    已有画像不动，也不复活用户主动删掉的那些。
    返回新建的文件名。
    """
    source = skill_root / TEMPLATE_DIR
    target = data_root / PROFILE_DIR
    if not source.is_dir():
        return []
    if target.is_dir() and any(target.glob("*.md")):
        return []
    target.mkdir(parents=True, exist_ok=True)
    created = []
    for path in sorted(source.glob("*.md")):
        dest = target / path.name
        if not dest.exists():
            write_atomic(dest, read(path))
            created.append(path.name)
    return created


def ensure_profile_file(skill_root: Path, data_root: Path, stem: str) -> bool:
    """补一份指定画像：数据根 `profile/<stem>.md` 不存在时，从引擎根的模板复制一份。

    模板里也没有就别造——让调用方提示用户自己建带 `##` 小节的文件。
    """
    source = skill_root / TEMPLATE_DIR / f"{stem}.md"
    dest = data_root / PROFILE_DIR / f"{stem}.md"
    if dest.exists() or not source.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(dest, read(source))
    return True


def bootstrap_workspace(skill_root: Path, data_root: Path) -> tuple[list[str], bool]:
    """把工作区补齐：画像空壳 + 常驻层模板。

    返回 (新建的画像文件名, 常驻层是否新建)。
    """
    created = bootstrap_profile(skill_root, data_root)
    resident = False
    source = skill_root / TEMPLATE_RESIDENT
    dest = data_root / RESIDENT
    if source.exists() and not dest.exists():
        write_atomic(dest, read(source))
        resident = True
    return created, resident


def is_empty(path: Path) -> bool:
    """去掉注释、标题、表格骨架后没有正文，就算未启用。

    表格单独处理：只有「表头 + 分隔行」的表格不算内容——
    否则一个空表格会让整份文件被误判成已填写。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    lines = strip_comments(text).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("|"):
            block = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                block.append(lines[index])
                index += 1
            if len(block) >= 3:
                return False
            continue
        if not line.strip() or HEADING_RE.match(line) or FILLER_RE.match(line):
            index += 1
            continue
        return False
    return True


def summary(path: Path, limit: int = 30) -> str:
    """取一条最像「这份在讲什么」的摘要，供索引里一眼识别。

    边界文件很特殊：它的小节正文是 `### [硬] …` 这种标题，会被当成标题跳过，
    于是「第一条正文」反而落到别的小节上。这种情况直接数条数，比摘要有用。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "—"
    body = strip_comments(text)
    hard = len(re.findall(r"^###\s*\[硬\]", body, re.M))
    soft = len(re.findall(r"^###\s*\[软\]", body, re.M))
    if hard or soft:
        return f"硬边界 {hard} 条 · 软 {soft} 条"

    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("|"):
            block = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                block.append(lines[index])
                index += 1
            if len(block) >= 3:
                return f"表格 · {len(block) - 2} 行"
            continue
        stripped = line.strip()
        if not stripped or HEADING_RE.match(line) or FILLER_RE.match(line):
            index += 1
            continue
        plain = re.sub(r"^[#>*\-+\s]+", "", stripped)
        return plain[:limit] + ("…" if len(plain) > limit else "")
    return "—"


def skill_version(root: Path) -> str:
    path = root / SKILL_DOC
    if not path.exists():
        return "?"
    match = VERSION_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else "?"


def resident_version(root: Path) -> str:
    """常驻层里写死的版本号。Agent 拿它和系统提示里看到的那份比对，判断是否过期。"""
    path = root / RESIDENT
    if not path.exists():
        return "?"
    match = RESIDENT_VERSION_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else "未标版本"


def _stamp(path: Path) -> str:
    try:
        moment = datetime.datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return "—"
    return moment.strftime("%Y-%m-%d %H:%M")


def build_index(skill_root: Path, data_root: Path) -> Path:
    """重建数据根的 `profile/_index.md`，返回它的路径。

    索引写在数据根（跟画像待在一起），技能版本从引擎根读，常驻层版本从数据根读。
    """
    files = profile_files(data_root)
    rows = []
    enabled = 0
    for path in files:
        empty = is_empty(path)
        if not empty:
            enabled += 1
        rows.append(
            "| {name} | {state} | {summary} | {stamp} |".format(
                name=path.stem,
                state="空" if empty else "启用",
                summary="—" if empty else summary(path),
                stamp="—" if empty else _stamp(path),
            )
        )

    lines = [
        "# 画像索引",
        "",
        "<!-- 自动生成，不要手改。由 scripts/validate.py 和 scripts/profile_write.py 维护。 -->",
        "",
        f"- 技能版本：{skill_version(skill_root)}",
        f"- 常驻层版本：{resident_version(data_root)}",
        f"- 已启用：{enabled} / {len(files)}",
        f"- 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 文件 | 状态 | 一句话 | 最后修改 |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(rows if rows else ["| （空） | — | — | — |"])

    target = profile_dir(data_root) / INDEX_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, "\n".join(lines) + "\n")
    return target
