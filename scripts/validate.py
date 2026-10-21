#!/usr/bin/env python3
"""personal-profile 自检。

四件事：
1. 密钥扫描——唯一会失败的一项
2. 结构检查——死链、空段统计、硬边界条数、常驻层占位符与行数
3. 基线比对——`--baseline` 建基线，`--audit` 查出「绕过脚本直接改 profile/」的改动
4. 索引重建——默认顺带刷新；`--index-only` 只干这一件事

「缺失即跳过」是这份画像的正常语义：空段不是缺陷，不报错、不催填。

退出码契约（脚本化调用必须按这个判断，别靠猜）：
    0  通过
    1  失败——发现密钥，或审计查出绕过脚本的改动
    2  无法执行——目录不存在、参数用法错误、或 `--audit` 时还没有基线

注意 2 和 0 的区别：「没有基线所以没审」不等于「审过了所以干净」。
没有基线时 `--audit` 返回 2，不会伪装成通过。

用法：
    python scripts/validate.py
    python scripts/validate.py --index-only    # Agent 加载时只重建索引
    python scripts/validate.py --baseline
    python scripts/validate.py --audit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import (  # noqa: E402
    bootstrap_workspace,
    build_index,
    is_empty,
    profile_files,
    rel,
    resident_version,
    resolve_data_root,
    skill_version,
    strip_comments,
)
from scan_rules import scan_text  # noqa: E402

SKIP_DIRS = {".git", "__pycache__", "node_modules"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_CANNOT = 2


def _utf8_output() -> None:
    """Windows 默认 GBK，中文和符号会直接抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass


def iter_markdown(roots):
    """扫多个根下的 Markdown，产出 (所属根, 文件)。

    引擎根和数据根都要扫——密钥可能落在画像里，链接可能坏在模板里。
    同一个文件只算一次（单目录布局时两个根是同一个）。
    """
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                key = path.resolve()
            except OSError:
                key = path
            if key in seen:
                continue
            seen.add(key)
            yield root, path


def scan_secrets(files):
    hard, soft = [], []
    for root, path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[!] 读不了 {path}: {exc}")
            continue
        h, s = scan_text(text)
        for lineno, label, masked in h:
            hard.append((_relative(root, path), lineno, label, masked))
        for lineno, label, masked in s:
            soft.append((_relative(root, path), lineno, label, masked))
    return hard, soft


def scan_links(files):
    broken = []
    for root, path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in LINK_RE.findall(COMMENT_RE.sub("", text)):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0].strip()
            if not clean:
                continue
            if not (path.parent / clean).resolve().exists():
                broken.append((_relative(root, path), target))
    return broken


def _relative(root: Path, path: Path) -> Path:
    """尽量给出相对于所属根的路径；实在不在这棵树下就给绝对路径。"""
    try:
        return path.relative_to(root)
    except ValueError:
        return path


# ---------------------------------------------------------------- 基线

def state_path(root: Path) -> Path:
    return root / ".profile-state.json"


def load_state(root: Path):
    path = state_path(root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_baseline(root: Path) -> int:
    state = {"version": 1, "files": {}}
    count = 0
    for path in profile_files(root):
        state["files"][rel(root, path)] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "entry": "baseline",
        }
        count += 1
    state_path(root).write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[ok] 已为 {count} 份画像建立基线")
    print("     以后用 --audit 查「绕过脚本直接改文件」的改动。")
    return 0


def audit(root: Path) -> int:
    state = load_state(root)
    if state is None:
        print("[!] 还没有基线，无从审计。先跑一次：python scripts/validate.py --baseline")
        print("    （返回 2：「没审过」不等于「审过了干净」）")
        return EXIT_CANNOT

    recorded = state.get("files", {})
    drift, untracked = [], []
    for path in profile_files(root):
        rel_path = rel(root, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        known = recorded.get(rel_path)
        if known is None:
            if not is_empty(path):
                untracked.append(rel_path)
        elif known.get("sha256") != digest:
            drift.append((rel_path, known.get("entry", "?")))

    if drift:
        print("[x] 这些文件在基线之后被改过，而且不是通过 profile_write.py：")
        for rel_path, entry in drift:
            print(f"    {rel_path}  （基线条目 {entry}）")
        print("    要么用脚本重写一遍，要么确认改动后重建基线：--baseline")
    elif untracked:
        print("[!] 这些文件有内容但不在基线里（可能是手写的）：")
        for rel_path in untracked:
            print(f"    {rel_path}")
        print("    确认后跑一次 --baseline 收进基线。")
    else:
        print("[ok] 没有发现绕过脚本的改动")

    inbox = root / "inbox.md"
    if inbox.exists():
        pending = len(
            re.findall(
                r"^- 状态：pending\s*$",
                inbox.read_text(encoding="utf-8", errors="replace"),
                re.M,
            )
        )
        if pending:
            print(f"[!] inbox 里还有 {pending} 条待合并（apply 或 decline 都行）")

    return EXIT_FAIL if drift else EXIT_OK


def main() -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(
        description="personal-profile 自检",
        epilog=(
            "退出码：0=通过；1=失败（发现密钥，或审计查出绕过脚本的改动）；"
            "2=无法执行（目录不存在、用法错误、--audit 时还没有基线）。"
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="数据根目录（画像在哪）。默认读引擎根里的 .profile-root 指针，没有就用引擎根本身。",
    )
    parser.add_argument("--baseline", action="store_true", help="记录当前画像的哈希基线")
    parser.add_argument("--audit", action="store_true", help="比对基线，查出绕过脚本的改动")
    parser.add_argument("--no-index", action="store_true", help="不刷新索引")
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="只重建索引，不做其他检查——Agent 加载画像时用这一条",
    )
    args = parser.parse_args()

    # 引擎根 = 脚本的上一级；数据根 = --root > .profile-root 指针 > 引擎根
    skill_root = Path(__file__).resolve().parent.parent
    data_root = resolve_data_root(skill_root, args.root)
    if not skill_root.is_dir():
        print(f"[x] 引擎根不是一个目录：{skill_root}")
        return EXIT_CANNOT
    if not data_root.is_dir():
        print(f"[x] 数据根不是一个目录：{data_root}")
        return EXIT_CANNOT

    # 首次运行：把引擎根 templates/ 里的空壳铺进数据根 profile/，常驻层模板铺到数据根
    created, resident = bootstrap_workspace(skill_root, data_root)
    if created:
        print(f"[ok] 已初始化 {len(created)} 份画像空壳：{', '.join(created)}")
    if resident:
        print("[ok] 已生成 resident-layer.md（待填）")

    if args.index_only:
        target = build_index(skill_root, data_root)
        print(f"数据根 {data_root}")
        print(f"[ok] 索引已刷新：{rel(data_root, target)}")
        return EXIT_OK

    if args.baseline:
        code = build_baseline(data_root)
        _refresh_index(skill_root, data_root, args)
        return code

    files = list(iter_markdown([skill_root, data_root]))
    print(f"引擎根 {skill_root}")
    print(f"数据根 {data_root}")
    print(f"共 {len(files)} 个 Markdown 文件\n")

    hard, soft = scan_secrets(files)
    broken = scan_links(files)

    if hard:
        print("[x] 发现密钥或敏感标识，必须删掉再提交：")
        for rel_path, lineno, label, masked in hard:
            print(f"    {rel_path}:{lineno}  {label}  {masked}")
    else:
        print("[ok] 没发现密钥或敏感标识")

    if soft:
        print("\n[!] 这些地方像是密钥赋值，请人眼确认（不一定是错）：")
        for rel_path, lineno, label, masked in soft:
            print(f"    {rel_path}:{lineno}  {label}  {masked}")

    if broken:
        print("\n[!] 相对链接指向不存在的文件：")
        for rel_path, target in broken:
            print(f"    {rel_path} -> {target}")
    else:
        print("[ok] 没有断掉的相对链接")

    print("\n画像填充情况（空 = 未启用，不是错误）：")
    empty = []
    for path in profile_files(data_root):
        if is_empty(path):
            print(f"    [--] {path.name}  空")
            empty.append(path.name)
        else:
            print(f"    [ok] {path.name}  已填写")
    if not profile_files(data_root):
        print("    （profile/ 下还没有数据文件）")

    boundaries = data_root / "profile" / "boundaries.md"
    if boundaries.exists():
        text = strip_comments(boundaries.read_text(encoding="utf-8", errors="replace"))
        hard_count = len(re.findall(r"^###\s*\[硬\]", text, re.M))
        if hard_count > 3:
            print(
                f"\n[!] 硬边界有 {hard_count} 条，常驻层最多放 3 条。"
                "只挑最关键的 3 条进 resident-layer.md，其余留在这里。"
            )
        elif hard_count == 0:
            print("\n[!] 还没有任何 [硬] 边界。这是整份画像里最值钱的一块，建议至少写一条。")

    # 模块目录与主文件的模块表要对得上，否则「主文件里查不到这个模块」
    modules = skill_root / "modules"
    if modules.is_dir():
        skill_doc = skill_root / "SKILL.md"
        skill_text = skill_doc.read_text(encoding="utf-8", errors="replace") if skill_doc.exists() else ""
        unlisted = []
        for directory in sorted(modules.iterdir()):
            if not (directory.is_dir() and (directory / "SKILL.md").exists()):
                continue
            row = re.compile(r"^\|\s*`?" + re.escape(directory.name) + r"`?\s*\|", re.M)
            if not row.search(skill_text):
                unlisted.append(directory.name)
        if unlisted:
            print("\n[!] 这些模块没出现在主 SKILL.md 的模块表里：")
            for name in unlisted:
                print(f"    {name}")
            print("    在主文件补一行，否则 Agent 不知道该在什么时候读它。")

    resident = data_root / "resident-layer.md"
    if resident.exists():
        text = strip_comments(resident.read_text(encoding="utf-8", errors="replace"))
        placeholders = re.findall(r"<[^<>\n]{1,40}>", text)
        if placeholders:
            print(f"\n[!] resident-layer.md 还有 {len(placeholders)} 处占位符没填：")
            for item in placeholders:
                print(f"    {item}")
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) > 22:
            print(f"\n[!] 常驻层有 {len(lines)} 行，建议压到 20 行以内——贴满了没人看。")
        print(f"\n常驻层版本：{resident_version(data_root)}　技能版本：{skill_version(skill_root)}")
        print("    常驻层版本的比对对象是「宿主常驻位里粘的那份」，不是技能版本——")
        print("    Agent 在系统提示里看到旧版本号时，提醒用户重粘即可。")

    exit_code = EXIT_OK
    if args.audit:
        print()
        exit_code = audit(data_root)

    _refresh_index(skill_root, data_root, args)

    print()
    if hard:
        print("结果：失败。先删掉上面的密钥，再重新跑一次。")
        print("如果这些值是真的，请立刻吊销并重新签发——它已经进过文件了。")
        return EXIT_FAIL
    if exit_code == EXIT_FAIL:
        print("结果：有改动绕过了写入脚本。")
        return EXIT_FAIL
    if exit_code == EXIT_CANNOT:
        print("结果：无法完成审计——没有基线可比。先跑一次 --baseline。")
        return EXIT_CANNOT

    print("结果：通过。")
    if empty:
        print(f"有 {len(empty)} 份画像是空的，跳过即可；需要时再补。")
    return EXIT_OK


def _refresh_index(skill_root: Path, data_root: Path, args) -> None:
    if args.no_index:
        return
    try:
        target = build_index(skill_root, data_root)
        print(f"[ok] 索引已刷新：{rel(data_root, target)}")
    except OSError as exc:
        print(f"[!] 索引刷新失败：{exc}")


if __name__ == "__main__":
    sys.exit(main())
