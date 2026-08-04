# Sanmu-Skill

Sanmu 的个人 Skills 集合，用于统一管理和分发 Codex 等 Agent 工具的技能。

## 当前 Skills

| Skill | 用途 | 源仓库 |
| --- | --- | --- |
| `keylol-post-converter` | 将 Markdown 或纯文本转换为其乐论坛 BBCode | [Fusanmu/keylol-post-converter](https://github.com/Fusanmu/keylol-post-converter) |
| `personal-game-review-prose` | 将已确认的真实体验整理成中文游戏评测 | [Fusanmu/personal-game-review-prose](https://github.com/Fusanmu/personal-game-review-prose) |
| `interview-game-review` | 通过采访、观点账本和盲点扫描协助完成游戏评测 | [Fusanmu/interview-game-review](https://github.com/Fusanmu/interview-game-review) |

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

## 更新机制

原来的 3 个仓库是源仓库，内容更新后由 `.github/workflows/sync-skills.yml` 定期同步到这里。也可以在 GitHub Actions 中手动运行 `Sync skills from upstream`。

同步完成后，在 CC Switch 中刷新技能列表，再执行单项更新或全部更新。

请直接在各自的源仓库中修改 Skill；`skills/` 目录由同步工作流维护，手动修改可能在下一次同步时被覆盖。
