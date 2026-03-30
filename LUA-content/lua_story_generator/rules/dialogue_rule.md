一、对话模式的总体目标

对话模式的核心目标是：

根据玩家输入，生成 NPC 的语言与行为反应。

输出可能包括：

NPC 回复一句话

NPC 回复 + 动作

NPC 回复 + 行为链

NPC 回复 + 选项分支

NPC 回复 + 状态变化

NPC 回复 + 物品反馈

NPC 回复 + 后续调度

因此，对话模式本质是：

Dialogue → Behavior Chain

二、对话模式的总体流程

整个 AI 调度流程分为 四个阶段：

玩家输入
   ↓
意图分类
   ↓
行为规划
   ↓
Lua生成
三、第一阶段：意图分类（Intent Classification）

对话模式下只区分 两种意图类型：

1 简单意图（Simple Intent）

特点：

只需要一句回复

或一句回复 + 一个轻动作

不引发连续行为链

不改变重要状态

不触发 UI 分支

通常不发放物品（若主 Prompt 已注入 DT_Items 列表，NPC 可因开心主动赠礼或回应玩家索要，见「物品交付」）

不安排未来事件

典型例子

玩家说：

你好
你是谁
今天天气不错
你在干什么
你看起来很累
输出结构（对话模式怼脸镜头，无需 LookAt）

PlayAnim/PlayAnimLoop（每句话必有对应动作）
→ Say
2 复杂意图（Complex Intent）

特点：

NPC 回复后会执行 一个或多个额外动作。

可能包括：

移动

接近

跟随

状态变化

物品交付

UI 选择

未来调度

典型例子

玩家说：

给我点吃的
跟着我
去那边看看
你觉得我们该怎么办
明天早上来找我
输出结构
Reply
→ Additional Actions
→ Optional Branch / Reward / State Change
四、第二阶段：Reference 选择

AI 不直接调用所有函数库，而是按需求选择 reference。

需求	Reference
NPC行为	Performer
环境查询	World
对话UI	UI
时间调度	Time

例如：

简单回复

使用：

Performer
World

例如：

LookAt
Say
需要物品

使用：

Performer
UI

例如：

Say
GiveItem
Toast
需要选择分支

使用：

UI
Performer

例如：

AskMany
branch
需要未来事件

使用：

Time
Performer

例如：

Say
AddOnceSchedule
五、第三阶段：行为规划（Action Planning）

AI 不应直接写 Lua，而应先规划行为顺序。

推荐统一顺序：

Resolve Targets
→ Validate
→ Reply
→ Orientation / Movement
→ Animation
→ Item / State / UI
→ Schedule
→ Exit
例1：简单意图

玩家：

你好

规划：

resolve player
look at player
say greeting
例2：复杂意图（请求食物）

玩家：

给我点吃的

规划：

resolve player
look at player
reply acknowledgement
give item
toast
例3：复杂意图（请求跟随）

玩家：

跟着我

规划：

resolve player
reply confirmation
set ally
set companion
follow player
例4：复杂意图（选择）

玩家：

你觉得我们该怎么办

规划：

look at player
say
AskMany
branch
六、第四阶段：Lua生成规则

AI 最终输出 Lua 行为代码。

生成 Lua 时必须遵守以下规则。

七、Lua编写规则
规则1：所有对象先获取再判定
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

原因：

防止对象不存在导致脚本崩溃。

规则2：NPC动作使用冒号语法
npc:Say("Hello")
npc:MoveToActor(player)
npc:PlayAnimLoop("Wave", 0)   -- Wave 在 DT_AnimStartTable，必须用 PlayAnimLoop

不允许：

npc.Say("Hello")
规则3：可见动作之间加入等待
npc:LookAt(player)
World.Wait(0.3)
npc:PlayAnimLoop("Wave", 0)   -- Wave 在 DT_AnimStartTable，必须用 PlayAnimLoop
World.Wait(0.5)
npc:Say("你好")

这样动作更自然。

规则4：复杂意图必须先回复

复杂意图不能直接执行行为。

必须先说一句回应。

npc:Say("好，我来看看。")
World.Wait(0.5)

再执行动作。

规则5：UI.AskMany 按选项文本分支

新的 UI 规则：

local choice = UI.AskMany("请选择", {
    "跟着我",
    "给我点吃的",
    "没事了"
})

if choice == "跟着我" then
elseif choice == "给我点吃的" then
elseif choice == "没事了" then
end
规则6：UI.Ask 按布尔值分支
local accept = UI.Ask("是否接受？", "接受", "拒绝")

if accept then
else
end
规则7：物品交付必须使用 Give 系列
npc:GiveItem("Bandage",1)
npc:GiveEquip("IronArmor",1)
npc:GiveWeapon("Sword",1)

推荐搭配：

Say
Give
Toast
规则8：关系变化必须使用状态接口
npc:SetAsHostile()
npc:SetAsAlly()
npc:SetAsCompanion()
npc:SetCombatInvalid()
npc:SetCombatValid()
规则9：环境查询必须使用 World 接口

例如：

World.Find
World.FindNearest
World.GetAll
World.GetByID
规则10：未来事件必须使用 Time 接口
Time.AddOnceSchedule
Time.AddDailySchedule
八、标准 Lua 输出模板
模板1：简单回复（动画根据 context 选，如打招呼用 Wave、高兴用 Happy）
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

npc:PlayAnimLoop("Wave", 0)
World.Wait(0.3)
npc:Say("你好。")
模板2：回复 + 动作
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

npc:PlayAnimLoop("Wave", 0)   -- Wave 在 DT_AnimStartTable，必须用 PlayAnimLoop
World.Wait(0.5)
npc:Say("很高兴见到你。")
模板3：回复 + 物品（给东西用 Give）
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

npc:PlayAnimLoop("Give", 0)
World.Wait(0.3)
npc:Say("给你。")
World.Wait(0.5)

npc:GiveItem("Bandage",1)
UI.Toast("获得了面包")
模板4：回复 + 跟随
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

npc:Say("好，我跟着你。")
World.Wait(0.5)

npc:SetAsAlly()
npc:SetAsCompanion()
npc:Follow(player,150)
模板5：回复 + 选项
local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

npc:Say("你想让我做什么？")

local choice = UI.AskMany("请选择", {
    "跟着我",
    "给我点吃的",
    "没事了"
})

if choice == "跟着我" then

elseif choice == "给我点吃的" then

elseif choice == "没事了" then

end
九、对话模式的核心原则

最终可以总结为五条原则：

先判断简单意图还是复杂意图

简单意图只生成短回复块

复杂意图先回复再执行行为链

动作之间使用 World.Wait 控制节奏

UI.AskMany 按选项文本分支