# Sanmu-Skill

Sanmu 的个人 Skills 集合，用于统一管理和分发 Codex 等 Agent 工具的技能。

## 当前 Skills

| Skill | 用途 | 目录 |
| --- | --- | --- |
| `keylol-post-converter` | 将 Markdown 或纯文本转换为其乐论坛 BBCode | [`skills/keylol-post-converter`](skills/keylol-post-converter) |
| `personal-game-review-prose` | 将已确认的真实体验整理成中文游戏评测 | [`skills/personal-game-review-prose`](skills/personal-game-review-prose) |
| `interview-game-review` | 通过采访、观点账本和盲点扫描协助完成游戏评测 | [`skills/interview-game-review`](skills/interview-game-review) |

## 目录结构

每个 Skill 都是独立目录，目录内保留自己的 `SKILL.md`、`agents`、参考资料和脚本：

```text
skills/
├── keylol-post-converter/
├── personal-game-review-prose/
└── interview-game-review/
```

## 在 CC Switch 中使用

在 CC Switch 的 Skills → 仓库管理中添加本仓库：

```text
https://github.com/Fusanmu/Sanmu-Skill
分支：main
```

刷新技能列表后即可分别安装和管理这 3 个 Skill。CC Switch 会根据各目录中的 `SKILL.md` 发现技能。

## 维护方式

本仓库是这 3 个 Skill 的唯一源仓库。以后请直接修改对应的 `skills/<skill-name>/` 目录并提交；CC Switch 刷新后即可发现更新。

原来的 3 个独立仓库仅保留历史内容，已经迁移为私有归档仓库，不再参与日常维护。总仓库不再从其他仓库自动同步，因此在这里的修改不会被覆盖。
