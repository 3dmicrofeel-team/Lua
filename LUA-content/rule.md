Encounter 系统开发档案（Lua + World.SpawnEncounter Pipeline）
版本信息

系统：CineText + Narrative

语言：Lua

Encounter 容器：World.SpawnEncounter(...)

Trigger 类型：EnterVolume

当前主要目标：支持开放世界内多个奇遇（1~N个）

1. 系统目标与核心概念
1.1 系统目标

实现一个可扩展的 Encounter（奇遇）系统，使开发者可以：

在地图中布置多个 Encounter。

每个 Encounter 在玩家进入触发范围时执行一次剧情逻辑。

Encounter 内可以：

生成 NPC / 敌人

播放动画 / 对话

提供 UI 选择

触发战斗（hostile）

发放奖励（item/weapon/equip）

播放 UI 特效（Fade / Toast / MiniGame）

1.2 Encounter 定义（关键结构）

一个 Encounter 必须包含：

触发位置 loc

触发范围 range

参与 NPC 数据表 npcData

触发方式 luaType（当前固定 EnterVolume）

执行脚本 code（Lua string）

最终统一封装为：

World.SpawnEncounter(
    loc,
    range,
    npcData,
    "EnterVolume",
    code
)

2. 全局工作流（从0到1搭建一个奇遇世界）

整个项目开发的流程固定为：

Setup 初始化地图（一次性）

Build 世界（一次性）

生成常驻 NPC / 路人（可选）

注册多个 Encounter（1~N个）

StartGame + Resume Time（一次性）

3. 标准脚本结构规范（必须遵循）
3.1 主脚本结构（推荐工程组织）

程序员必须将脚本拆分为以下结构：

Setup_World.lua（地图生成、建筑、prop、spawn点）

Spawn_AmbientNPC.lua（路人NPC、常驻NPC）

Encounters/enc_*.lua（每个奇遇独立文件）

Main.lua（统一加载顺序，最后启动游戏）

3.2 Main.lua 的标准加载顺序（硬规则）
Time.Pause()

-- 1) build world
require("Setup_World")

-- 2) spawn ambient NPC
require("Spawn_AmbientNPC")

-- 3) register encounters
require("Encounters.enc_firstmeet")
require("Encounters.enc_profiteer")
require("Encounters.enc_paybill")
require("Encounters.enc_dance")
require("Encounters.enc_ttt")

World.StartGame()
Time.Resume()
UI.Toast("游戏开始")

强制要求

所有 Encounter 必须在 World.StartGame() 前注册。

Time.Pause() 必须在 Build 之前调用，防止 build 过程世界乱动。

Time.Resume() 必须在所有 encounter 注册完成后调用。

4. Setup 初始化模块规范（World Setup）
4.1 Setup 模块的目标

完成地图的“舞台搭建”：

创建地图

生成地形

添加 Block

添加建筑

放置 props（装饰、场景物）

添加 spawn point（玩家出生点）

添加 NPC spawn / Enemy spawn

Validate + Build

4.2 Setup 模块必须使用的 API
地图控制

Env.CreateMap(w,h,cellSize)

Env.SetMapName(map,name)

Env.SetMapTheme(map,theme)

Env.ValidateMap(map)

Env.BuildAsync(map)

地形塑造

Env.SetTerrainHeight(map,x,y,h)

Env.FlattenTerrain(map,center,radius,height)

Env.RaiseTerrain(map,center,radius,height,falloff)

Env.LowerTerrain(map,center,radius,depth,falloff)

Env.GenMountainRange(map,start,end,height,width)

Env.PaintTerrain(map,x,y,radius,material)

Block / 建筑

Env.AddBlock(map,name,pos,size)

Env.SetBlockType(block,type)

Env.SetBlockRotation(block,yawDeg)

Env.SetBlockProperty(block,key,val)

Env.AddBuilding(block,pos,size,style,rot)

Env.SetBuildingType(building,type)

Env.AddBuildingFloor(building,height)

Props / 装饰

Env.AddProp(block,id,pos,rot)

Env.IsSpaceEmpty(block,pos,size2D)

Env.FindEmptySpace(block,size2D)

Spawn点

Env.AddSpawnPoint(block,tag,pos)

Env.AddNPCSpawn(block,id,pos,rot)

Env.AddEnemySpawn(block,id,pos,radius)

4.3 Setup 推荐输出数据（重要）

程序员应当在 Setup 阶段输出一个 WorldAnchorTable（Lua table），供 Encounter 选点使用。

示例：

_G.WorldAnchors = {
    Tavern = {X=18900, Y=20600, Z=4801},
    Fountain = {X=18800, Y=21000, Z=4801},
    Market = {X=19000, Y=22000, Z=4801},
    NorthRoad = {X=13700, Y=15500, Z=4801}
}


这样 AI Planner 后续可以根据语义选点，而不是写死坐标。

5. 常驻 NPC 填充模块（Ambient NPC）
5.1 目标

用于增强世界真实感，与 Encounter 无直接依赖。

5.2 API

World.SpawnNPC(type,name,loc)

示例：

World.SpawnNPC("Merchant_Male","stranger",{X=18123,Y=21699,Z=4801})
World.SpawnNPC("Hunter_Male","fountain",{X=18807,Y=21029,Z=4801})

6. Encounter 开发规范（核心）
6.1 Encounter 文件结构模板（必须统一）

每个 Encounter 文件必须严格遵循以下结构：

local function ResolveEncounterLoc()
    return {X=0, Y=0, Z=0}
end

function SpawnEncounter_XXXX()
    local npcData = {
        encXX_A = "Default"
    }

    local code = [[
        if _G.encXX_done then return end
        _G.encXX_done = true

        local player = World.GetByID("Player")
        local npcA = World.GetByID("encXX_A")

        if not player or not player:IsValid() then return end
        if not npcA or not npcA:IsValid() then return end

        UI.Toast("触发奇遇")
        npcA:ApproachAndSay(player, "你好。")
    ]]

    local loc = ResolveEncounterLoc()
    return World.SpawnEncounter(loc, 200.0, npcData, "EnterVolume", code)
end

SpawnEncounter_XXXX()

6.2 Encounter 的硬性规则（必须遵守）
Rule 1：必须防止重复触发

每个 encounter 必须有：

if _G.encXX_done then return end
_G.encXX_done = true

Rule 2：必须做对象合法性检查

必须对 player 和所有 NPC 做：

if not obj or not obj:IsValid() then return end


否则会导致 runtime crash。

Rule 3：Encounter 内禁止使用未注册 API

只能使用你的 API 文档内存在的函数。

Rule 4：所有 UI.Ask / AskMany 必须处理返回值

UI.Ask 可能返回 string/bool，因此必须写成兼容式逻辑。

推荐写法：

local r = UI.Ask("?", "A", "B")
if r == true or r == "A" then
    ...
else
    ...
end

Rule 5：所有奖励必须调用 GiveItem/GiveWeapon/GiveEquip

Toast 不算奖励，必须执行：

npc:GiveItem(id,count)

npc:GiveWeapon(id,count)

npc:GiveEquip(id,count)

7. Encounter Code 内可用功能模块（程序员实现参考）

Encounter code 内逻辑建议拆为 6类模块：

7.1 剧情展示模块（Dialogue / Story Beat）

推荐组合：

UI.Toast()

UI.ShowDialogue()

npc:ApproachAndSay()

npc:LookAt()

示例：

UI.Toast("你走进酒馆。")
npc:ApproachAndSay(player, "欢迎。")
UI.ShowDialogue("玩家", "我只是路过。")

7.2 动画模块（Animation Beat）

npc:PlayAnim()

npc:PlayAnimLoop()

World.Wait()

示例：

npc:PlayAnimLoop("Happy", 0)
World.Wait(1.0)

7.3 分支交互模块（Choice / Branching）

UI.Ask()

UI.AskMany()

示例：

local choice = UI.Ask("你要怎么做？", "战斗", "离开")
if choice == "战斗" then
    ...
else
    ...
end

7.4 战斗触发模块（Combat Trigger）

npc:SetAsHostile()

npc:SetAsAlly()

示例：

UI.Toast("战斗开始！")
enemy:SetAsHostile()

7.5 奖励模块（Reward）

npc:GiveItem()

npc:GiveWeapon()

npc:GiveEquip()

示例：

npc:GiveWeapon("FireSword", 1)
UI.Toast("获得 FireSword")

7.6 迷你游戏模块（MiniGame）

UI.PlayMiniGame(gameType, lv)

示例：

local result = UI.PlayMiniGame("TTT", 3)
if result == "Success" then
    UI.Toast("你赢了！")
end

8. Encounter 设计参数规范（建议统一）

每个 Encounter 在设计层需要这些参数：

参数	类型	示例	说明
encounter_id	string	enc07	唯一ID
encounter_name	string	Profiteer	用于代码函数名
loc	FVector	{X=...,Y=...,Z=...}	触发点
range	number	200~400	EnterVolume半径
npcData	table	{enc07_A="Default"}	参与NPC
requires_companion	bool	true	是否依赖 Companion_0
reward	table	{"FireSword",1}	奖励
one_time	bool	true	是否一次性触发
9. Encounter 编码标准（强制约束）
9.1 NPC ID 命名规范

必须使用：

encXX_<RoleName>

示例：

enc07_rogue1

enc07_rogue2

enc06_oldman

原因：

保证 World.GetByID("enc07_rogue1") 能稳定取到对象。

9.2 Companion 固定引用规范

如果需要同伴 Alice，必须使用：

local alice = World.GetByID("Companion_0")


并做检查：

if not alice or not alice:IsValid() then return end

9.3 事件节奏规范（必须有 Wait）

推荐每段台词/动作之间至少：

World.Wait(0.8 ~ 1.5)

否则剧情会在同一帧执行完，体验很差。

10. 推荐 Encounter 模板（可直接复制用）
10.1 标准剧情对话 Encounter 模板
function SpawnEncounter_TemplateStory()
    local npcData = {
        enc99_npc = "Default"
    }

    local code = [[
    if _G.enc99_done then return end
    _G.enc99_done = true

    local player = World.GetByID("Player")
    local npc = World.GetByID("enc99_npc")

    if not player or not player:IsValid() then return end
    if not npc or not npc:IsValid() then return end

    UI.Toast("你听到远处传来脚步声。")
    npc:ApproachAndSay(player, "旅行者，你愿意帮我一个忙吗？")

    World.Wait(1.0)

    local choice = UI.Ask("你要怎么做？", "帮忙", "拒绝")
    if choice == "帮忙" then
        npc:PlayAnimLoop("Happy", 0)
        World.Wait(1.0)
        npc:ApproachAndSay(player, "谢谢你。")
        npc:GiveItem("Money", 20)
        UI.Toast("获得金币 +20")
    else
        npc:PlayAnimLoop("Frustrated", 0)
        World.Wait(1.0)
        npc:ApproachAndSay(player, "好吧，我不会忘记的。")
    end
    ]]

    local loc = {X=0,Y=0,Z=0}
    return World.SpawnEncounter(loc, 200.0, npcData, "EnterVolume", code)
end

10.2 战斗 Encounter 模板
function SpawnEncounter_TemplateCombat()
    local npcData = {
        enc88_enemy1 = "Assassin_Male",
        enc88_enemy2 = "Ironworker_Male"
    }

    local code = [[
    if _G.enc88_done then return end
    _G.enc88_done = true

    local player = World.GetByID("Player")
    local e1 = World.GetByID("enc88_enemy1")
    local e2 = World.GetByID("enc88_enemy2")

    if not player or not player:IsValid() then return end
    if not e1 or not e1:IsValid() then return end
    if not e2 or not e2:IsValid() then return end

    UI.Toast("两个陌生人挡住了你的去路。")
    e1:ApproachAndSay(player, "把钱交出来！")
    World.Wait(0.8)
    e2:ApproachAndSay(player, "不然别怪我们不客气。")

    local choice = UI.Ask("你要怎么做？", "战斗", "逃跑")
    if choice == "战斗" then
        UI.Toast("战斗开始！")
        e1:SetAsHostile()
        e2:SetAsHostile()
    else
        UI.Toast("你选择离开。")
    end
    ]]

    local loc = {X=0,Y=0,Z=0}
    return World.SpawnEncounter(loc, 300.0, npcData, "EnterVolume", code)
end

11. AI Planner / 自动生成 Encounter 的开发接口（给程序员的要求）

如果要实现“输入自然语言故事 → 自动生成 encounter 脚本”，程序员需要实现以下组件：

11.1 输入（Input）

AI Planner 输入应包含：

story outline（自然语言）

world anchors（地图关键点）

available NPC types（可用 NPC 类型表）

available items（可用道具 row keys）

encounter count（生成几个 encounter）

11.2 输出（Output）

AI Planner 输出必须是：

Encounters/enc_*.lua 多个文件

每个文件都必须包含一个 SpawnEncounter_XXX() 并自动执行

最终 main.lua require 即可运行

12. Debug / 稳定性策略（必须写入开发规范）
12.1 必须用 pcall 防御 Env 模块崩溃

你 Setup 里已经用 pcall 包装：

Env.GetPropGridSize

Env.IsSpaceEmpty

Env.FindEmptySpace

这一策略必须保留。

12.2 Encounter 内禁止复杂循环生成（避免卡顿）

Encounter code 内不应进行大规模随机生成（Perlin、批量 Spawn），这些必须放在 Setup 阶段完成。

12.3 每个 Encounter 的范围 range 推荐值

1 NPC 对话：100~200

2 NPC + 分支：200~300

战斗/多 NPC：300~450

13. 函数分类清单（交付给程序员）
13.1 世界初始化类

Time.Pause / Resume

Env.CreateMap / ValidateMap / BuildAsync

World.StartGame

13.2 地形与布局类

Env.SetTerrainHeight

Env.FlattenTerrain / RaiseTerrain / LowerTerrain

Env.PaintTerrain

Env.GenMountainRange

13.3 Block / Building 类

Env.AddBlock / SetBlockType / SetBlockRotation / SetBlockProperty

Env.AddBuilding / AddBuildingFloor / SetBuildingType

13.4 Props 类

Env.AddProp

Env.IsSpaceEmpty

Env.FindEmptySpace

13.5 Spawn 类（预设 spawn marker）

Env.AddSpawnPoint

Env.AddNPCSpawn

Env.AddEnemySpawn

13.6 Runtime Spawn 类（运行时动态生成）

World.SpawnNPC

World.SpawnEnemy

World.SpawnEnemyAtPlayer

World.SpawnTrigger

World.SpawnEncounter

13.7 查询与销毁类

World.GetByID

World.Find / FindNearest / GetAll

World.Destroy / DestroyByID

13.8 UI 类

UI.Toast

UI.ShowDialogue

UI.Ask / AskMany

UI.FadeIn / FadeOut

UI.PlayMiniGame

13.9 NPC 行为类

npc:MoveTo / MoveToActor

npc:LookAt

npc:ApproachAndSay

npc:PlayAnim / PlayAnimLoop

npc:SetAsHostile / SetAsAlly

npc:GiveItem / GiveWeapon / GiveEquip

13.10 Entity 基础类

obj:IsValid

obj:GetPos / Teleport

obj:SetVisible / SetCollision

obj:AddTag / HasTag / RemoveTag

obj:AddTrigger

13.11 Math 随机类

Math.RandInt / RandFloat

Math.PerlinNoise2D

Math.Clamp 等

14. 最终交付标准（程序员验收用）

开发完成后，必须满足：

main.lua 执行后不会报错

Setup 世界生成正确

玩家进入每个 Encounter 范围时触发剧情

每个 Encounter 只触发一次（_G.enc_done 生效）

UI 分支逻辑正确

战斗触发正确（hostile）

奖励发放真实有效（GiveItem/GiveWeapon/GiveEquip）

多 Encounter 可以同时存在，不互相冲突

Encounter NPC ID 不重复

Companion_0 引用不会导致 crash（必须做 IsValid 检查）

15. 程序员最重要的实现建议（你这个系统的核心技巧）
建议 1：强制 Encounter ID Registry

程序员应该维护一个表：

_G.EncounterRegistry = {
    "enc00_firstmeet",
    "enc07_profiteer",
    "enc03_paybill",
    "enc02_dance",
    "enc06_ttt"
}


用于 debug 和未来存档系统。

建议 2：统一封装 Encounter Template

建议程序员写一个 helper：

function RegisterEncounter(encId, loc, range, npcData, code)
    return World.SpawnEncounter(loc, range, npcData, "EnterVolume", code)
end


让生成器更稳定。

16. 结论：完整开发流程总结（最简工程视角）

如果要完成一个“包含多个奇遇”的开放世界，程序员只需要按下面步骤执行：

Step 1 Setup
用 Env 系列 API 创建地图 + Build。

Step 2 Ambient
用 World.SpawnNPC 填充路人。

Step 3 Encounters
每个 Encounter 写一个 SpawnEncounter_XXX()，调用 World.SpawnEncounter。

Step 4 Runtime Logic
在 code 字符串里写剧情逻辑（UI + NPC行为 + 奖励）。

Step 5 StartGame
World.StartGame + Time.Resume。