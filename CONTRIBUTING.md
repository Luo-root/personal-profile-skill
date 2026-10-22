# 贡献指南

## 这是个什么仓库

**公开的是模板，不是你的画像。** 仓库里只有空壳（`templates/`）和工具（`scripts/`）；
你的画像住在你自己机器上的 skill 目录里，是 untracked 的，git 不会碰它。

所以这个仓库可以放心公开，改它也不会动到任何人的个人数据。

## 两个目录，别搞混

| 目录 | 是什么 | 能不能提交 |
| --- | --- | --- |
| `templates/` | 空壳模板 | 能 |
| `scripts/`、`SKILL.md`、`onboarding.md` | 工具和流程 | 能 |
| `profile/`、`inbox.md`、`resident-layer.md` | **个人数据** | **不能**（`.gitignore` 已挡） |
| `.profile-root` | 本机指针文件 | **不能**（`.gitignore` 已挡） |

如果你在本地做开发，**建议不要在源码副本里放画像**：在副本根目录放一个 `.profile-root`，
内容写 `none`，脚本就认得「这里不含画像」。

## 改完怎么验

```sh
python .selftest/selftest.py     # 三种模式各跑一遍全链路
python scripts/validate.py       # 密钥、死链、空段、占位符
```

自测会造临时的干净工作区，跑完自己清理。

**改文档也算改动**。`onboarding.md` 和 `SKILL.md` 直接决定 Agent 的行为，
自测里有针对它们的行为契约断言（见 `.selftest/selftest.py` 的 `check_doc_contract`），
改之前先看一眼那些断言在断言什么。

## 提 PR 前

1. `python .selftest/selftest.py` 全绿
2. `python scripts/validate.py` 退出码 0
3. 确认 `git status` 里没有 `profile/`、`inbox.md`、`resident-layer.md`、`.profile-root`
4. 版本号按需递增（`SKILL.md` 的 `version:` 和 README 的徽章）

## 不要做的事

- **不要**把任何人的画像、账号、密钥提交进来。`validate.py` 会扫，但别指望它兜底。
- **不要**重排 `profile/` 下的文件名或改小节名——那是已有数据的锚点，改了就得迁移。
- **不要**动 `templates/` 里空壳的小节结构而不做迁移方案。增量加，别重排。

## 改了之后怎么用

模板更新后，skill 安装实例拉一下就行：

```sh
cd <你的 skill 目录> && git pull
```

画像是 untracked 的，`git pull` 不会动它。
