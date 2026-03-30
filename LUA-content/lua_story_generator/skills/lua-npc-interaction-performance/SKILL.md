---
name: lua-npc-interaction-performance
description: Generates LUA for NPC 思考 (表演/演绎). Use when UE/Web sends Type=NPC_Think_Begin, Code={NPCInfo, TagList}. Combines personality + environment; may use MoveTo/GetPos/World.Find/HasTag, Time, Math, World FX/sound. Chain for props locate → move → say + anim.
---

# LUA NPC 思考 / 表演 Skill

## 何时加载

当 UE/Web 端传入 `Type=NPC_Think_Begin`、`Code={NPCInfo, TagList}` 时，根据 NPC 信息与**周围可互动对象（TagList）**生成表演 LUA。NPCInfo 含 Favorability、MoralTendency、Personality（大五）、Goals（长期/中期/短期）、Memory。

**「思考」定义**：像真人一样，在**性格 + 目标 + 记忆 + 当前环境（TagList）**下决定**做什么、说什么**；可原地表演，也可**走向某处再演**（例如上台跳舞、去吧台喝酒）。

## 可用 API（分层）

### 1. 表演核心（`_self_`）

使用 **`_self_`** 指代当前 NPC，调用格式 `_self_:函数名(...)`。

| 函数 | 说明 | 适用场景 |
|------|------|----------|
| _self_:Say(Text) | 头顶气泡台词，挂起至展示结束（默认约 3 秒） | 任意台词 |
| _self_:PlayAnim(AnimName) | **一次性**蒙太奇，**仅** DT_MontageTable（如 Attack、Drink） | 短手势、举杯、攻击 |
| _self_:PlayAnimLoop(AnimName, Time) | **持续**时间，**仅** DT_AnimStartTable（Wave、Happy、Idle、Sit、Sleep…） | 挥手、跳舞感、久坐、闲聊姿态 |
| _self_:MoveTo(loc) | **异步**，走到世界坐标；返回值常见 `Success` / `Fail` | 走向舞台、吧台、椅子附近 |
| _self_:MoveToActor(target) | **异步**，走到某 Actor 旁 | 走向可互动物体或玩家 |
| _self_:LookAt(target) | 注视目标 | 到达后看向吧台/舞台/玩家 |
| _self_:ApproachAndSay(target, text) | **异步**，靠近并说（一步到位的社交接近） | 优先走向玩家说话时使用 |
| _self_:GetPos() | 当前位置 `FVector` | 作为 `World.Find` 的圆心 |

说明：`MoveTo` / `MoveToActor` / `ApproachAndSay` 为异步，结束后接 `World.Wait` 再接 Say/动画，节奏更自然。

### 2. 环境与检索（`World` + `Entity`）

用于「根据 TagList 找到想去的目标」或取坐标。

| API | 说明 |
|-----|------|
| `World.GetByID(uid)` | 若 UE 侧为互动物体配置了稳定 ID，可直接取 Actor |
| `World.Find(type, center, radius)` | 在半径内按类型查一组 Actor；`center` 常用 `_self_:GetPos()` |
| `World.FindNearest(type, pos)` | 取最近一个 |
| `obj:GetPos()` | 目标位置，用于 `MoveTo` |
| `obj:HasTag(tag)` | TagList 与场景物体 tag 对齐时，遍历 `Find` 结果筛选 |

生成时**优先**与输入 TagList 一致：若列表含 `Stage`、`Bar`、`Chair` 等，应映射到**具体行为**（见下表），再决定是原地演还是**先移动再演**。

### 3. 时间与氛围（可选）

| API | 思考用途 |
|-----|----------|
| `Time.GetHour()` / `Time.IsNight()` | 深夜更可能去酒吧、情绪低落或兴奋；清晨偏清醒台词 |
| `Time.GetTimeString()` | 偶尔在台词里带一句时间感 |
| `World.SetWeather(type)` | **慎用**（改全局天气）；仅当性格「戏剧化」且剧情需要时 |
| `World.PlayFX(id, loc)` / `World.PlaySound(id, loc)` | 到达舞台时轻量氛围（若项目有对应 id） |

### 4. 随机与犹豫（`Math`，可选）

| API | 思考用途 |
|-----|----------|
| `Math.Chance(p)` | 内向 NPC 对某道具「想靠近又犹豫」时分支 |
| `Math.RandInt(1, n)` | 在多个可互动 Tag 间**加权随机**选一个（仍须符合性格，不能乱跳） |

## TagList × 性格 → 行为构思（须多样化）

同一 Tag 不同性格应不同：**外向**可能主动上台；**内向**可能只在台下看或角落坐；**高尽责**可能整理椅子；**低宜人性**可能霸占吧台。

| 环境 Tag（示例） | 可生成的行为思路（结合 DT 动画表选名） |
|------------------|----------------------------------------|
| Stage / 舞台 | 上台 → `MoveTo` 舞台区域 → `PlayAnimLoop`（偏舞蹈/展示类，若表中有）或 Happy/Wave；台词：表演欲、紧张、邀请玩家 |
| Bar / 吧台 | 走向吧台 → `LookAt` → `PlayAnim` Drink 或 `PlayAnimLoop` Sit 久坐；台词：放松、借酒消愁、社交 |
| Chair / Seat | `MoveTo` 座位旁 → Sit/Idle；台词：休息、观察 |
| Food | 靠近食物相关点 → Eat（若 AnimStart 有）或 Happy；台词：饥饿、挑剔 |
| Player / 玩家在 TagList 中 | `LookAt(player)`、`ApproachAndSay(player, "...")` 或 `MoveToActor(player)` |

**到达型行为链（推荐顺序）**：

1. `local myPos = _self_:GetPos()`（或已知目标 ID）
2. 解析目标：`GetByID` → 或 `World.Find` + `HasTag` 匹配 TagList 中一项
3. `local loc = target:GetPos()`（可在目标旁微调偏移则用 `Math` 向量运算，可选）
4. `local r = _self_:MoveTo(loc)`（或 `MoveToActor(target)`）
5. `World.Wait(0.3~0.6)`
6. `if r == "Success"` then `_self_:LookAt(...)` → `_self_:Say(...)` → `PlayAnim` / `PlayAnimLoop`
7. `MoveTo` 失败则**不要硬演在原地假装到了**；应改台词（「太挤了」「改天吧」）或换近处 Tag

## 生成原则

生成的台词和行为**必须同时反映**：TagList、Personality、Goals（尤其 ShortTerm）、可选 Favorability / MoralTendency / Memory。

- **TagList**：至少**呼应一项**环境对象；若多个 tag，按性格**选一个主行为**（或 Chance 次要尝试），避免脚本过长。
- **Personality（大五）**：外向→多移动、多互动；内向→少动、短句、角落；开放→愿试舞台；尽责→少酗酒胡闹等（可按设定微调）。
- **Goals**：ShortTerm 决定「当下为何走过去」；LongTerm 可偶尔在台词里露一句。
- **PlayAnim vs PlayAnimLoop**：短动作→PlayAnim；持续状态→PlayAnimLoop。
- **动画名**：必须从当前 **DT_MontageTable / DT_AnimStartTable** 选，禁止编造表中不存在的名字。

## 动画库（DataTable 路径：ChronicleForge/Doc/DataTable）

- **PlayAnim**（一次性）：`DT_MontageTable.csv`
- **PlayAnimLoop**（持续）：`DT_AnimStartTable.csv`

两表**互不混用**；策划新增行即对生成器生效。

## 输出格式

### 原地表演（仅 Say + 动画）

```lua
_self_:Say("生成的台词")
_self_:PlayAnim("Drink")
_self_:PlayAnimLoop("Wave", 0)
```

### 走向环境再表演（TagList 驱动）

```lua
local player = World.GetByID("Player")
local stage = World.GetByID("Prop_Stage_Main")  -- 若 UE 提供稳定 ID；否则用 Find + HasTag("Stage") 筛选

if stage and stage:IsValid() then
    local loc = stage:GetPos()
    local r = _self_:MoveTo(loc)
    World.Wait(0.5)
    if r == "Success" then
        if player and player:IsValid() then _self_:LookAt(player) end
        _self_:Say("这台上……正适合活动一下筋骨。")
        _self_:PlayAnimLoop("Happy", 4.0)   -- 时长按语境；表中有 Dance 等则优先
    else
        _self_:Say("人太多了，改天再上吧。")
    end
end
```

### 吧台示例（移动 + Drink）

```lua
local bar = World.FindNearest("Interactive", _self_:GetPos())  -- type 以项目为准；可改为 Find + HasTag("Bar")
if bar and bar:IsValid() and bar:HasTag("Bar") then
    local r = _self_:MoveToActor(bar)
    World.Wait(0.4)
    if r == "Success" then
        _self_:Say("来一杯。今天算我的。")
        _self_:PlayAnim("Drink")
    end
end
```

- **PlayAnim**：仅 Montage 表。
- **PlayAnimLoop**：仅 AnimStart 表；根据 TagList / 性格 / 情境选**多样**动画，避免每段都是 Dialogue。
- 对象获取后**务必** `IsValid()`；`Find`/`FindNearest` 的 `type` 字符串需与项目里叙事注册一致，不确定时在注释中标明「由程序/策划约定」。
