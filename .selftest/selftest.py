#!/usr/bin/env python3
"""自测：跑通「加载 -> 写入 -> 审计」全链路，两种布局都验一遍。

布局一（单目录）：画像和技能放一起，没有指针文件——老的用法，照旧能跑。
布局二（双根）：技能是纯引擎，画像在另一个目录，靠 `.profile-root` 指针指过去。

每种布局都造一份「模拟新 clone」的干净环境再逐条断言。
任何一条不符就打印 FAIL 并以非 0 退出。

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
STAGE = REPO / ".selftest"

# 新 clone 里应该有的东西（引擎侧），不含 profile/ 与个人数据
ENGINE_CONTENT = [
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
    """跑脚本。不传 --root——让它自己按 .profile-root 指针找数据根，这才是真实用法。"""
    return subprocess.run(
        [sys.executable, str(root / "scripts" / args[0]), *args[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def make_engine(tag: str) -> Path:
    """造一份干净的引擎根（模拟新 clone）。"""
    engine = STAGE / f"engine-{tag}-{datetime.now().strftime('%H%M%S-%f')}"
    engine.mkdir(parents=True)
    for item in ENGINE_CONTENT:
        source = REPO / item
        if not source.exists():
            continue
        target = engine / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return engine


def make_data(tag: str) -> Path:
    """造一份独立的数据根。"""
    data = STAGE / f"data-{tag}-{datetime.now().strftime('%H%M%S-%f')}"
    data.mkdir(parents=True)
    return data


def run_suite(layout: str) -> None:
    print(f"\n{'=' * 60}\n布局：{layout}\n{'=' * 60}")

    engine = make_engine(layout)
    if layout == "single":
        data = engine
    else:
        data = make_data(layout)
        (engine / ".profile-root").write_text(str(data) + "\n", encoding="utf-8")

    # --- 全新工作区：画像文件根本不存在
    check(f"[{layout}] 全新 clone 里没有 profile/", not (engine / "profile").exists())

    # 1. --index-only：只重建索引，应该顺带把空壳铺好
    result = run(engine, "validate.py", "--index-only")
    check(f"[{layout}] --index-only 退出码 0", result.returncode == 0, f"实际 {result.returncode}: {result.stdout[-200:]}")
    check(f"[{layout}] 索引写在数据根", (data / "profile" / "_index.md").exists())
    shells = [p for p in (data / "profile").glob("*.md") if not p.name.startswith("_")]
    check(f"[{layout}] 铺好 6 份空壳", len(shells) == 6, f"实际 {len(shells)} 份")
    noise = [w for w in ("扫描", "画像填充情况", "没发现密钥", "断掉的相对链接") if w in result.stdout]
    check(f"[{layout}] --index-only 不做全量体检", not noise, f"出现噪音 {noise}")
    if layout == "split":
        check("[split] 引擎根里没有长出 profile/", not (engine / "profile").exists())
        check("[split] 指针文件被识别", str(data) in result.stdout, result.stdout[:120])

    # 2. 空模板不该被判成「已填写」
    index = (data / "profile" / "_index.md").read_text(encoding="utf-8")
    check(f"[{layout}] 空壳索引显示全部为空", index.count("| 空 |") == 6, f"实际 {index.count('| 空 |')} 个空")

    # 3. 全量自检：空段是正常状态，不该失败
    result = run(engine, "validate.py")
    check(f"[{layout}] 全量自检退出码 0", result.returncode == 0, f"实际 {result.returncode}")

    # 4. 没有基线时 --audit 必须是「无法执行」，不能伪装成通过
    result = run(engine, "validate.py", "--audit")
    check(f"[{layout}] --audit 无基线返回 2", result.returncode == 2, f"实际 {result.returncode}")

    # 5. 建基线后 --audit 应该干净
    result = run(engine, "validate.py", "--baseline")
    check(f"[{layout}] --baseline 退出码 0", result.returncode == 0, f"实际 {result.returncode}")
    result = run(engine, "validate.py", "--audit")
    check(f"[{layout}] --audit 有基线返回 0", result.returncode == 0, f"实际 {result.returncode}")

    # 6. 写入链路：propose -> apply
    result = run(
        engine,
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
    check(f"[{layout}] propose 退出码 0", result.returncode == 0, result.stdout[-200:])
    entry_id = ""
    for line in result.stdout.splitlines():
        if "已记进 inbox" in line:
            entry_id = line.split("：")[-1].strip()
    check(f"[{layout}] propose 产生条目 id", bool(entry_id), entry_id)

    result = run(engine, "profile_write.py", "apply", entry_id)
    check(f"[{layout}] apply 退出码 0", result.returncode == 0, result.stdout[-200:])
    who = (data / "profile" / "who-i-am.md").read_text(encoding="utf-8")
    check(f"[{layout}] apply 内容落到 ## 称呼", "以后叫我江楠" in who)
    check(f"[{layout}] inbox 写在数据根", (data / "inbox.md").exists())
    check(f"[{layout}] 哈希基线写在数据根", (data / ".profile-state.json").exists())

    # 7. 绕过脚本手改 -> 审计必须抓到
    who_path = data / "profile" / "who-i-am.md"
    who_path.write_text(who + "\n手改的一行\n", encoding="utf-8")
    result = run(engine, "validate.py", "--audit")
    check(f"[{layout}] 手改被审计抓到（退出码 1）", result.returncode == 1, f"实际 {result.returncode}")

    # 8. 数据根里的密钥必须被扫到（密钥扫描要覆盖数据根，不能只扫引擎）
    leak = data / "profile" / "how-to-talk.md"
    leak.write_text("# 怎么跟我说话\n\n## 汇报格式\n\nghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n", encoding="utf-8")
    result = run(engine, "validate.py")
    check(f"[{layout}] 数据根里的密钥被扫到", result.returncode == 1 and "发现密钥" in result.stdout, f"实际 {result.returncode}")

    # 9. 新画像没有模板时应明确报错，而不是静默乱写
    result = run(
        engine,
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
    check(f"[{layout}] 无模板的新画像被拒绝", result.returncode != 0, f"实际 {result.returncode}")
    check(f"[{layout}] 拒绝时说明了怎么办", "templates" in (result.stdout + result.stderr), result.stdout[-200:])

    # 10. --root 在子命令前后都要能用（两个脚本用法一致）
    pre = subprocess.run(
        [sys.executable, str(engine / "scripts" / "profile_write.py"), "--root", str(data), "status"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check(f"[{layout}] --root 在子命令之前可用", pre.returncode == 0, f"实际 {pre.returncode}: {pre.stderr[-200:]}")
    post = run(engine, "profile_write.py", "status")
    check(f"[{layout}] --root 在子命令之后可用", post.returncode == 0, f"实际 {post.returncode}: {post.stderr[-200:]}")

    # 11. 状态文件结构
    state = json.loads((data / ".profile-state.json").read_text(encoding="utf-8"))
    check(f"[{layout}] 基线记录了 6 份画像", len(state.get("files", {})) == 6, str(len(state.get("files", {}))))

    shutil.rmtree(engine, ignore_errors=True)
    if data != engine:
        shutil.rmtree(data, ignore_errors=True)


def check_repo_hygiene() -> None:
    """仓库层面的检查：模板没被误屏蔽、个人数据确实被挡住。"""
    print(f"\n{'=' * 60}\n仓库卫生\n{'=' * 60}")

    # 这条曾经真的出过一次事故：`profile/` 不带前导斜杠会连 templates/profile/ 一起屏蔽，
    # 公开仓库就会变成没有模板的空壳，而且 git 不会报任何错。
    ignored = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v",
         "templates/profile/who-i-am.md", "templates/resident-layer.md"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check("模板没有被 .gitignore 误屏蔽", ignored.returncode != 0, ignored.stdout.strip()[:200])

    blocked = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v",
         "profile/who-i-am.md", "inbox.md", "resident-layer.md", ".profile-root"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check("个人数据与指针文件确实被 .gitignore 挡住", blocked.returncode == 0, blocked.stdout.strip()[:200])

    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    leaked = [
        p for p in tracked.stdout.splitlines()
        if p.startswith("profile/") or p in ("inbox.md", "resident-layer.md", ".profile-root")
    ]
    check("git 跟踪的文件里没有个人数据", not leaked, str(leaked))


def main() -> int:
    run_suite("single")
    run_suite("split")
    check_repo_hygiene()

    print()
    failed = [name for name, ok, _ in results if not ok]
    print(f"合计 {len(results)} 条，通过 {len(results) - len(failed)} 条")
    if failed:
        print("失败：")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
