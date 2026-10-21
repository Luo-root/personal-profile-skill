"""画像的公共操作：文件发现、空判定、原子写、索引生成、模板初始化。

`validate.py` 和 `profile_write.py` 都从这里取，避免「检查时一套、写入时另一套」。

为什么要生成索引：Agent 判断「哪份填了、要不要展开」，不该去读六份文件才知道。
索引由脚本生成、不手写——手写的索引一定会漂。

为什么要分模板和数据：`templates/` 里是空壳，`profile/` 里是你的画像。
公开仓库只留空壳，画像留在本机——这样仓库可以公开，画像不会跟着走。
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
# 空壳模板所在目录：仓库里只有它，profile/ 是本机数据目录
TEMPLATE_DIR = "templates/profile"
TEMPLATE_RESIDENT = "templates/resident-layer.md"

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


# ---------------------------------------------------------------- 模板初始化


def bootstrap_profile(root: Path) -> list[str]:
    """新工作区初始化：把 `templates/profile/` 里的空壳复制到 `profile/`。

    只在「全新」时做——`profile/` 不存在，或里面一份画像都没有。
    已有画像不动，也不复活用户主动删掉的那些。
    返回新建的文件名。
    """
    source = root / TEMPLATE_DIR
    target = root / PROFILE_DIR
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


def ensure_profile_file(root: Path, stem: str) -> bool:
    """补一份指定画像：`profile/<stem>.md` 不存在时，从模板复制一份过来。

    模板里也没有就别造——让调用方提示用户自己建带 `##` 小节的文件。
    """
    source = root / TEMPLATE_DIR / f"{stem}.md"
    dest = root / PROFILE_DIR / f"{stem}.md"
    if dest.exists() or not source.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(dest, read(source))
    return True


def bootstrap_workspace(root: Path) -> tuple[list[str], bool]:
    """把工作区补齐：画像空壳 + 常驻层模板。

    返回 (新建的画像文件名, 常驻层是否新建)。
    """
    created = bootstrap_profile(root)
    resident = False
    source = root / TEMPLATE_RESIDENT
    dest = root / RESIDENT
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


def build_index(root: Path) -> Path:
    """重建 profile/_index.md，返回它的路径。"""
    files = profile_files(root)
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
        f"- 技能版本：{skill_version(root)}",
        f"- 常驻层版本：{resident_version(root)}",
        f"- 已启用：{enabled} / {len(files)}",
        f"- 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 文件 | 状态 | 一句话 | 最后修改 |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(rows if rows else ["| （空） | — | — | — |"])

    target = profile_dir(root) / INDEX_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, "\n".join(lines) + "\n")
    return target
