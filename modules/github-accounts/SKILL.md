---
name: github-accounts
description: 管理多个 GitHub 账号的身份路由、验活与切换。当需要确认当前是哪个账号、在不同项目间切换账号、或排查认证失败时使用。不含任何 token，也不输出 token。
---

# GitHub 账号路由

## 先读

`profile/my-setup.md` 的「账号清单」给出这个人的账号、用途和路由规则。没填就说明未启用，不要猜。

## 铁律

- **不运行、不输出** `gh auth token` 或 `gh auth status --show-token`。
- 不把 token、PAT、恢复码写进任何文件，包括画像。
- `active` 只是运行状态，**不覆盖**项目或画像里的路由规则。

## 验活

```
gh auth status
gh api user --jq '.login'
```

第二条回读到的 `login` 才是账号身份，显示名不算。

## 路由

写操作前先确认：当前 active 账号 == 这次任务该用的账号。

```
gh auth switch --hostname github.com --user <login>
```

切错了会在别人的仓库里留下提交，所以这一步不省。

## 常见故障

| 现象 | 先查什么 |
| --- | --- |
| `gh: command not found` | 装没装、PATH、是不是 `gh.exe` 包装脚本 |
| 403 / 404 同时出现 | 大概率是账号不对或没权限，不是仓库不存在 |
| push 被拒 | 分支保护、SSH 与 HTTPS 混用、凭据助手拿错账号 |

## 边界

账号可用不等于授权：创建仓库、改可见性、配置 remote、首次 push 都要单独确认。
