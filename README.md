# personal-profile-skill

一份能被 Agent 读懂、能跟着你走的**个人画像**。换 Agent、换电脑、换工具，不用再从零解释你是谁。

当前版本 **0.2.0**。

## 它解决什么

Agent 的能力可以迁移——网关配置、MCP、技能都能同步。但**你这个人**带不走。新装一个 Agent，它不知道该怎么称呼你、喜欢多长的回答、哪些事必须先问你、你的仓库和服务器在哪。

这份画像就补这一块。它带的是**说明书**，不是**钥匙**。

## 为什么不放密码

skill 会被 Agent 读进上下文，而上下文会发到模型供应商。换 Agent 常常就是换了供应商或中转站——密钥写进去，等于把钥匙挨家挨户发一遍。而且备份解密后还会明文落在每台机器上。

所以分三类：

| 类型 | 内容 | 去哪 |
| --- | --- | --- |
| 可以随便读 | 身份、沟通偏好、授权边界、环境摘要 | 进画像，Agent 可读可引用 |
| 默认不读 | 生活、健康、收入、家庭 | 进画像，但你明确要求时才打开 |
| 永不入文件 | 密码、私钥、token、身份证 | 只写「去哪取」 |

凭据本身放在 Bitwarden、系统钥匙串、`gh` 的 keyring 里。画像只记接线图——那份接线图叫 `profile/restore-my-access.md`，是整套东西里最有用的一份。

## 四步跑起来

1. **拿到模板**：下载这个仓库（zip 或 clone 都行），放到一个你找得到的位置。
2. **让 Agent 采集**：对新 Agent 说「读 `SKILL.md` 和 `onboarding.md`，帮我建个人画像」。阶段 1 只问 5 个问题，**每阶段问完就落盘**，中途停下也不丢。
3. **加进 magpie**：Library → 技能 → 新增 → 来源选**本机文件夹**，指向这个目录。不用另外建仓库。
4. **贴常驻层**：把生成的 `resident-layer.md` 粘进 magpie 的「指令」，选给哪些 Agent。

第 3、4 步的菜单名以你当前的 magpie 版本为准。

## 怎么加载

Agent 不会一次读全量：

1. 先读 `profile/_index.md`——脚本生成的索引，一份一行：启用/空、一句话、最后修改
2. 按任务只展开需要的那一两份
3. 能回答当前问题就停手

索引由脚本生成，不手写，所以不会漂。

## 之后怎么维护

- Agent 发现新偏好 → 向你提议 → 你批准 → 进 `inbox.md` → 定期合并进 `profile/`
- 随时可以说「把这个记下来」，走同一套审批
- 说「不记」的会进 `declined`，以后不会再被同一件事打扰

## 写入只有一条通道

不要手改 `profile/*`，用脚本：

```sh
python scripts/profile_write.py propose --file who-i-am --section 称呼 --text "..." --why "用户说：..."
python scripts/profile_write.py status
python scripts/profile_write.py apply <id>
python scripts/profile_write.py decline <id> --reason "..."
```

它能拦住三类常见错误：密钥误贴、漏记审批依据、格式写歪。每次写入都会刷新 `.profile-state.json` 里的哈希和 `profile/_index.md`。

目标文件**不写死**：脚本扫 `profile/*.md` 自动认，想加一份新画像，丢一个带 `##` 小节的 `.md` 进去就行。

**它挡不住绕过脚本直接改文件**，但能查出来：

```sh
python scripts/validate.py --baseline   # 第一次建基线
python scripts/validate.py --audit      # 以后查有没有绕过去改
```

审计到未经脚本的改动会退出码 1 并点名文件。要不要回滚由你决定——脚本不自动改你的东西。

## 版本与漂移

- `SKILL.md` 的 `version:` 是技能版本
- `resident-layer.md` 末尾有一行 `常驻层 vN`，那是**你粘进 magpie 的那份**的版本
- 改了边界就要同步改 `resident-layer.md` 并把 `vN` 加一，然后重新粘贴

Agent 如果发现系统提示里的版本比文件里的旧，会提醒你重粘。这是唯一能发现「magpie 里粘的是旧版」的办法。

## 校验

```sh
python scripts/validate.py
```

查密钥误贴、死链、空段统计、硬边界条数、常驻层行数，并刷新索引。**只把密钥当失败**——空段是正常情况，不是缺陷。

## 升级模板

模板没有内置升级机制，但模板和你的数据分在两个地方：

| 模板文件（可整体替换） | 你的数据（替换时保留） |
| --- | --- |
| `SKILL.md`、`onboarding.md`、`modules/README.md`、`scripts/` | `profile/*`（保留）、`inbox.md`、`resident-layer.md` |

换新版时只覆盖左列，右列别动。`profile/_index.md` 是派生物，可以删，下次跑校验会自动重建。

## 目录

| 路径 | 作用 |
| --- | --- |
| `SKILL.md` | 加载规则 + 写入协议 |
| `onboarding.md` | 首次采集脚本 |
| `resident-layer.md` | 常驻层（生成物，带版本号；给人拷进 magpie，Agent 不读） |
| `profile/` | 画像真相源 |
| `profile/_index.md` | 索引（脚本生成） |
| `modules/` | 可选能力包，默认不用装 |
| `inbox.md` | 待合并 / 已拒绝 |
| `scripts/profile_write.py` | 唯一写入通道 |
| `scripts/validate.py` | 自检 + 基线比对 + 刷新索引 |
| `scripts/profile_lib.py` | 文件发现、空判定、索引生成（共用） |
| `scripts/scan_rules.py` | 密钥特征（共用） |
| `.profile-state.json` | 哈希基线（脚本自动维护） |
