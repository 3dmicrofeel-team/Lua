# Encounter 相关 LUA API 参考（符合 lua_atomic_modules_call_guide.md）

## 数据类型（必须严格遵循）
- FVector: `{X=0, Y=0, Z=0}`
- FRotator: `{Pitch=0, Yaw=0, Roll=0}`

## World（全局表）
- World.GetByID(uid) -> Actor|nil
- World.SpawnEncounter(loc, range, npcData, luaType, code) — loc=FVector, npcData={uid=type}, luaType 如 "EnterVolume"
- World.SpawnEnemy(id, loc, count) -> Actor[] — id 来自 DT_EnemyDataTable
- World.SpawnEnemyAtPlayer(id, count) -> Actor[]
- World.DestroyByID(uid) -> nil — 按 ID 销毁 NPC/Actor
- World.Destroy(obj) -> nil — 按对象销毁
- World.Wait(seconds) -> nil（异步）

## UI（异步）
- UI.Toast(text) -> nil
- UI.ShowDialogue(name, text) -> nil|any
- UI.Ask(msg, btnA, btnB) -> bool|string — 返回选中按钮文案，比较用 if r == "btnA文案"
- UI.AskMany(title, options) -> any — options 为数组，返回选中项字符串
- UI.PlayMiniGame(gameType, lv) -> string|any — 播放迷你游戏，返回 "Success" 等，用于对弈/赌局/挑战

## Entity 接口（obj:Method）
- obj:IsValid() -> bool
- obj:GetPos() -> FVector
- obj:Destroy() -> nil — 销毁自身
- obj:SetVisible(show) -> nil — 隐藏/显示

## Performer 接口（npc:Method，NPC 须实现）
- npc:ApproachAndSay(target, text) -> nil（异步）
- npc:LookAt(target) -> nil
- npc:PlayAnim(animName) -> nil（异步）— 仅 Drink
- npc:PlayAnimLoop(animName, time) -> nil — Happy, Frustrated, Wave, Stagger, Scared, Sleep, Sing, Dance, Idle, Shy
- npc:SetAsHostile() -> string（异步）
- npc:SetAsAlly() -> nil
- npc:SetAsCompanion() -> nil — 邀请该 NPC 成为同伴，调用后建议 UI.Toast("XXX成为同伴")
- npc:GiveItem(id, count) -> nil — id 来自 DT_Items
- npc:GiveWeapon(id, count) -> nil
- npc:GiveEquip(id, count) -> nil
