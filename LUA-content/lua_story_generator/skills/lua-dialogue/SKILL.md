---
name: lua-dialogue
description: Generates LUA for NPC 对话 (Dialogue → Behavior Chain). Use when UE/Web sends Type=NPC_Dialogue_Request. Four phases: Intent Classification → Reference Selection → Action Planning → Lua Generation.
---

# LUA 对话 Skill

## 何时加载

当 UE/Web 端传入 `Type=NPC_Dialogue_Request`、`Code={NPCInfo, CurrentDialogue}` 时应用本 Skill。根据玩家输入生成 NPC 的语言与行为反应。

## 总体流程（四阶段）

```
玩家输入(CurrentDialogue)
   ↓
意图分类（简单 / 复杂）
   ↓
行为规划（Resolve → Reply → Actions）
   ↓
Lua 生成
```

## 一、意图分类（Intent Classification）

### 1. 简单意图（Simple Intent）

- 只需一句回复，或一句回复 + 一个轻动作
- 不引发连续行为链、不改变状态、不触发 UI 分支、**通常**不发放物品、不安排未来事件（**例外**：若 Prompt 中已注入「可发放道具」列表且剧情需要一句答谢后顺手赠礼，可视为「短行为链」，仍须 `Give*` + `UI.Toast`，id 仅能用该列表）
- **典型**：你好、你是谁、今天天气不错、你在干什么、现在几点了 / 当前时间是多少
- **输出**：PlayAnim/PlayAnimLoop → SayWithDialoguebox。**每说一句话必有对应动作**。对话模式为怼脸镜头，无需 LookAt(player)。

### 2. 复杂意图（Complex Intent）

- NPC 回复后执行一个或多个额外动作（移动、跟随、物品交付、UI 选择、未来调度）
- **典型**：给我点吃的、跟着我、去那边看看、你觉得我们该怎么办、明天早上来找我；**玩家索要道具**；**NPC 因开心/感激主动赠礼**
- **输出**：Reply → Additional Actions → Optional Branch / Reward / State Change

### 2.1 物品赠送（与奇遇共用 DT_Items）

- **id 来源**：每次请求时主 Prompt 会附带当前 **DT_Items** 列表；**只能**使用该列表中的 Row Name，禁止 `Food_Bread` 等编造 id。
- **NPC 主动给**：玩家夸奖、道谢、告别或聊得投机，且 Favorability / Personality 支持时，可在台词后用 `_self_:GiveItem` / `GiveWeapon` / `GiveEquip` + `UI.Toast`。给物动画用 `Give` 或 `Happy` → `Give`。
- **玩家要 NPC 给**：先按人设判断是否愿意；**不愿意**只拒绝（无 `Give*`）；**愿意**先答应台词再 `Give*` + `UI.Toast`。
- **API**：武器向 Equipment 优先 `GiveWeapon`；防具饰品 `GiveEquip`；货币/消耗/资源等 `GiveItem`（不确定时用 `GiveItem`）。
- **服务端**：`npc_dialogue` 生成后会用 **DT_Items 白名单**校验 `Give*` 的第一个参数；若出现表外 id（如 `Iron_Sword`），会自动再请求模型 **修正一整段 LUA**，改为白名单内 id 或删掉发奖。

## 二、Reference 选择（按需选用）

| 需求 | Reference |
|------|-----------|
| NPC 行为 | Performer |
| 环境查询 | World |
| 对话 UI | UI |
| 游戏内当前时间（回答几点了） | Time |
| 时间调度 | Time |

- 简单回复：Performer + World
- 回答当前时间：Performer + Time（`Time.GetTimeString` 或 `GetHour`/`GetMinute`/`GetDay`）
- 需要物品 / 赠礼 / 玩家索要：Performer + UI（SayWithDialoguebox + GiveItem|GiveWeapon|GiveEquip + Toast），id 仅 Prompt 所列 DT_Items
- 需要选择分支：UI + Performer（AskMany + branch）
- 需要未来事件：Time + Performer（AddOnceSchedule）

## 三、行为规划（Action Planning）

**推荐顺序**：Resolve Targets → Validate → Reply → Orientation/Movement → Animation → Item/State/UI → Schedule → Exit

| 意图 | 规划示例 |
|------|----------|
| 简单（你好） | resolve player → say greeting（含动作） |
| 简单（几点了） | resolve player → `Time` 取时 → say 告知时间（含动作） |
| 复杂（给吃的/索要/主动谢礼） | resolve player → reply（答应或拒绝）→ 若愿意则 Give* → Toast |
| 复杂（跟随） | resolve player → reply confirmation → set ally → set companion → follow player |
| 复杂（选择） | say → AskMany → branch |

## 四、Lua 编写规则（必须遵守）

1. **对象先获取再判定**：`local player = World.GetByID("Player")` 后必须 `if not player or not player:IsValid() then return end`
2. **NPC 用冒号语法**：`_self_:SayWithDialoguebox("...")`、`_self_:PlayAnim(...)`，禁止 `_self_.Say(...)`
3. **动作间加等待**：可见动作之间插入 `World.Wait(0.3~0.5)`
4. **复杂意图先回复**：必须先 SayWithDialoguebox 一句，再执行行为链
5. **UI.AskMany 按选项文本分支**：`if choice == "跟着我" then`，禁止用 "A"、"B"
6. **UI.Ask 按布尔分支**：`if accept then ... else ... end`
7. **物品交付用 Give 系列**：`_self_:GiveItem(id,count)`，推荐 SayWithDialoguebox + Give + Toast
8. **关系变化用状态接口**：`_self_:SetAsAlly()`、`_self_:SetAsCompanion()` 等
9. **环境查询用 World**：`World.GetByID`、`World.Find`、`World.FindNearest`
10. **未来事件用 Time**：`Time.AddOnceSchedule`、`Time.AddDailySchedule`
11. **玩家问当前时间用 Time（游戏内时间）**：优先 `Time.GetTimeString()` 拼进台词；需拆解时用 `Time.GetDay()`、`Time.GetHour()`、`Time.GetMinute()`。不要用 Lua `os.time` / `os.date`（与叙事世界时间不一致时易错）

## 五、对话模式专用 API（使用 _self_）

- **台词**：`_self_:SayWithDialoguebox(Text)` — NPC 前展示对话框（对话模式专用，不用 Say）
- **动画**：`_self_:PlayAnim(AnimName)`（仅 DT_MontageTable）/ `_self_:PlayAnimLoop(AnimName, Time)`（仅 DT_AnimStartTable）— 两表互不共用。**动画列表由 DT_AnimStartTable / DT_MontageTable 动态加载，策划新增即生效。**
- **动画选择**：根据说话的 context（情绪、内容、情境）从当前可用列表中选**最贴合**的，尽量多样，不要总是 Dialogue。例如：高兴→Happy、不满→Frustrated、打招呼→Wave、给东西→Give、害羞→Shy。
- **面向**：`_self_:LookAt(target)` — 对话模式怼脸镜头，通常不需要；若需（如跟随前）可按需使用
- **跟随**：`_self_:Follow(player, distance)`
- **物品**：`_self_:GiveItem(id, count)` / `GiveWeapon` / `GiveEquip`
- **关系**：`_self_:SetAsAlly()` / `SetAsCompanion()` / `SetAsHostile()`
- **当前时间（全局 Time）**：`Time.GetTimeString()`（字符串，可直接用于台词）；或 `Time.GetDay()` / `Time.GetHour()` / `Time.GetMinute()` 自行格式化；`Time.IsNight()` 可作语气补充

## 六、标准输出模板

（以下为示例，**动画须根据 context 从当前可用列表选最贴合的**，不要总用 Dialogue）

### 模板1：简单回复（例如打招呼）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Wave", 0)   -- 打招呼用 Wave；根据语境可选 Happy/Shy/Dialogue 等
World.Wait(0.3)
_self_:SayWithDialoguebox("你好。")
```

### 模板2：回复 + 动作（例如高兴回应）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Happy", 0)   -- 高兴时用 Happy；不满用 Frustrated，害羞用 Shy 等
World.Wait(0.5)
_self_:SayWithDialoguebox("很高兴见到你。")
```

### 模板3：询问当前时间（游戏内时间）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Dialogue", 0)   -- 说明性回答；可按语境换 Think/Happy
World.Wait(0.3)

local now = Time.GetTimeString()
_self_:SayWithDialoguebox("现在是 " .. now .. "。")
```

若需格式化（示例：第几天、几时几分）：
```lua
local day = Time.GetDay()
local h = Time.GetHour()
local m = Time.GetMinute()
_self_:SayWithDialoguebox(string.format("今天是第 %d 天，现在 %d 点 %d 分。", day, h, m))
```

### 模板4：回复 + 物品（id 必须用 Prompt 中 DT_Items 列表，示例用 Bandage）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Give", 0)   -- 给东西用 Give；其他情境选 Sit/Eat/Happy 等
World.Wait(0.3)
_self_:SayWithDialoguebox("给你。")
World.Wait(0.5)

_self_:GiveItem("Bandage", 1)
UI.Toast("获得了简易绷带")
```

### 模板4b：NPC 开心主动赠礼（无玩家索要）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Happy", 0)
World.Wait(0.3)
_self_:SayWithDialoguebox("今天聊得真开心，这个你拿着。")
World.Wait(0.4)
_self_:PlayAnimLoop("Give", 0)
World.Wait(0.3)

_self_:GiveItem("Money", 10)
UI.Toast("获得了金币")
```

### 模板4c：玩家索要 — NPC 愿意
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Dialogue", 0)
World.Wait(0.3)
_self_:SayWithDialoguebox("行，拿去吧。")
World.Wait(0.5)

_self_:GiveItem("raw_meat", 1)
UI.Toast("获得了生肉")
```

### 模板4d：玩家索要 — NPC 拒绝（无 Give）
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:PlayAnimLoop("Frustrated", 0)
World.Wait(0.3)
_self_:SayWithDialoguebox("我自己还不够呢，没法分你。")
```

### 模板5：回复 + 跟随
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:SayWithDialoguebox("好，我跟着你。")
World.Wait(0.5)

_self_:SetAsAlly()
_self_:SetAsCompanion()
_self_:Follow(player, 150)
```

### 模板6：回复 + 选项
```lua
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

_self_:SayWithDialoguebox("你想让我做什么？")

local choice = UI.AskMany("请选择", {
    "跟着我",
    "给我点吃的",
    "没事了"
})

if choice == "跟着我" then
elseif choice == "给我点吃的" then
    -- 若人设愿意：Say + GiveItem(列表中的 id) + Toast；否则仅拒绝台词
elseif choice == "没事了" then
end
```

## 七、核心原则

1. 先判断简单意图还是复杂意图
2. 简单意图只生成短回复块
3. 复杂意图先回复再执行行为链
4. 动作之间使用 World.Wait 控制节奏
5. UI.AskMany 按选项文本分支
