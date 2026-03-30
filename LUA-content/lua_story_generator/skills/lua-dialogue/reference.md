# 对话模式 LUA API 参考

当 ChronicleForge/Doc/Lua_Function(for AI) 无对应文件时，使用本参考。

## World
- World.GetByID(uid) -> Actor|nil
- World.Wait(seconds) -> nil（异步）
- World.Find(...) / World.FindNearest(...) / World.GetAll(...)

## UI
- UI.Toast(text) -> nil
- UI.Ask(msg, btnA, btnB) -> bool — 按布尔分支
- UI.AskMany(title, options) -> string — 返回选中项文案，按 if choice == "选项文本" 分支

## Entity
- obj:IsValid() -> bool

## Performer（_self_: 指代当前 NPC）
- _self_:LookAt(target) -> nil
- _self_:SayWithDialoguebox(Text) -> nil — 对话模式专用，NPC 前对话框
- _self_:PlayAnim(animName) -> nil — 一次性，仅 DT_MontageTable
- _self_:PlayAnimLoop(animName, time) -> nil — 持续，仅 DT_AnimStartTable
- _self_:Follow(target, distance) -> nil
- _self_:GiveItem(id, count) -> nil
- _self_:GiveWeapon(id, count) -> nil
- _self_:GiveEquip(id, count) -> nil
- _self_:SetAsAlly() -> nil
- _self_:SetAsCompanion() -> nil
- _self_:SetAsHostile() -> nil
- _self_:SetCombatInvalid() / SetCombatValid() -> nil

## Time
- Time.AddOnceSchedule(callback, delay) -> nil
- Time.AddDailySchedule(...) -> nil
