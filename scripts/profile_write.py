#!/usr/bin/env python3
"""画像的唯一写入通道。

为什么要有这个脚本：让 Agent 直接用编辑器改 profile/* 会出三类错——
格式写歪、漏记审批依据、把密钥顺手贴进去。脚本把这三类消灭掉，
并且每写一次都更新哈希基线与索引，事后能查出「谁绕过脚本改了东西」。

目标文件不写死：扫 profile/*.md 自动发现。想加一份新画像，丢一个 .md 进去就行。

用法：
    python scripts/profile_write.py propose --file who-i-am --section 称呼 \
        --text "以后叫我江楠" --why "用户在 2026-10-20 说：以后都叫江楠"

    python scripts/profile_write.py status
    python scripts/profile_write.py apply <id>
    python scripts/profile_write.py decline <id> --reason "不想被记住"
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import (  # noqa: E402
    build_index,
    profile_files,
    read,
    rel,
    write_atomic,
)
from scan_rules import scan_text  # noqa: E402

HEADER = """# 画像待办

由 `scripts/profile_write.py` 维护。不要手改这个文件——手改的东西对不上账。

## 待合并

## 已拒绝
"""


def _utf8_output() -> None:
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


def targets(root: Path) -> dict[str, str]:
    """{文件名词干: profile/xxx.md}，从目录里扫，不写死。"""
    return {path.stem: rel(root, path) for path in profile_files(root)}


def parse_inbox(text: str):
    entries = []
    current = None
    field = None
    for line in text.splitlines():
        if line.startswith("### "):
            if current:
                entries.append(current)
            parts = [p.strip() for p in line[4:].split("·")]
            current = {
                "id": parts[0] if parts else "",
                "date": parts[1] if len(parts) > 1 else "",
                "target": parts[2] if len(parts) > 2 else "",
                "section": parts[3] if len(parts) > 3 else "",
                "text": "",
                "why": "",
                "status": "pending",
                "reason": "",
                "mode": "append",
            }
            field = None
            continue
        if current is None:
            continue
        if line.startswith("- 原文："):
            current["text"] = line[len("- 原文：") :]
            field = "text"
        elif line.startswith("- 依据："):
            current["why"] = line[len("- 依据：") :]
            field = "why"
        elif line.startswith("- 模式："):
            current["mode"] = line[len("- 模式：") :].strip() or "append"
            field = None
        elif line.startswith("- 状态："):
            value = line[len("- 状态：") :].strip()
            if "：" in value:
                status, reason = value.split("：", 1)
                current["status"] = status.strip()
                current["reason"] = reason.strip()
            else:
                current["status"] = value
            field = None
        elif field and line.startswith("  "):
            current[field] += "\n" + line[2:]
        elif not line.strip():
            field = None
    if current:
        entries.append(current)
    return entries


def render_inbox(entries) -> str:
    pending = [e for e in entries if e["status"] != "declined"]
    declined = [e for e in entries if e["status"] == "declined"]

    def block(entry):
        out = [
            f"### {entry['id']} · {entry['date']} · {entry['target']} · {entry['section']}",
            "- 原文：" + entry["text"].replace("\n", "\n  "),
            "- 依据：" + entry["why"].replace("\n", "\n  "),
        ]
        if entry.get("mode", "append") == "replace":
            out.append("- 模式：replace")
        if entry["status"] == "declined":
            reason = entry.get("reason") or "用户拒绝"
            out.append(f"- 状态：declined：{reason}")
        else:
            out.append(f"- 状态：{entry['status']}")
        return "\n".join(out)

    parts = [HEADER.split("## 已拒绝")[0].rstrip(), ""]
    if pending:
        parts.append("\n\n".join(block(e) for e in pending))
        parts.append("")
    parts.append("## 已拒绝")
    parts.append("")
    if declined:
        parts.append("\n\n".join(block(e) for e in declined))
        parts.append("")
    return "\n".join(parts)


def load_state(root: Path):
    path = root / ".profile-state.json"
    if not path.exists():
        return {"version": 1, "files": {}}
    try:
        return json.loads(read(path))
    except json.JSONDecodeError:
        return {"version": 1, "files": {}}


def save_state(root: Path, state) -> None:
    write_atomic(
        root / ".profile-state.json",
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def record_hash(root: Path, state, rel_path: str, entry_id: str) -> None:
    path = root / rel_path
    state.setdefault("files", {})[rel_path] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "updated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "entry": entry_id,
    }
    save_state(root, state)


def write_section(root: Path, rel_path: str, section: str, text: str, replace: bool) -> None:
    """把 text 写进 ## section。

    replace=False 追加到小节末尾；replace=True 整段替换掉小节正文。
    两种都不碰别的小节。
    """
    path = root / rel_path
    if not path.exists():
        raise SystemExit(f"x 目标文件不存在：{rel_path}")
    lines = read(path).splitlines()
    heading = re.compile(r"^##\s+" + re.escape(section) + r"\s*$")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise SystemExit(f"x {rel_path} 里没有小节「{section}」，请先手工建好这一节")

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}\s", lines[j]):
            end = j
            break

    head = lines[: start + 1]
    tail = lines[end:]

    if replace:
        body = ["", text]
    else:
        existing = lines[start + 1 : end]
        while existing and not existing[-1].strip():
            existing.pop()
        body = existing + ["", text] if existing else ["", text]

    new_lines = head + body
    if tail:
        new_lines = new_lines + [""] + tail
    write_atomic(path, "\n".join(new_lines) + "\n")


def cmd_propose(root: Path, args) -> int:
    available = targets(root)
    if args.file not in available:
        raise SystemExit(
            "x 未知目标：{name}\n  现有：{items}\n  想加新的一份，就在 profile/ 下建一个 .md（带 ## 小节），脚本会自动认。".format(
                name=args.file, items=", ".join(available) or "（还没有）"
            )
        )
    if not args.section.strip():
        raise SystemExit("x --section 不能为空，要指定写到哪个小节")
    if not args.text.strip():
        raise SystemExit("x --text 不能为空")
    if not args.why.strip():
        raise SystemExit("x --why 不能为空：每次写入都要留下审批依据")

    hard_text, _ = scan_text(args.text)
    hard_why, _ = scan_text(args.why)
    hard = hard_text + hard_why
    if hard:
        print("x 拒绝写入：文本里像是有密钥。")
        for lineno, label, masked in hard:
            print(f"    第 {lineno} 行  {label}  {masked}")
        print("  凭据不要进画像。需要时只写「去哪取、怎么验活」。")
        return 1

    inbox_path = root / "inbox.md"
    entries = parse_inbox(read(inbox_path)) if inbox_path.exists() else []
    entry_id = hashlib.sha256(
        (args.text + args.why + datetime.datetime.now().isoformat()).encode("utf-8")
    ).hexdigest()[:8]
    entries.append(
        {
            "id": entry_id,
            "date": datetime.date.today().isoformat(),
            "target": args.file,
            "section": args.section.strip(),
            "text": args.text.strip(),
            "why": args.why.strip(),
            "status": "pending",
            "reason": "",
            "mode": "replace" if args.replace else "append",
        }
    )
    write_atomic(inbox_path, render_inbox(entries))
    print(f"[ok] 已记进 inbox：{entry_id}")
    print(f"     目标：{available[args.file]} -> ## {args.section}")
    print(f"     合并：python scripts/profile_write.py apply {entry_id}")
    return 0


def _find(root: Path, entry_id: str):
    inbox_path = root / "inbox.md"
    if not inbox_path.exists():
        raise SystemExit("x 还没有 inbox.md")
    entries = parse_inbox(read(inbox_path))
    match = next((e for e in entries if e["id"] == entry_id), None)
    if match is None:
        raise SystemExit(f"x 找不到条目 {entry_id}")
    return entries, match


def cmd_apply(root: Path, args) -> int:
    entries, entry = _find(root, args.id)
    if entry["status"] == "declined":
        raise SystemExit("x 这条已经被拒绝，不能合并")
    if entry["status"] == "applied":
        raise SystemExit("x 这条已经合并过了")

    available = targets(root)
    if entry["target"] not in available:
        raise SystemExit(f"x 目标文件已经不存在了：{entry['target']}")

    rel_path = available[entry["target"]]
    write_section(root, rel_path, entry["section"], entry["text"], entry.get("mode") == "replace")
    entry["status"] = "applied"
    write_atomic(root / "inbox.md", render_inbox(entries))

    state = load_state(root)
    record_hash(root, state, rel_path, entry["id"])
    build_index(root)

    print(f"[ok] 已合并进 {rel_path} -> ## {entry['section']}")
    print(f"     哈希已记入 .profile-state.json（条目 {entry['id']}），索引已刷新")
    return 0


def cmd_decline(root: Path, args) -> int:
    entries, entry = _find(root, args.id)
    if entry["status"] == "applied":
        raise SystemExit("x 已经合并进画像了，要撤销得直接改 profile/ 并重建基线")
    entry["status"] = "declined"
    entry["reason"] = args.reason or "用户拒绝"
    write_atomic(root / "inbox.md", render_inbox(entries))
    print(f"[ok] 已标记拒绝：{entry['id']}")
    print("     以后不要再提同一条。")
    return 0


def cmd_status(root: Path, args) -> int:
    inbox_path = root / "inbox.md"
    if not inbox_path.exists():
        print("还没有 inbox.md")
        return 0
    entries = parse_inbox(read(inbox_path))
    if not entries:
        print("inbox 是空的")
        return 0

    def show(title, items):
        if not items:
            return
        print(f"\n{title}（{len(items)}）")
        for e in items:
            print(f"  {e['id']}  {e['date']}  {e['target']} · {e['section']}")
            print(f"        {e['text'].splitlines()[0]}")

    show("待合并", [e for e in entries if e["status"] == "pending"])
    show("已合并", [e for e in entries if e["status"] == "applied"])
    show("已拒绝", [e for e in entries if e["status"] == "declined"])
    return 0


def main() -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(description="画像的唯一写入通道")
    parser.add_argument("--root", default=None, help="画像根目录，默认是脚本的上一级")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="提议一条，写进 inbox")
    p.add_argument("--file", required=True, help="目标文件名词干，如 who-i-am")
    p.add_argument("--section", required=True, help="写进哪个 ## 小节")
    p.add_argument("--text", required=True, help="原文，逐字")
    p.add_argument("--why", required=True, help="审批依据：用户哪句话")
    p.add_argument(
        "--replace",
        action="store_true",
        help="整段替换该小节，而不是追加（改口、纠正时用）",
    )

    a = sub.add_parser("apply", help="把条目合并进 profile")
    a.add_argument("id")

    d = sub.add_parser("decline", help="标记为拒绝")
    d.add_argument("id")
    d.add_argument("--reason", default="")

    sub.add_parser("status", help="列出 inbox")

    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    if not root.is_dir():
        raise SystemExit(f"x 不是一个目录：{root}")

    handler = {
        "propose": cmd_propose,
        "apply": cmd_apply,
        "decline": cmd_decline,
        "status": cmd_status,
    }[args.command]
    return handler(root, args)


if __name__ == "__main__":
    sys.exit(main())
