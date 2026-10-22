<p align="center">
  <img src="assets/logo.svg" width="104" height="104" alt="personal-profile-skill">
</p>

<h1 align="center">personal-profile-skill</h1>

<p align="center">
  一份能被 Agent 读懂、能跟着你走的<strong>个人画像</strong>。<br>
  换 Agent、换电脑、换工具，不用再从零解释你是谁。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.4.0-4f46e5" alt="version">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-555" alt="platform">
  <img src="https://img.shields.io/badge/format-Agent%20Skill-0ea5e9" alt="format">
</p>

<p align="center">
  <a href="https://github.com/Luo-root/personal-profile-skill/stargazers"><img src="https://img.shields.io/github/stars/Luo-root/personal-profile-skill?style=social" alt="Stars"></a>
  <a href="https://github.com/Luo-root/personal-profile-skill/graphs/contributors"><img src="https://img.shields.io/github/contributors/Luo-root/personal-profile-skill?style=social" alt="Contributors"></a>
</p>

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

## 两个地方，画像和模板各归各位

**① 公开模板仓库**（GitHub 上这个，以及你本地的源码副本）

```
SKILL.md  onboarding.md  scripts/  templates/  modules/  assets/
```

这里**只有模板，一行个人数据都没有**。你可以随便改、随便推。

**② 你本机装的 skill**（Agent 真正读画像的地方）

```
<skills>/personal-profile-skill/
  SKILL.md  scripts/  templates/  modules/      ← 跟仓库一样，是模板
  profile/                  ← 你的画像在这里
  inbox.md
  resident-layer.md
  .profile-state.json
```

**画像住在 skill 目录里，但它是 untracked 的**——`git pull` 更新模板时，git 不会碰它。
所以：公开仓库干净，画像却一直跟着 skill 走。

**③ 源码副本里不放画像。** 你本地那份仓库副本（改代码用）里放一个 `.profile-root` 文件，
内容就一个词 `none`：

```
none
```

这是给工具看的声明：**「这里不含画像」**。脚本认得它——在这个目录跑自检只查技能本体，
不会默默铺一份空画像出来；想在这儿写画像会被直接拒绝，并告诉你该去哪操作。

## 四步跑起来

1. **拿到模板**：下载这个仓库（zip 或 clone 都行），放到一个你找得到的位置。
2. **让 Agent 采集**：对新 Agent 说「读 `SKILL.md` 和 `onboarding.md`，帮我建个人画像」。阶段 1 只问 5 个问题，**每阶段问完就落盘**，中途停下也不丢。
3. **装进你的 Agent**：
   - **magpie**：Library → 技能 → 新增 → 来源选**本机文件夹**，指向这个目录。不用另外建仓库。
   - **MiniMax Code**：`git clone` 到 `~/.minimax/skills/personal-profile-skill/`。
   - 别的宿主按各自的 skill 安装方式装，**装好后确认它指向的是这个目录**，不是某份拷贝。
4. **贴常驻层**：把生成的 `resident-layer.md` 粘进宿主的常驻位——magpie 的「指令」，
   MiniMax Code 的 `AGENTS.md` 或用户级 Memory。

第 3、4 步的菜单名以你当前那个宿主的版本为准。

### MiniMax Code 的安装命令

```powershell
git clone https://github.com/Luo-root/personal-profile-skill.git "$env:USERPROFILE\.minimax\skills\personal-profile-skill"
```

macOS / Linux：

```sh
git clone https://github.com/Luo-root/personal-profile-skill.git ~/.minimax/skills/personal-profile-skill
```

装完跑一次验证——它应该报出画像有几份启用：

```sh
python ~/.minimax/skills/personal-profile-skill/scripts/validate.py
```

## 怎么加载

Agent 不会一次读全量：

1. 先读 `profile/_index.md`——脚本生成的索引，一份一行：启用/空、一句话、最后修改
2. 按任务只展开需要的那一两份
3. 能回答当前问题就停手

索引由脚本生成，不手写，所以不会漂。索引不存在或过期时跑
`python scripts/validate.py --index-only` 重建——**只重建索引，不做全量体检**。
机器上没有 Python 也能读：列 `profile/` 下的文件，看每份的小节有没有正文。


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
python scripts/validate.py                 # 全量自检
python scripts/validate.py --index-only    # 只重建索引（Agent 加载时用这条）
python scripts/validate.py --baseline      # 建哈希基线
python scripts/validate.py --audit         # 比基线，查有没有绕过脚本
```

全量自检查密钥误贴、死链、空段统计、硬边界条数、常驻层行数，并刷新索引。
**只把密钥当失败**——空段是正常情况，不是缺陷。

退出码有契约，脚本化调用按它判断：

| 退出码 | 含义 |
| --- | --- |
| `0` | 通过 |
| `1` | 失败——发现密钥，或审计查出绕过脚本的改动 |
| `2` | 无法执行——目录不存在、用法错误、`--audit` 时还没有基线 |

`--audit` 在没有基线时返回 `2` 而不是 `0`：**「没审过」不等于「审过了干净」。**

自测套件在 `.selftest/selftest.py`，会造一个「模拟新 clone」的干净工作区跑完整链路：

```sh
python .selftest/selftest.py
```

## 改模板 / 升级模板

日常只有两件事，各在各的地方做：

| 想干什么 | 在哪做 | 做完之后 |
| --- | --- | --- |
| 改 skill 本体（SKILL.md、scripts、templates） | 源码副本 | 提交 → 推送 → 到安装实例 `git pull` |
| 改自己的画像 | 安装实例（或用脚本写） | 画像是 untracked，pull 不会碰它 |

**`git pull` 更新模板时，画像是安全的**——它不在 git 跟踪范围里，git 不会碰 untracked 文件。
就算哪次升级真的动了画像的目录结构，也只会让脚本找不到（然后明确报错），
不会**静默改坏**你已有的内容。

模板定型之后建议**少动结构**：要改就增量加，别重排目录、别改小节名——
画像里的小节名（`## 称呼` 这类）是数据的锚点，改了就得迁移。

`profile/_index.md` 是派生物，可以删，下次跑 `--index-only` 会自动重建。

## 许可证

MIT。拿去改、拿去用，保留版权声明即可。

## 目录

| 路径 | 作用 | 在公开仓库里？ |
| --- | --- | --- |
| `SKILL.md` | 加载规则 + 写入协议 | 是 |
| `onboarding.md` | 首次采集脚本 | 是 |
| `templates/profile/` | 六份画像的空壳 | 是 |
| `templates/resident-layer.md` | 常驻层空壳 | 是 |
| `modules/` | 可选能力包，默认不用装 | 是 |
| `assets/logo.svg` | 项目图标 | 是 |
| `LICENSE` | MIT | 是 |
| `scripts/profile_write.py` | 唯一写入通道 | 是 |
| `scripts/validate.py` | 自检 + 基线比对 + 刷新索引 | 是 |
| `scripts/profile_lib.py` | 文件发现、空判定、索引生成、模板初始化、数据根解析（共用） | 是 |
| `scripts/scan_rules.py` | 密钥特征（共用） | 是 |
| `.selftest/selftest.py` | 自测套件（三种模式各跑一遍全链路） | 是 |
| `.profile-root` | 本机文件：写 `none` = 本副本不含画像 | 否（gitignore） |
| `profile/` | **你的**画像真相源（住在 skill 安装实例里） | 否 |
| `profile/_index.md` | 索引（脚本生成） | 否 |
| `resident-layer.md` | **你的**常驻层（生成物，带版本号） | 否 |
| `inbox.md` | **你的**待合并 / 已拒绝 | 否 |
| `.profile-state.json` | 哈希基线（脚本自动维护） | 否 |

## ⭐ 支持 personal-profile-skill

让 Agent 一次读懂你：可随 magpie 迁移的个人画像 skill 模板。

如果你也遇到过「换 Agent 就要重新解释一遍自己」，Star 一下能帮它被更多人看到 —— 对个人维护的开源项目帮助很大。

- 遇到问题或想要功能：[提交 issue](https://github.com/Luo-root/personal-profile-skill/issues)
- 觉得好用但暂时没需求：点右上角的 ⭐ 就够了
- 想参与开发：[贡献指南](CONTRIBUTING.md)
