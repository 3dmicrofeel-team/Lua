---
name: lua-planning
description: Plans LUA encounter development steps from expanded story. Use when decomposing story into Setup/Encounter steps. Outputs JSON step list for Coding Agent.
---

# LUA Planning Skill

## 【强制】每次仅输出 1 个 encounter

**当前系统设计**：每次生成只输出**一个**奇遇。续写功能用于添加新章节，不要在同一次生成中拆成多步。

- **禁止**输出多个 steps
- **禁止** chain 多步
- 复杂剧情（对弈、赌局、多分支、同伴邀请等）**全部合并**在这一个 encounter 内完成
- 一个 NPC 一个地点，禁止同一 NPC 在不同地点出现多次

## 标准流程（rule.md）

1. Setup 初始化地图
2. Build 世界
3. 生成常驻 NPC（可选）
4. 注册 Encounter（当前仅 1 个）
5. StartGame + Time.Resume

## 输出格式（仅 1 个 step）

```json
{
  "steps": [
    {"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "完整的单幕奇遇剧情描述", "chain": null}
  ]
}
```

**注意**：name 固定为 `SpawnEncounter_main`，chain 固定为 null。

## 示例（对弈/赌局 - 单 encounter 完成）

```json
{
  "steps": [
    {"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "酒吧门口老人邀玩家下棋，PlayMiniGame 获胜得 TestSword，失败被骂。同一 NPC 同一地点完成。", "chain": null}
  ]
}
```

## 示例（同伴邀请 - 单 encounter）

```json
{
  "steps": [
    {"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "森林边遇 Alice，玩家可选择邀请成为同伴，SetAsCompanion 后 Toast。", "chain": null}
  ]
}
```

## step.type 取值

- `setup` → 加载 lua-setup-world Skill
- `encounter` → 加载 lua-encounter Skill
