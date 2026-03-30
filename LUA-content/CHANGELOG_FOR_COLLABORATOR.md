# LUA Story Generator 改动说明（发给合作者）

本文档汇总近期对 LUA 故事生成器及 UE 集成的改动，便于合作者了解与联调。

---

## 一、UE 端改动（LuaSocketServer 插件）

### 1.1 通信方式：HTTP → TCP 客户端

- **原状**：`RequestLuaScript` 使用 HTTP 请求 Python 服务
- **现况**：改为 **TCP 客户端** 直连 Python 的 TCP 服务
  - 默认连接：`127.0.0.1:9010`（与 `python main.py` 启动的 TCP 端口一致）
  - 协议：JSON 行（每行一个完整 JSON，以 `\n` 结尾）

### 1.2 JSON 与编码处理

- **请求 JSON**：使用 `TCondensedJsonPrintPolicy` 输出紧凑 JSON，避免换行破坏 TCP 行协议
- **发送**：`StringCast<UTF8CHAR>` 将请求转为 UTF-8 发送，避免 Windows 上可能的 UTF-16
- **接收**：按 UTF-8 解析 Python 响应并转换为 FString

### 1.3 响应解析

支持两种返回格式：
- `full_script`：直接使用完整 Lua 脚本
- `stages`：将 `[{Type, Code}, ...]` 的 `Code` 按顺序拼接后使用

最终均通过 `OnHttpResponseReceived` 广播，Type 为 `FullScript` 或 `Error`。

### 1.4 异步执行

- 网络 I/O 在后台线程执行（`AnyBackgroundThreadNormalTask`）
- 回调在主线程执行（`GameThread`），保证蓝图/游戏逻辑安全

---

## 二、Python 端改动（lua_story_generator）

### 2.1 素材库：DataTable 替代 assets.json

- **原状**：从 `assets.json` 加载 NPC/Enemy/Prop
- **现况**：从 DataTable CSV 加载
  - 文件：`DT_SpawnNPCTable.csv`、`DT_EnemyDataTable.csv`、`PropVilligeData.csv`、`DT_Items.csv`
  - 路径：默认 `项目根/../../Doc/DataTable`（项目根 LUA-Skills 向上 2 级至 ChronicleForge），可通过环境变量 `DATATABLE_DIR` 覆盖

### 2.2 端口与 TCP

- **HTTP 端口**：由 8000 调整为 **9000**
- **TCP 端口**：默认 **9010**，可通过 `TCP_PORT` 覆盖
- **启动方式**：`python main.py` 同时启动 HTTP + TCP；`set SKIP_TCP=1` 可只启动 HTTP

### 2.3 奇遇生成格式（符合“正确”演绎格式）

- **单奇遇**：函数名固定为 `SpawnEncounter_main`（不再用如 `SpawnEncounter_LoveTriangle`）
- **注释**：在奇遇代码前自动添加：
  ```lua
  -- 奇遇：Main encounter from story
  -- 直接执行：固定坐标生成
  ```
- **路人 NPC 注释**：在 `step3_npc_located.lua` 中 `World.SpawnNPC` 前添加 `-- ============ 放置路人NPC ============`
- **World.SpawnEncounter 半径**：单奇遇使用 220.0

### 2.4 坐标与 Z 高度修正（解决“在天上掉落”问题）

- **问题**：玩家/NPC 初始 Z=4797 等高空值，落地后 Z≈90，触发盒子未跟随
- **修改**：
  - `config.py`：新增 `GROUND_Z=90`、`ENCOUNTER_BASE_X=11600`、`ENCOUNTER_BASE_Y=12000`（靠近玩家落地 (11536, 11963, 90)）
  - `step3_npc_located.lua`：所有 `World.SpawnNPC` 的 Z 从 4770~4801 调整为 **90**
  - 奇遇 `ResolveEncounterLoc()`：Z 从 4797 改为 **90**，示例坐标 `{X=11600, Y=12000, Z=90}`
  - `agents.py` / `skills/lua-encounter/SKILL.md`：提示与模板统一使用地面高度 90

### 2.5 地图构建

- **step2_map_generate.lua**：仍使用 `Env.BuildAsync(map)`（与正确演绎格式一致）
- **map 部分**：沿用当前 step1/step2/step3，不做结构性调整

### 2.6 校验与提示

- `validate_lua.py`：对 `ResolveEncounterLoc()` 返回 `{X=0,Y=0,Z=0}` 的提示更新为“应靠近玩家落地位置(约11536,11963,90)，Z 须为地面高度 90”

---

## 三、联调注意事项

1. **启动 Python 服务**：运行 `python main.py`，确保 TCP 监听 `127.0.0.1:9010`
2. **UE 调用**：`RequestLuaScript(Content, ApiKey, "127.0.0.1", 9010)`，监听 `OnHttpResponseReceived`
3. **DataTable 路径**：若 CSV 不在默认路径，设置环境变量 `DATATABLE_DIR`
4. **奇遇触发**：确保玩家/NPC/奇遇坐标 Z 一致（约 90），避免触发盒子在错误高度

---

## 四、涉及文件一览

| 模块 | 文件 |
|------|------|
| UE | `Plugins/LuaSocketServer/.../LuaSocketServerSubsystem.cpp` |
| 配置 | `lua_story_generator/config.py` |
| 编排 | `lua_story_generator/orchestrator.py` |
| 代理 | `lua_story_generator/agents.py` |
| 校验 | `lua_story_generator/validate_lua.py` |
| 技能 | `lua_story_generator/skills/lua-encounter/SKILL.md` |
| 路人 NPC | `lua_story_generator/step3_npc_located.lua` |

---

*文档生成日期：2025-03*
