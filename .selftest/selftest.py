#!/usr/bin/env python3
"""自测：模拟一次全新 clone，跑通「加载 -> 写入 -> 审计」全链路。

用 `.selftest/fresh/` 造一个只含模板、不含 profile/ 的干净工作区，
逐条验证脚本行为是否符合约定。任何一条不符就打印 FAIL 并以非 0 退出。

跑法：python .selftest/selftest.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# 每次跑用一个新的干净目录，���免上一轮的改动污染下一轮
FRESH = REPO / ".selftest" / ("fresh-" + datetime.now().strftime("%H%M%S-%f"))

# 新 clone 里应该有的东西（模板 + 脚本 + 文档），不含 profile/ 与个人数据
CLONE_CONTENT = [
    "SKILL.md",
    "onboarding.md",
    "README.md",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    "scripts",
    "templates",
    "modules",
    "assets",
]

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  —— {detail}" if detail else ""))


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / args[0]), *args[1:], "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def make_fresh() -> Path:
    if FRESH.exists():
        return FRESH
    FRESH.mkdir(parents=True)
    for item in CLONE_CONTENT:
        source = REPO / item
        if not source.exists():
            continue
        target = FRESH / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return FRESH


def main() -> int:
    root = make_fresh()

    # --- 全新工作区：profile/ 根本不存在
    check("全新 clone 里没有 profile/", not (root / "profile").exists())

    # 1. --index-only：只重建索引，应该顺带把空壳铺好
    result = run(root, "validate.py", "--index-only")
    check("--index-only 退出码 0", result.returncode == 0, f"实际 {result.returncode}: {result.stdout[-200:]}")
    check("--index-only 生成索引", (root / "profile" / "_index.md").exists())
    shells = [p for p in (root / "profile").glob("*.md") if not p.name.startswith("_")]
    check(
        "--index-only 铺好 6 份空壳",
        len(shells) == 6,
        f"实际 {len(shells)} 份",
    )
    noise = [w for w in ("扫描", "画像填充情况", "没发现密钥", "断掉的相对链接") if w in result.stdout]
    check("--index-only 不做全量体检（无噪音输出）", not noise, f"出现噪音 {noise}")

    # 2. 空模板不该被判成「已填写」
    index = (root / "profile" / "_index.md").read_text(encoding="utf-8")
    check("空壳索引显示全部为空", index.count("| 空 |") == 6, f"实际 {index.count('| 空 |')} 个空")

    # 3. 全量自检：空段是正常状态，不该失败
    result = run(root, "validate.py")
    check("全量自检退出码 0", result.returncode == 0, f"实际 {result.returncode}")

    # 4. 没有基线时 --audit 必须是「无法执行」，不能伪装成通过
    result = run(root, "validate.py", "--audit")
    check("--audit 无基线返回 2（假干净已修）", result.returncode == 2, f"实际 {result.returncode}")

    # 5. 建基线后 --audit 应该干净
    result = run(root, "validate.py", "--baseline")
    check("--baseline 退出码 0", result.returncode == 0, f"实际 {result.returncode}")
    result = run(root, "validate.py", "--audit")
    check("--audit 有基线返回 0", result.returncode == 0, f"实际 {result.returncode}")

    # 6. 写入链路：propose -> apply
    result = run(
        root,
        "profile_write.py",
        "propose",
        "--file",
        "who-i-am",
        "--section",
        "称呼",
        "--text",
        "以后叫我江楠",
        "--why",
        "用户说：以后都叫江楠",
    )
    check("propose 退出码 0", result.returncode == 0, result.stdout[-200:])
    entry_id = ""
    for line in result.stdout.splitlines():
        if "已记进 inbox" in line:
            entry_id = line.split("：")[-1].strip()
    check("propose 产生条目 id", bool(entry_id), entry_id)

    result = run(root, "profile_write.py", "apply", entry_id)
    check("apply 退出码 0", result.returncode == 0, result.stdout[-200:])
    who = (root / "profile" / "who-i-am.md").read_text(encoding="utf-8")
    check("apply 内容落到 ## 称呼", "以后叫我江楠" in who)

    # 7. 绕过脚本手改 -> 审计必须抓到
    who_path = root / "profile" / "who-i-am.md"
    who_path.write_text(who + "\n手改的一行\n", encoding="utf-8")
    result = run(root, "validate.py", "--audit")
    check("手改被审计抓到（退出码 1）", result.returncode == 1, f"实际 {result.returncode}")

    # 8. 新画像没有模板时应明确报错，而不是静默乱写
    result = run(
        root,
        "profile_write.py",
        "propose",
        "--file",
        "no-such-profile",
        "--section",
        "x",
        "--text",
        "t",
        "--why",
        "w",
    )
    check("无模板的新画像被拒绝", result.returncode != 0, f"实际 {result.returncode}")
    check("拒绝时说明了怎么办", "templates" in (result.stdout + result.stderr), result.stdout[-200:])

    # 9. --root 在子命令前后都要能用（两个脚本用法一致）
    pre = subprocess.run(
        [sys.executable, str(root / "scripts" / "profile_write.py"), "--root", str(root), "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    check("--root 在子命令之前可用", pre.returncode == 0, f"实际 {pre.returncode}: {pre.stderr[-200:]}")
    post = run(root, "profile_write.py", "status")
    check("--root 在子命令之后可用", post.returncode == 0, f"实际 {post.returncode}: {post.stderr[-200:]}")

    # 10. 状态文件结构
    state = json.loads((root / ".profile-state.json").read_text(encoding="utf-8"))
    check("基线记录了 6 份画像", len(state.get("files", {})) == 6, str(len(state.get("files", {}))))

    # 11. .gitignore 正确性——模板不能被误屏蔽，个人数据必须被挡住
    #     这条曾经真的出过一次事故：`profile/` 不带前导斜杠会连 templates/profile/ 一起屏蔽，
#     公开仓库就会变成没有模板的空壳，而且 git 不会报任何错。
    ignored = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v",
         "templates/profile/who-i-am.md", "templates/resident-layer.md"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check("模板没有被 .gitignore 误屏蔽", ignored.returncode != 0, ignored.stdout.strip()[:200])

    blocked = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v",
         "profile/who-i-am.md", "inbox.md", "resident-layer.md"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check("个人数据确实被 .gitignore 挡住", blocked.returncode == 0, blocked.stdout.strip()[:200])

    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    leaked = [
        p for p in tracked.stdout.splitlines()
        if p.startswith("profile/") or p in ("inbox.md", "resident-layer.md")
    ]
    check("git 跟踪的文件里没有个人数据", not leaked, str(leaked))

    print()
    failed = [name for name, ok, _ in results if not ok]
    print(f"合计 {len(results)} 条，通过 {len(results) - len(failed)} 条")
    if failed:
        print("失败：")
        for name in failed:
            print(f"  - {name}")
    else:
        print("全部通过。")

    # 收尾：删掉这次造的干净工作区（已经在 .gitignore 里，但别留垃圾）
    try:
        shutil.rmtree(FRESH, ignore_errors=True)
    except Exception as exc:  # pragma: no cover
        print(f"[!] 临时目录没删掉，手动清一下：{FRESH}（{exc}）")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
