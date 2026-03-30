# Prompts 文件夹

所有 AI 调用的 Prompt 集中存放于此，便于策划/开发者直接修改调整。

| 文件 | 用途 |
|------|------|
| `npc_think.py` | NPC 思考功能 - Type=NPC_Think_Begin 时的表演 LUA 生成 |
| `npc_dialogue.py` | NPC 对话功能 - Type=NPC_Dialogue_Request 时的回复 LUA 生成 |
| `npc_persuade.py` | NPC 说服功能 - Type=NPC_Persuade_Request 时的回合回复生成 |
| `story_expert.py` | Story Expert Agent - 故事扩写/续写 |
| `planner.py` | Planner Agent - 奇遇步骤规划 |
| `coding_agent.py` | Coding Agent - LUA 代码生成 |

修改后需重启服务生效。
