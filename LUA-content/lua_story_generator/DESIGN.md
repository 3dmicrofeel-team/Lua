# LUA Story Generator 系统设计文档

本文档详细描述 LUA 奇遇脚本生成器的架构、各模块工作流、AI 数据流，以及产品上线所需工作。

---

## 一、系统概览

LUA Story Generator 是一个面向 Unreal Engine 的 AI 辅助脚本生成系统，核心能力包括：

1. **奇遇剧本生成**：自然语言 → 扩写/续写剧本 → 规划步骤 → 生成可执行 LUA
2. **NPC 对话**：玩家发言 + NPC 信息 → 生成对话回复 LUA（`SayWithDialoguebox`、动画）
3. **NPC 思考**：周围可互动对象（TagList）+ NPC 信息 → 生成表演 LUA（`Say` 头顶气泡、动画）

### 架构图

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              客户端层（Clients）                                    │
├────────────────────────────────┬─────────────────────────────────────────────────┤
│   Unreal Engine (TCP)           │   Web 前端 (HTTP)                                │
│   - 发送 story_input / 对话/思考  │   - index.html（奇遇生成）                       │
│   - 接收 LUA 脚本               │   - npc_dialogue.html（对话）                      │
│   - 端口: 9010                  │   - npc_think.html（思考）                        │
└───────────────┬────────────────┴─────────────────────┬───────────────────────────┘
                │                                       │
                ▼                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              服务端层（Backend）                                    │
├────────────────────────────────┬─────────────────────────────────────────────────┤
│   tcp_server.py                 │   main.py (FastAPI)                             │
│   - JSON 行协议                  │   - HTTP API                                   │
│   - 解析请求、分发命令            │   - 静态文件服务                                │
│   - 推送到 UE 客户端             │   - /generate, /api/npc-interaction/generate    │
│   - UE 消息队列 → 前端轮询        │   - /api/send-to-unreal（推送到 TCP 客户端）    │
└───────────────┬────────────────┴─────────────────────┬───────────────────────────┘
                │                                       │
                └───────────────────┬───────────────────┘
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              业务逻辑层（Business Logic）                           │
├───────────────────────────────────────────────────────────────────────────────────┤
│   orchestrator.py     │  run_full_pipeline: Story → Plan → Code                    │
│   npc_dialogue.py     │  generate_npc_dialogue_reply_lua                           │
│   npc_interaction.py  │  generate_npc_think_lua                                    │
└───────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              AI 代理层（Agents）                                    │
├───────────────────────────────────────────────────────────────────────────────────┤
│   agents.py          │  Story Expert, Planner, Coding Agent                        │
│   prompts/            │  各 Agent 的 System/User Prompt 模板                        │
│   skills/             │  按步骤类型的渐进式技能（Progressive Disclosure）             │
└───────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              数据与资源层（Data & Resources）                        │
├───────────────────────────────────────────────────────────────────────────────────┤
│   datatable_loader.py │  DataTable CSV → NPC/Enemy/Prop/Item/Animations            │
│   stage_loader.py     │  固定 LUA 模板（step1~5）                                    │
│   validate_lua.py     │  LUA 规则校验与修复反馈                                      │
│   config.py           │  模型、路径、坐标等配置                                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、各模块详细工作流

### 2.1 奇遇剧本生成（Story → Plan → Code）

**入口**：TCP `cmd=generate` 或 HTTP `POST /generate`

**流水线**（`orchestrator.run_full_pipeline`）：

```
用户输入 (story_input)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Story Expert                                                         │
│ - 输入: story_input, story_mode(expand/continue), previous_npc_info(续写时)   │
│ - 输出: expanded_story（TPA 格式的完整奇遇剧本）                               │
│ - 模型: gpt-4.1 / gpt-5.1                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Planner                                                              │
│ - 输入: expanded_story, assets(NPC/Enemy/Prop/Item 素材库)                   │
│ - 输出: plan_output（JSON 步骤列表）                                         │
│ - 仅规划 Encounter 类型，Setup 固定不生成                                    │
│ - 模型: gpt-4.1 / gpt-5.1                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: 步骤提取与限制                                                        │
│ - extract_steps_from_planner_output() 解析 JSON                              │
│ - 强制单奇遇：仅保留第一个 encounter 步骤                                     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Coding Agent（含验证反馈环）                                          │
│ - 输入: step, expanded_story, assets, npc_located, encounter_locations      │
│ - 输出: InitEvent LUA                                                        │
│ - validate_encounter() 校验规则，失败则 CODING_FIX 重试（最多 2 次）          │
│ - 模型: gpt-4.1 / gpt-5.1 / gpt-5.1-codex-max / gpt-5.2-codex                │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 5: 组装 stages                                                          │
│ - InitMap: step1 + step2 + step3（或用户提供的 init_map_code）                │
│ - InitEvent: Coding Agent 生成的奇遇 LUA                                     │
│ - StartGame: step5 固定模板                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
返回 { stages: [{Type, Code}, ...], full_script, expanded_story, ... }
```

**AI 数据流（奇遇生成）**：

| Agent        | 输入数据                         | 输出数据                    |
|--------------|----------------------------------|-----------------------------|
| Story Expert | story_input, base_rules          | expanded_story (TPA 剧本)   |
| Planner      | expanded_story, assets, full_docs| plan_output (JSON steps)    |
| Coding Agent | step, skill_content, assets, npc_located | InitEvent LUA 代码   |

---

### 2.2 NPC 对话（NPC_Dialogue_Request）

**入口**：TCP `Type=NPC_Dialogue_Request` 或 HTTP `POST /api/npc-interaction/generate`（Type=NPC_Dialogue_Request）

**工作流**：

```
UE/Web 请求
  { Type: "NPC_Dialogue_Request", Code: { NPCInfo, CurrentDialogue }, AdditionalContent }
    │
    │  （UE 可能将 Code 作为字符串发送，含 \r\n\t 转义 → tcp_server._ensure_dict 解析）
    │
    ▼
main._build_code_for_request()
  → Code = { NPCInfo, CurrentDialogue }
    │
    ▼
npc_dialogue.generate_npc_dialogue_reply_lua()
    │
    ├─ 解析 NPCInfo (Name, Title, Gender, Personality, Goals, Memory 等)
    ├─ 解析 CurrentDialogue (玩家说的话)
    ├─ 加载 dialogue_skill：skills/lua-dialogue/SKILL.md + `lua_reference_loader` 从 LUA_REFERENCE_DIR 合并全部 `*.md`（每次请求读盘，无缓存）
    ├─ 调用 OpenAI Chat Completions (gpt-4.1)
    │    Prompt: NPC_DIALOGUE_MAIN_PROMPT + NPCInfo + CurrentDialogue + 动画列表
    │
    ▼
后处理
  - npc: → _self_
  - 添加 IsValid、LookAt、Wait 等前置检查
    │
    ▼
返回 { Type: "NPC_Dialogue_Reply", Code: lua }
```

**AI 数据流（NPC 对话）**：

| 阶段       | 输入                           | 输出                    |
|------------|--------------------------------|-------------------------|
| 解析       | Code (NPCInfo, CurrentDialogue)| 结构化 npc_info, current_dialogue |
| Prompt 构建| npc_info_str, current_str, dialogue_skill, anim_play/loop | 完整 prompt |
| GPT-4.1    | system + user messages         | 原始 LUA（含 npc:）     |
| 后处理     | 原始 LUA                       | npc→_self_，加前置检查  |

---

### 2.3 NPC 思考（NPC_Think_Begin）

**入口**：TCP `Type=NPC_Think_Begin` 或 HTTP `POST /api/npc-interaction/generate`（Type=NPC_Think_Begin）

**工作流**：

```
UE/Web 请求
  { Type: "NPC_Think_Begin", Code: { NPCInfo, TagList }, AdditionalContent }
    │
    ▼
main._build_code_for_request()
  → Code = { NPCInfo, TagList }
    │
    ▼
npc_interaction.generate_npc_think_lua()
    │
    ├─ 解析 NPCInfo
    ├─ 解析 TagList (周围可互动对象 [{UID, Tags}, ...])
    ├─ 加载 think_skill：skills/lua-npc-interaction-performance/SKILL.md + 同上 LUA API 合并文档（每次请求读盘）
    ├─ 加载 NPC_THINK_MAIN_PROMPT（含 think_skill 占位）
    ├─ 调用 OpenAI Chat Completions (gpt-4.1)
    │    Prompt: NPC_THINK_MAIN_PROMPT + NPCInfo + TagList + 动画列表
    │
    ▼
后处理
  - npc: → _self_
  - 添加 IsValid 等前置检查
    │
    ▼
返回 { Type: "NPC_Think_End", Code: lua }
```

**AI 数据流（NPC 思考）**：

| 阶段       | 输入                           | 输出                    |
|------------|--------------------------------|-------------------------|
| 解析       | Code (NPCInfo, TagList)        | npc_info, tag_list      |
| Prompt 构建| npc_info_str, tag_list_str, anim_play/loop | 完整 prompt |
| GPT-4.1    | system + user messages         | 原始 LUA                |
| 后处理     | 原始 LUA                       | npc→_self_，加前置检查  |

---

### 2.4 TCP 服务端（tcp_server.py）

**协议**：JSON 行，每行一个 JSON 对象，UTF-8 编码。

**命令分发**：

| cmd / Type              | 处理逻辑                                                     |
|-------------------------|--------------------------------------------------------------|
| `generate`              | orchestrator.run_full_pipeline → 返回 stages / full_script   |
| `NPC_Dialogue_Request`  | npc_dialogue.generate_* → 返回 NPC_Dialogue_Reply            |
| `NPC_Think_Begin`       | npc_interaction.generate_npc_think_lua → 返回 NPC_Think_End  |
| `report` / `ue_feedback`| push_ue_message → 供前端轮询 /api/ue-messages                 |
| `get_assets`            | _load_assets → 返回素材库                                    |
| `ping` / `health`       | 返回 {ok: true}                                              |

**Code 字符串解析**：当 UE 将 `Code` 作为 JSON 字符串发送（含 `\r\n\t`）时，`_ensure_dict()` 会 `json.loads(Code)` 转为 dict，保证后续逻辑正确读取 NPCInfo 等字段。

**推送到 UE**：`send_to_unreal_clients(payload)` 将 `{Type, Code, AdditionalContent}` 推送给所有已连接的 TCP 客户端。

---

### 2.5 前端页面

| 页面             | 功能                                                         |
|------------------|--------------------------------------------------------------|
| index.html       | 奇遇生成：输入故事、选模型、地图坐标、素材库，调用 /generate   |
| npc_dialogue.html| NPC 对话：输入 JSON、解析并填充、AI 生成 LUA、发送到 UE      |
| npc_think.html   | NPC 思考：输入 JSON、解析并填充、AI 生成 LUA、发送到 UE      |

**解析并填充**：`parseAndUnescapeJson()` 递归解析，当 `Code` 为字符串时再解析为对象，去除 UE 传来的转义符，便于前端读取 key 并展示。

---

## 三、AI 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 奇遇生成管线                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  story_input ──► Story Expert ──► expanded_story                                      │
│                                     │                                                 │
│                                     ▼                                                 │
│  assets ───────► Planner ──────────► plan_output (JSON steps)                         │
│                                     │                                                 │
│                                     ▼                                                 │
│  step, skill ─► Coding Agent ─────► InitEvent LUA ──► validate_encounter ──► fix loop  │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│ NPC 对话管线                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  NPCInfo + CurrentDialogue ──► Prompt 构建 ──► GPT-4.1 ──► 后处理 ──► NPC_Dialogue_Reply│
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│ NPC 思考管线                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  NPCInfo + TagList ──► Prompt 构建 ──► GPT-4.1 ──► 后处理 ──► NPC_Think_End            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、产品上线所需工作

### 4.1 安全与认证

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| API Key 存储   | 内存 + 前端 localStorage | 支持服务端加密存储，环境变量备用              |
| API Key 暴露   | 前端可见                 | 仅后端持有，UE 通过安全 channel 获取 token   |
| CORS           | allow_origins=["*"]      | 生产环境限制为指定域名                        |
| 速率限制       | 无                       | 按 IP/用户限流，防滥用                        |

### 4.2 可靠性

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 错误处理       | 部分 try/except          | 统一异常处理、结构化错误码、用户可读提示       |
| 重试机制       | Coding Agent 有 fix 重试 | AI 调用增加指数退避重试，应对 transient 错误   |
| 超时           | 依赖 OpenAI 默认         | 显式设置 request timeout，避免长时间阻塞     |
| 日志           | print 到 stderr          | 结构化日志（JSON），支持 log level、trace ID  |

### 4.3 可观测性

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 监控           | 无                       | 请求量、延迟、错误率、AI token 消耗           |
| 追踪           | 无                       | 请求级 trace（Story→Plan→Code 全链路）       |
| 健康检查       | ping/health              | /health 返回依赖状态（DataTable、OpenAI 连通性）|

### 4.4 配置与部署

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 配置管理       | config.py + 环境变量     | 区分 dev/staging/prod 配置，敏感信息用 secrets |
| DataTable 路径 | 硬编码默认路径           | 文档化 DATATABLE_DIR、LUA_REFERENCE_DIR 要求   |
| 多实例         | 单进程                   | 支持无状态部署，TCP 需考虑 sticky session     |

### 4.5 功能完整性

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 多奇遇         | 强制单奇遇               | 产品需多步时，扩展 planner + orchestrator    |
| 版本兼容       | 无                       | API 版本（/v1/generate），向后兼容策略       |
| 文档           | README 等                | API 文档（OpenAPI/Swagger）、UE 集成示例      |
| 测试           | 未系统化                 | 单元测试（解析、验证逻辑）+ 集成测试（API）   |

### 4.6 用户体验

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 加载反馈       | 按钮 disabled             | 进度指示、预估耗时、取消能力                  |
| 错误提示       | alert                    | 页面内 toast，可复制错误信息                  |
| 历史记录       | 无                       | 最近生成记录、可重跑/对比                     |
| 离线/断网      | 无特殊处理               | 明确提示、重连与恢复                          |

### 4.7 成本与效率

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| Token 统计     | 无                       | 记录每次调用的 token 用量，便于优化          |
| 缓存           | 无                       | 对相同 story_input 等可缓存结果，减少调用    |
| 模型选择       | 前端可选                 | 支持按场景推荐模型（如轻量用 4.1，重逻辑用 codex）|

### 4.8 合规与审计

| 工作项         | 现状                     | 建议                                         |
|----------------|--------------------------|----------------------------------------------|
| 内容审计       | 无                       | 输出内容过滤、敏感词检测（视产品要求）       |
| 使用记录       | 无                       | 关键操作审计日志（谁、何时、何种输入/输出）  |

---

## 五、文件索引

| 文件/目录        | 职责说明                                           |
|------------------|----------------------------------------------------|
| main.py          | FastAPI 入口、HTTP 路由、API Key、assets、generate |
| tcp_server.py    | TCP JSON 协议、UE 连接管理、命令分发、消息队列     |
| orchestrator.py  | Story→Plan→Code 流水线、stage 组装                 |
| agents.py        | Story Expert、Planner、Coding Agent 实现          |
| npc_dialogue.py  | NPC 对话 LUA 生成                                 |
| npc_interaction.py| NPC 思考 LUA 生成                                |
| datatable_loader.py| DataTable CSV 加载、素材库                        |
| stage_loader.py  | 固定 LUA 模板（step1~5）                           |
| validate_lua.py  | LUA 规则校验、修复反馈                             |
| config.py        | 模型、路径、坐标配置                               |
| prompts/         | 各 Agent 的 Prompt 模板                            |
| skills/          | 按步骤类型的 Skill（lua-encounter、lua-dialogue 等）|
| static/          | Web 前端 HTML                                     |

---

*文档版本：2025-03，随系统迭代更新。*
