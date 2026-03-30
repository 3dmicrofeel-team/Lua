# LUA 奇遇脚本生成器（Skills 版）

多 Agent AI 系统，将自然语言故事转换为符合 `rule.md` 规范的 LUA 奇遇脚本。采用 **Skills 思维**：Progressive Disclosure、Checklist、Feedback Loop。

## 快速部署

### 1. 环境要求

- Python 3.10+
- OpenAI API Key（或兼容接口的 API Key）

### 2. 安装依赖

```bash
cd lua_story_generator
pip install -r requirements.txt
```

### 3. 项目结构要求

本服务需要从**父目录**读取 `rule.md` 和 `lua_atomic_modules_call_guide.md`。请确保目录结构为：

```
项目根目录/
├── rule.md
├── lua_atomic_modules_call_guide.md
└── lua_story_generator/
    ├── main.py
    ├── requirements.txt
    ├── assets_default.json
    └── ...
```

若父目录没有这两个文件，规划阶段可能缺少 API 参考，建议从 LUA 工程中拷贝到父目录。

**NPC 对话 / NPC 思考** 使用的 LUA API 说明来自 `ChronicleForge/Doc/Lua_Function(for AI)`（默认路径相对本仓库向上解析）。服务**每次生成请求**都会重新读取该目录下全部 `*.md` 并合并进 Prompt，不在内存中缓存合并结果；启动时会在控制台打印路径与 `.md` 数量。可通过环境变量 `LUA_REFERENCE_DIR` 覆盖目录。

### 4. 启动服务

```bash
python main.py
```

默认监听 `http://0.0.0.0:9000`。如需指定端口：

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 5. 素材库（DataTable）

素材库从 **DataTable CSV** 加载，启动/刷新时自动读取：

- `DT_SpawnNPCTable.csv` → NPC 类型
- `DT_EnemyDataTable.csv` → Enemy 类型
- `PropVilligeData.csv` → Prop 类型
- `DT_Items.csv` → Item 类型（奖励道具，用于 GiveItem/GiveWeapon/GiveEquip）
- `DT_MontageTable.csv` → PlayAnim 一次性动画（Attack、Drink 等）
- `DT_AnimStartTable.csv` → PlayAnimLoop 持续/循环动画（Admiring、Dance、Drink、Happy 等）

默认路径：`ChronicleForge/Doc/DataTable`（相对 LUA 工程，与 ChronicleForge 同级）。可通过环境变量 `DATATABLE_DIR` 覆盖。

策划修改表格后，刷新页面即可生效。

### 6. 访问与使用

1. 打开浏览器访问 `http://localhost:9000`
2. 输入 OpenAI API Key（可勾选保存到本地）
3. 素材库从 DataTable 自动加载，可在页面查看可用 NPC/Enemy/Prop/Item；MiniGame 可在页面手动添加
4. 输入故事梗概，点击「生成 LUA 脚本」
5. 复制总拼装脚本或下载 `Full_Script.lua` 使用

### 7. TCP 服务（Unreal 客户端）

默认同时启动 TCP 服务 `tcp://127.0.0.1:9010`（HTTP 占用 9000，TCP 默认 9010），Unreal 可作为 TCP 客户端连接并发送 JSON 请求生成 LUA。详见 `UNREAL_INTEGRATION.md`。

- 仅运行 TCP：`python tcp_server.py --port 9010`
- 禁用 TCP：`set SKIP_TCP=1` 后运行 `python main.py`

---

## 流程

1. **故事专家 AI**：将简短故事扩写为完整奇遇剧本（TPA 格式）
2. **规划 AI**：按 `lua-planning` Skill + rule.md 拆解为开发步骤
3. **代码 AI**：每步按类型加载对应 Skill（lua-encounter / lua-setup-world），生成 LUA 代码
4. **校验反馈**：Encounter 代码通过 `validate_lua.py` 校验，不通过则自动修正（最多 2 轮）

## Skills 目录

```
skills/
├── lua-encounter/      # 奇遇脚本 Skill
│   ├── SKILL.md       # Checklist、模板、功能模块
│   └── reference.md   # API 参考
├── lua-setup-world/   # 地图 Setup Skill
│   ├── SKILL.md
│   └── reference.md
└── lua-planning/      # 规划 Skill
    └── SKILL.md
```

## 模型选择

- **故事/规划**：GPT 4.1、GPT 5.1
- **代码生成**：GPT 4.1、GPT 5.1、Codex (gpt-5.1-codex-max)、Codex (gpt-5.2-codex)

## 目录结构

```
lua_story_generator/
├── main.py             # FastAPI 入口
├── config.py
├── skills_loader.py    # Progressive disclosure 加载 Skills
├── agents.py          # Story / Planner / Coding
├── orchestrator.py    # 流水线 + 校验反馈循环
├── validate_lua.py    # Encounter 规则校验
├── setup_template.lua # 固定 Setup 模板
├── assets_default.json # 默认素材库（含 minigames）
├── skills/             # Skill 定义
├── static/
│   └── index.html
└── requirements.txt
```
