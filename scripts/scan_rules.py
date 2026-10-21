"""密钥与敏感标识的判定规则。

`validate.py` 和 `profile_write.py` 共用这一份，避免「检查时用一套、写入时用另一套」。
文件名不用 secrets.py——那是 Python 标准库的模块名，会被抢先导入。
"""

from __future__ import annotations

import re

# 命中即失败
HARD_PATTERNS = [
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("GitHub PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("通用 sk- 密钥", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("带口令的 URL", re.compile(r"https?://[^\s/:@]+:[^\s/@]+@")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
]

# 只提示，不失败：可能是误报，比如「凭据位置」这类说明文字
SOFT_PATTERNS = [
    (
        "疑似密钥赋值",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"
        ),
    ),
]


def mask(value: str) -> str:
    """只露头几个字符，避免把密钥打到终端和日志里。"""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:4]}...({len(value)} chars)"


def scan_text(text: str):
    """返回 (hard_hits, soft_hits)，元素是 (行号, 类别, 脱敏后的值)。"""
    hard, soft = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern in HARD_PATTERNS:
            for match in pattern.finditer(line):
                hard.append((lineno, label, mask(match.group(0))))
        for label, pattern in SOFT_PATTERNS:
            for match in pattern.finditer(line):
                soft.append((lineno, label, mask(match.group(0))))
    return hard, soft
