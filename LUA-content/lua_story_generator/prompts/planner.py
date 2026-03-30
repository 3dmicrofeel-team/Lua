# -*- coding: utf-8 -*-
"""
Planner Agent - 奇遇步骤规划 Prompt
"""

PLANNING_SKILL = """
## 【强制】只输出 1 个 encounter

**当前系统设计**：每次生成仅输出**一个**奇遇。复杂剧情（对弈、赌局、多分支、同伴邀请等）全部合并在这一个 encounter 内完成。续写功能用于添加新章节，不要在同一次生成中拆成多步。

- **禁止**输出多个 steps，**禁止** chain 多步
- **禁止**同一 NPC 在不同地点出现多次
- 对弈、赌局、MiniGame、对话分支、同伴邀请、奖励发放 → **全部在一个 encounter 内**当场完成
- 输出格式固定为仅 1 个 step：

{
  "steps": [
    {"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "完整的单幕奇遇剧情描述", "chain": null}
  ]
}
"""

PLANNER_SYSTEM = """你是一位LUA奇遇系统开发规划师。Setup 和路人NPC 已固定，只需规划奇遇(Encounter)步骤。
{asset_note}

输出格式：仅 encounter 类型步骤的 JSON。
{planning_skill}
"""

PLANNER_USER = """规则与API：
{full_docs}

---

扩写故事：
{expanded_story}

请输出步骤JSON。"""
