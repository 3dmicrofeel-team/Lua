# Lua 原子模块全量 API 文档（CineText + Narrative）

更新目标：
1. 列出当前代码里注册到 Lua 的全部 API（不是节选）。
2. 给出每个 API 的输入、返回和调用示例。
3. 增加 `Doc/datatable` 表格分析，并标注代码使用与返回结果。

代码基准：
- `Plugins/CineText/Source/CineText/Private/Event/CineTextEventLibRegister.cpp`
- `Source/AIGame/Private/Narrative/Core/Narrative*Register.cpp`
- `Source/AIGame/Public/Narrative/**/*.h`
- `Source/AIGame/Public/WorldEnvironment/EnvWorldBlueprintLibrary.h`
- `Source/AIGame/Private/Narrative/World/NarrativeWorldLibrary.cpp`
- `Source/AIGame/Private/Narrative/Interfaces/NarrativePerformerInterface.cpp`

## 1. 通用约定

| 项 | 约定 |
|---|---|
| `FVector` | `{X=0,Y=0,Z=0}` |
| `FRotator` | `{Pitch=0,Yaw=0,Roll=0}` |
| `FIntPoint` | `{X=0,Y=0}` |
| `TArray<T>` | Lua 数组（1 开始） |
| `TMap<K,V>` | Lua 字典表 |
| 同步 API | 直接返回 C++ 返回值 |
| 异步 API | 协程 `yield`，由 `UCineTextLatentHandle:Finish*` 恢复并返回 |

异步恢复值：
- `Finish()` -> `nil`
- `FinishWithString(s)` -> `string`
- `FinishWithInt(i)` -> `number`
- `FinishWithBool(b)` -> `boolean`

## 2. CineText 全量 API

### 2.1 `Event`（全局表）【预留程序实现，没有效果时装】

- `Event.On(eventName, callback)` -> `nil`
示例：`Event.On("NPCDeath", function(npc,killer) Log(npc,killer) end)`
- `Event.Once(eventName, callback)` -> `nil`
示例：`Event.Once("QuestComplete", function(id) Log("done", id) end)`
- `Event.Off(eventName, callback)` -> `nil`
示例：`Event.Off("NPCDeath", myCb)`
- `Event.Clear(eventName)` -> `nil`
示例：`Event.Clear("NPCDeath")`

说明：回调返回 `true` 会触发执行器中断全部脚本（AbortAllScripts）。

## 3. Narrative 全量 API

### 3.1 `System`（全局表）

- `System.Exit()` -> `nil`
示例：`System.Exit()`
- `System.ExitAll()` -> `nil`
示例：`System.ExitAll()`
- `System.Restart()` -> `nil`（协程挂起并重启请求）
示例：`System.Restart()`
- `System.Pause()` -> `nil`（协程挂起）
示例：`System.Pause()`
- `System.Resume()` -> `nil`
示例：`System.Resume()`
- `System.IsRunning()` -> `bool`
示例：`if System.IsRunning() then Log("running") end`

### 3.2 `World`（全局表）


- `World.SpawnNPC(type, name, loc)` -> `Actor`
示例：`local n = World.SpawnNPC("Default", "npc_01", {X=100,Y=0,Z=0})`
- `World.SpawnEnemy(id, loc, count)` -> `Actor[]`
示例：`local es = World.SpawnEnemy("Spider_Minion_1", {X=300,Y=0,Z=0}, 3)`
- `World.SpawnEnemyAtPlayer(id, count)` -> `Actor[]`
示例：`local es = World.SpawnEnemyAtPlayer("Spider_Minion_1", 2)`
- `World.SpawnTrigger(loc, type, range, code)` -> `Actor`
示例：`local t = World.SpawnTrigger({X=0,Y=0,Z=0}, "EnterVolume", 300, "Log('hit')")`
- `World.SpawnEncounter(loc, range, npcData, luaType, code)` -> `Actor|nil`（当前实现返回 `nil`）
示例：`World.SpawnEncounter({X=0,Y=0,Z=0}, 400, {npc_a="Default"}, "EnterVolume", "Log('enc')")`
- `World.DestroyByID(uid)` -> `nil`
示例：`World.DestroyByID("enc01_smith")`
- `World.Destroy(obj)` -> `nil`
示例：`World.Destroy(target)`
- `World.GetByID(uid)` -> `Actor|nil`
示例：`local p = World.GetByID("Player")`
- `World.Find(type, center, radius)` -> `Actor[]`
示例：`local list = World.Find("Enemy", {X=0,Y=0,Z=0}, 1000)`
- `World.FindNearest(type, pos)` -> `Actor|nil`
示例：`local e = World.FindNearest("Enemy", {X=0,Y=0,Z=0})`
- `World.GetAll(type)` -> `Actor[]`
示例：`local allNpc = World.GetAll("NPC")`
- `World.PlayFX(id, loc)` -> `nil`
示例：`World.PlayFX("FX_Explosion", {X=0,Y=0,Z=0})`
- `World.PlaySound(id, loc)` -> `nil`
示例：`World.PlaySound("SFX_Hit", {X=0,Y=0,Z=0})`
- `World.PlaySound2D(id)` -> `AudioObject|nil`
示例：`local audio = World.PlaySound2D("BGM_1")`
- `World.StopSound(audioObj)` -> `nil`
示例：`World.StopSound(audio)`
- `World.SetTime(hour)` -> `nil`
示例：`World.SetTime(18.5)`
- `World.SetWeather(type)` -> `nil`
示例：`World.SetWeather("Rain")`
- `World.Wait(seconds)` -> `nil`（异步）
示例：`World.Wait(1.2)`
- `World.StartGame()` -> `nil`
示例：`World.StartGame()`

### 3.3 `UI`（全局表，已注册的 Lua API）

- `UI.Toast(text)` -> `nil`（异步）
示例：`UI.Toast("任务开始")`
- `UI.FadeOut(duration)` -> `nil`（异步）
示例：`UI.FadeOut(0.5)`
- `UI.FadeIn(duration)` -> `nil`（异步）
示例：`UI.FadeIn(0.5)`
- `UI.AskMany(title, options)` -> `any`（异步，取决于蓝图 `FinishWithX`）
示例：`local r = UI.AskMany("选择", {"A","B","C"})`
- `UI.ShowDialogue(name, text)` -> `nil|any`（异步）
示例：`UI.ShowDialogue("铁匠", "欢迎")`
- `UI.PlayMiniGame(gameType, lv)` -> `string|any`（异步）
示例：`local r = UI.PlayMiniGame("TTT", 2)`
- `UI.Ask(msg, btnA, btnB)` -> `bool|string|any`（异步，取决于蓝图）
示例：`local r = UI.Ask("接受吗?", "是", "否")`

说明：`UNarrativeUILibrary::HideAllUI/RestoreAllUI` 目前存在 C++ API，但未在 `NarrativeUIRegister` 注册到 Lua。

### 3.4 `Time`（全局表）

- `Time.GetInfo()` -> `table`
示例：`local t = Time.GetInfo()`
- `Time.GetDay()` -> `int`
示例：`local d = Time.GetDay()`
- `Time.GetHour()` -> `int`
示例：`local h = Time.GetHour()`
- `Time.GetMinute()` -> `int`
示例：`local m = Time.GetMinute()`
- `Time.GetTimeString()` -> `string`
示例：`Log(Time.GetTimeString())`
- `Time.IsNight()` -> `bool`
示例：`if Time.IsNight() then ... end`
- `Time.SetScale(scale)` -> `nil`
示例：`Time.SetScale(2.0)`
- `Time.GetScale()` -> `number`
示例：`local s = Time.GetScale()`
- `Time.SetHour(hour)` -> `nil`
示例：`Time.SetHour(9)`
- `Time.SetDay(day)` -> `nil`
示例：`Time.SetDay(3)`
- `Time.Pause()` -> `nil`
示例：`Time.Pause()`
- `Time.Resume()` -> `nil`
示例：`Time.Resume()`
- `Time.Reset()` -> `nil`
示例：`Time.Reset()`
- `Time.AddOnceSchedule(day, hour, script)` -> `int(eventId)`
示例：`local id = Time.AddOnceSchedule(2, 20, "Log('night')")`
- `Time.AddDailySchedule(hour, script)` -> `int(eventId)`
示例：`local id = Time.AddDailySchedule(6, "Log('morning')")`
- `Time.RemoveSchedule(eventId)` -> `bool`
示例：`local ok = Time.RemoveSchedule(id)`
- `Time.ClearAllSchedules()` -> `nil`
示例：`Time.ClearAllSchedules()`

### 3.5 `Entity` 接口（`obj:Method(...)`）

- `obj:IsValid()` -> `bool`
示例：`if obj:IsValid() then ... end`
- `obj:SetVisible(show)` -> `nil`
示例：`obj:SetVisible(false)`
- `obj:SetCollision(enable)` -> `nil`
示例：`obj:SetCollision(true)`
- `obj:Destroy()` -> `nil`
示例：`obj:Destroy()`
- `obj:GetPos()` -> `FVector`
示例：`local p = obj:GetPos()`
- `obj:GetRot()` -> `FRotator`
示例：`local r = obj:GetRot()`
- `obj:Teleport(loc, rot)` -> `nil`
示例：`obj:Teleport({X=0,Y=0,Z=0},{Pitch=0,Yaw=90,Roll=0})`
- `obj:AttachTo(parent, socket)` -> `nil`
示例：`obj:AttachTo(player, "hand_r")`
- `obj:Detach()` -> `nil`
示例：`obj:Detach()`
- `obj:AddTag(tag)` -> `nil`
示例：`obj:AddTag("Quest")`
- `obj:RemoveTag(tag)` -> `nil`
示例：`obj:RemoveTag("Quest")`
- `obj:HasTag(tag)` -> `bool`
示例：`local ok = obj:HasTag("Quest")`
- `obj:AddTrigger(type, range, code, once)` -> `nil`
示例：`obj:AddTrigger("Enter", 300, "Log('enter')", true)`

### 3.6 `Performer` 接口（`npc:Method(...)`）

- `npc:MoveTo(loc)` -> `string`（异步，常见 `Success/Fail`）
示例：`local r = npc:MoveTo({X=100,Y=0,Z=0})`
- `npc:MoveToActor(target)` -> `string`（异步）
示例：`local r = npc:MoveToActor(player)`
- `npc:Follow(target, dist)` -> `nil`
示例：`npc:Follow(player, 180)`
- `npc:StopFollow()` -> `nil`
示例：`npc:StopFollow()`
- `npc:LookAt(target)` -> `nil`
示例：`npc:LookAt(player)`
- `npc:PlayAnim(animName)` -> `nil`（异步）— **仅** DT_MontageTable（Attack、Drink）
示例：`npc:PlayAnim("Drink")`
- `npc:PlayAnimLoop(animName, time)` -> `nil` — **仅** DT_AnimStartTable（Wave、Happy、Idle 等）
示例：`npc:PlayAnimLoop("Wave", 0)`
- `npc:ApproachAndSay(target, text)` -> `nil`（异步）
示例：`npc:ApproachAndSay(player, "你好")`
- `npc:SetAsHostile()` -> `string`（异步，缺组件时返回 `Victory`）
示例：`local r = npc:SetAsHostile()`
- `npc:SetAsAlly()` -> `nil`
示例：`npc:SetAsAlly()`
- `npc:GiveItem(id, count)` -> `nil`
示例：`npc:GiveItem("Money", 1)`
- `npc:GiveEquip(id, count)` -> `nil`
示例：`npc:GiveEquip("Helmet", 1)`
- `npc:GiveWeapon(id, count)` -> `nil`
示例：`npc:GiveWeapon("Sword", 1)`


### 3.7 `Math`（全量）

#### 随机
- `Math.RandInt(min,max) -> int`；示例：`local v=Math.RandInt(1,10)`
- `Math.RandFloat(min,max) -> number`；示例：`local v=Math.RandFloat(0,1)`
- `Math.Chance(p) -> bool`；示例：`if Math.Chance(0.3) then ... end`
- `Math.RandDir() -> FVector`；示例：`local d=Math.RandDir()`
- `Math.RandDir2D() -> FVector`；示例：`local d=Math.RandDir2D()`
- `Math.RandPointInSphere(center,radius) -> FVector`；示例：`local p=Math.RandPointInSphere({X=0,Y=0,Z=0},300)`
- `Math.RandPointOnSphere(center,radius) -> FVector`；示例：`local p=Math.RandPointOnSphere({X=0,Y=0,Z=0},300)`
- `Math.RandPointInRing(center,inner,outer) -> FVector`；示例：`local p=Math.RandPointInRing({X=0,Y=0,Z=0},100,300)`
- `Math.GaussianRand(mean,stddev) -> number`；示例：`local g=Math.GaussianRand(0,1)`

#### 基础工具
- `Math.Clamp(v,min,max) -> number`；示例：`local c=Math.Clamp(12,0,10)`
- `Math.Remap(v,inMin,inMax,outMin,outMax) -> number`；示例：`local x=Math.Remap(0.5,0,1,0,100)`
- `Math.RemapClamped(v,inMin,inMax,outMin,outMax) -> number`；示例：`local x=Math.RemapClamped(2,0,1,0,100)`
- `Math.Snap(v,grid) -> number`；示例：`local s=Math.Snap(1.34,0.5)`
- `Math.SnapVec(v,grid) -> FVector`；示例：`local s=Math.SnapVec({X=12,Y=9,Z=1},10)`
- `Math.Wrap(v,min,max) -> number`；示例：`local w=Math.Wrap(370,0,360)`
- `Math.Sign(v) -> int`；示例：`local s=Math.Sign(-2)`
- `Math.Abs(v) -> number`；示例：`local a=Math.Abs(-9)`
- `Math.Floor(v) -> int`；示例：`local i=Math.Floor(1.9)`
- `Math.Ceil(v) -> int`；示例：`local i=Math.Ceil(1.1)`
- `Math.Round(v) -> int`；示例：`local i=Math.Round(1.6)`
- `Math.Frac(v) -> number`；示例：`local f=Math.Frac(3.14)`
- `Math.Min(a,b) -> number`；示例：`local m=Math.Min(1,2)`
- `Math.Max(a,b) -> number`；示例：`local m=Math.Max(1,2)`
- `Math.MinInt(a,b) -> int`；示例：`local m=Math.MinInt(1,2)`
- `Math.MaxInt(a,b) -> int`；示例：`local m=Math.MaxInt(1,2)`

#### 向量与角度
- `Math.Dist(a,b) -> number`；示例：`local d=Math.Dist(p1,p2)`
- `Math.Dist2D(a,b) -> number`；示例：`local d=Math.Dist2D(p1,p2)`
- `Math.Dir(from,to) -> FVector`；示例：`local d=Math.Dir(p1,p2)`
- `Math.Dot(a,b) -> number`；示例：`local d=Math.Dot(v1,v2)`
- `Math.Cross(a,b) -> FVector`；示例：`local c=Math.Cross(v1,v2)`
- `Math.Normalize(v) -> FVector`；示例：`local n=Math.Normalize(v)`
- `Math.Length(v) -> number`；示例：`local l=Math.Length(v)`
- `Math.Length2D(v) -> number`；示例：`local l=Math.Length2D(v)`
- `Math.Reflect(v,n) -> FVector`；示例：`local r=Math.Reflect(v,n)`
- `Math.Project(v,target) -> FVector`；示例：`local p=Math.Project(v,t)`
- `Math.ProjectOnPlane(v,normal) -> FVector`；示例：`local p=Math.ProjectOnPlane(v,n)`
- `Math.DegToRad(deg) -> number`；示例：`local r=Math.DegToRad(90)`
- `Math.RadToDeg(rad) -> number`；示例：`local d=Math.RadToDeg(3.14)`
- `Math.NormalizeAngle(a) -> number`；示例：`local a=Math.NormalizeAngle(270)`
- `Math.ClampAngle(a,min,max) -> number`；示例：`local a=Math.ClampAngle(270,-90,90)`

#### Actor/旋转
- `Math.GetForward(obj) -> FVector`；示例：`local f=Math.GetForward(actor)`
- `Math.GetRight(obj) -> FVector`；示例：`local r=Math.GetRight(actor)`
- `Math.GetUp(obj) -> FVector`；示例：`local u=Math.GetUp(actor)`
- `Math.GetBounds(obj,bOnlyCol) -> FVector`；示例：`local e=Math.GetBounds(actor,true)`
- `Math.GetCenter(obj,bOnlyCol) -> FVector`；示例：`local c=Math.GetCenter(actor,true)`
- `Math.RotFromX(dir) -> FRotator`；示例：`local r=Math.RotFromX({X=1,Y=0,Z=0})`
- `Math.ForwardFromRot(rot) -> FVector`；示例：`local f=Math.ForwardFromRot({Pitch=0,Yaw=90,Roll=0})`
- `Math.ToRot(v) -> FRotator`；示例：`local r=Math.ToRot({X=0,Y=1,Z=0})`

#### 几何/插值
- `Math.IsPointInBox(pt,center,extent) -> bool`；示例：`local ok=Math.IsPointInBox(p,c,e)`
- `Math.RandPointInBox(center,extent) -> FVector`；示例：`local p=Math.RandPointInBox(c,e)`
- `Math.GetPointsInCircle(center,radius,count) -> FVector[]`；示例：`local arr=Math.GetPointsInCircle(c,300,8)`
- `Math.GetPointInCone(origin,dir,angle,dist) -> FVector`；示例：`local p=Math.GetPointInCone(o,d,30,500)`
- `Math.Lerp(a,b,t) -> number`；示例：`local v=Math.Lerp(0,10,0.3)`
- `Math.LerpVec(a,b,t) -> FVector`；示例：`local v=Math.LerpVec(v1,v2,0.3)`
- `Math.LerpRot(a,b,t) -> FRotator`；示例：`local r=Math.LerpRot(r1,r2,0.3)`
- `Math.EaseIn(t,exp) -> number`；示例：`local v=Math.EaseIn(0.5,2)`
- `Math.EaseOut(t,exp) -> number`；示例：`local v=Math.EaseOut(0.5,2)`
- `Math.EaseInOut(t,exp) -> number`；示例：`local v=Math.EaseInOut(0.5,2)`
- `Math.InterpTo(cur,target,dt,speed) -> number`；示例：`x=Math.InterpTo(x,10,dt,5)`
- `Math.InterpToVec(cur,target,dt,speed) -> FVector`；示例：`p=Math.InterpToVec(p,tp,dt,5)`

#### 样条/轨迹
- `Math.GetSplinePoint(points,t) -> FVector`；示例：`local p=Math.GetSplinePoint(ps,0.5)`
- `Math.GetSplineTangent(points,t) -> FVector`；示例：`local t=Math.GetSplineTangent(ps,0.5)`
- `Math.GetSplineLength(points) -> number`；示例：`local l=Math.GetSplineLength(ps)`
- `Math.GetSplinePoints(points,count) -> FVector[]`；示例：`local arr=Math.GetSplinePoints(ps,20)`
- `Math.GetSplinePointAtDist(points,dist) -> FVector`；示例：`local p=Math.GetSplinePointAtDist(ps,200)`
- `Math.GetArcPoint(start,end,height,t) -> FVector`；示例：`local p=Math.GetArcPoint(a,b,100,0.5)`
- `Math.GetArcPoints(start,end,height,count) -> FVector[]`；示例：`local arr=Math.GetArcPoints(a,b,100,16)`
- `Math.GetClosestPointOnSpline(points,pos) -> FVector`；示例：`local p=Math.GetClosestPointOnSpline(ps,pos)`
- `Math.GetClosestTOnSpline(points,pos) -> number`；示例：`local t=Math.GetClosestTOnSpline(ps,pos)`

#### 碰撞/噪声
- `Math.IsPointInSphere(pt,center,radius) -> bool`；示例：`local ok=Math.IsPointInSphere(p,c,100)`
- `Math.IsPointInCapsule(pt,start,end,radius) -> bool`；示例：`local ok=Math.IsPointInCapsule(p,a,b,50)`
- `Math.IsPointInCone(pt,origin,dir,length,angle) -> bool`；示例：`local ok=Math.IsPointInCone(p,o,d,500,30)`
- `Math.ClosestPointOnLine(pt,a,b) -> FVector`；示例：`local p=Math.ClosestPointOnLine(p0,a,b)`
- `Math.ClosestPointOnBox(pt,center,extent) -> FVector`；示例：`local p=Math.ClosestPointOnBox(p0,c,e)`
- `Math.LineIntersect2D(a1,a2,b1,b2) -> FVector`；示例：`local p=Math.LineIntersect2D(a1,a2,b1,b2)`
- `Math.BoxesOverlap(ca,ea,cb,eb) -> bool`；示例：`local ok=Math.BoxesOverlap(ca,ea,cb,eb)`
- `Math.PerlinNoise1D(x) -> number`；示例：`local n=Math.PerlinNoise1D(0.3)`
- `Math.PerlinNoise2D(x,y) -> number`；示例：`local n=Math.PerlinNoise2D(0.3,0.7)`
- `Math.PerlinNoise3D(x,y,z) -> number`；示例：`local n=Math.PerlinNoise3D(0.3,0.7,1.2)`

### 3.8 `Env`（全量）

#### Map/Terrain
- `Env.CreateMap(w,h,cellSize) -> MapHandle`；示例：`local map=Env.CreateMap(64,64,200)`
- `Env.SetMapName(map,name) -> nil`；示例：`Env.SetMapName(map,"Demo")`
- `Env.SetMapTheme(map,theme) -> nil`；示例：`Env.SetMapTheme(map,"Village")`
- `Env.SetTerrainHeight(map,x,y,h) -> nil`；示例：`Env.SetTerrainHeight(map,10,10,120)`
- `Env.SetTerrainHeightBatch(map,pts) -> nil`；示例：`Env.SetTerrainHeightBatch(map,{{X=1,Y=1,H=50}})`
- `Env.LowerTerrain(map,c,r,d,f) -> nil`；示例：`Env.LowerTerrain(map,{X=20,Y=20},5,30,1)`
- `Env.RaiseTerrain(map,c,r,h,f) -> nil`；示例：`Env.RaiseTerrain(map,{X=20,Y=20},5,30,1)`
- `Env.FlattenTerrain(map,c,r,h) -> nil`；示例：`Env.FlattenTerrain(map,{X=20,Y=20},8,100)`
- `Env.SmoothTerrain(map,iter) -> nil`；示例：`Env.SmoothTerrain(map,2)`
- `Env.PaintTerrain(map,x,y,r,mat) -> nil`；示例：`Env.PaintTerrain(map,10,10,4,"Grass")`
- `Env.GetTerrainHeight(map,x,y) -> number`；示例：`local h=Env.GetTerrainHeight(map,10,10)`
- `Env.GetMapSize(map) -> FIntPoint`；示例：`local s=Env.GetMapSize(map)`
- `Env.GridToWorld(map,x,y) -> FVector`；示例：`local p=Env.GridToWorld(map,10,10)`
- `Env.WorldToGrid(map,loc) -> FIntPoint`；示例：`local g=Env.WorldToGrid(map,{X=0,Y=0,Z=0})`

#### Block
- `Env.AddBlock(map,name,pos,size) -> BlockHandle`；示例：`local b=Env.AddBlock(map,"B1",{X=5,Y=5},{X=10,Y=10})`
- `Env.SetBlockType(block,type) -> nil`；示例：`Env.SetBlockType(b,"Town")`
- `Env.SetBlockProperty(block,key,val) -> nil`；示例：`Env.SetBlockProperty(b,"Owner","NPC_A")`
- `Env.GetBlockByName(map,name) -> BlockHandle`；示例：`local b=Env.GetBlockByName(map,"B1")`
- `Env.GetAllBlocks(map) -> BlockHandle[]`；示例：`local arr=Env.GetAllBlocks(map)`
- `Env.GetBlockBounds(block) -> FIntRect`；示例：`local r=Env.GetBlockBounds(b)`
- `Env.GetBlockCenter(block) -> FIntPoint`；示例：`local c=Env.GetBlockCenter(b)`
- `Env.GetBlockSize(block) -> FIntPoint`；示例：`local s=Env.GetBlockSize(b)`
- `Env.GetBlockPos(block) -> FIntPoint`；示例：`local p=Env.GetBlockPos(b)`
- `Env.GetBuildingsInBlock(block) -> BuildingHandle[]`；示例：`local bs=Env.GetBuildingsInBlock(b)`
- `Env.GetBlockWorldBounds(map,block) -> FBox`；示例：`local wb=Env.GetBlockWorldBounds(map,b)`
- `Env.IsPointInBlock(block,pos) -> bool`；示例：`local ok=Env.IsPointInBlock(b,{X=7,Y=7})`
- `Env.BlockGridToWorld(map,block,x,y) -> FVector`；示例：`local p=Env.BlockGridToWorld(map,b,2,2)`
- `Env.ResizeBlock(block,newSize) -> bool`；示例：`local ok=Env.ResizeBlock(b,{X=12,Y=12})`
- `Env.SetBlockRotation(block,yawDeg) -> bool`；示例：`local ok=Env.SetBlockRotation(b,90)`
- `Env.MoveBlockTo(block,newPos) -> bool`；示例：`local ok=Env.MoveBlockTo(b,{X=20,Y=20})`
- `Env.ClearBlockContent(block,mode) -> bool`；示例：`local ok=Env.ClearBlockContent(b,0)`
- `Env.DestroyBlock(block) -> bool`；示例：`local ok=Env.DestroyBlock(b)`

#### Building/Prop/Spawn
- `Env.AddBuilding(block,pos,size,style,rot) -> BuildingHandle`；示例：`local bd=Env.AddBuilding(b,{X=1,Y=1},{X=3,Y=3},"Wood",{Pitch=0,Yaw=0,Roll=0})`
- `Env.GetBuildingSize(building) -> FIntPoint`；示例：`local s=Env.GetBuildingSize(bd)`
- `Env.GetBuildingRotation(building) -> number`；示例：`local y=Env.GetBuildingRotation(bd)`
- `Env.GetBuildingPos(building) -> FIntPoint`；示例：`local p=Env.GetBuildingPos(bd)`
- `Env.GetBuildingCenter(building) -> FIntPoint`；示例：`local c=Env.GetBuildingCenter(bd)`
- `Env.GetBuildingBounds(building) -> FIntRect/FEnvIntRect`；示例：`local r=Env.GetBuildingBounds(bd)`
- `Env.GetBuildingWorldBounds(building) -> FBox`；示例：`local wb=Env.GetBuildingWorldBounds(bd)`
- `Env.SetBuildingType(building,type) -> nil`；示例：`Env.SetBuildingType(bd,"Shop")`
- `Env.AddBuildingFloor(building,h) -> int`；示例：`local idx=Env.AddBuildingFloor(bd,300)`
- `Env.SetBuildingRoof(building,type) -> nil`；示例：`Env.SetBuildingRoof(bd,"Gable")`
- `Env.AddProp(block,id,localPos,rot) -> nil`；示例：`Env.AddProp(b,"Prop_Tent",{X=100,Y=0,Z=0},{Pitch=0,Yaw=0,Roll=0})`
- `Env.AddNPCSpawn(block,id,localPos,rot) -> nil`；示例：`Env.AddNPCSpawn(b,"Default",{X=0,Y=0,Z=0},{Pitch=0,Yaw=0,Roll=0})`
- `Env.AddEnemySpawn(block,id,localPos,radius) -> nil`；示例：`Env.AddEnemySpawn(b,"Spider_Minion_1",{X=0,Y=0,Z=0},300)`
- `Env.AddInteractable(block,type,pos,script) -> nil`；示例：`Env.AddInteractable(b,"Chest",{X=0,Y=0,Z=0},"Log('open')")`
- `Env.AddTriggerZone(block,pos,size,type,script) -> nil`；示例：`Env.AddTriggerZone(b,{X=0,Y=0,Z=0},{X=200,Y=200,Z=100},"Enter","Log('in')")`
- `Env.AddSpawnPoint(block,tag,pos) -> nil`；示例：`Env.AddSpawnPoint(b,"PlayerStart",{X=0,Y=0,Z=0})`
- `Env.FindEmptySpace(block,size2D) -> FVector`；示例：`local p=Env.FindEmptySpace(b,{X=200,Y=200})`
- `Env.IsSpaceEmpty(block,pos,size2D) -> bool`；示例：`local ok=Env.IsSpaceEmpty(b,{X=0,Y=0,Z=0},{X=200,Y=200})`
- `Env.ResizeBuilding(building,newSize) -> bool`；示例：`local ok=Env.ResizeBuilding(bd,{X=4,Y=4})`
- `Env.SetBuildingRotation(building,yawDeg) -> bool`；示例：`local ok=Env.SetBuildingRotation(bd,45)`
- `Env.MoveBuildingTo(building,newPos) -> bool`；示例：`local ok=Env.MoveBuildingTo(bd,{X=3,Y=3})`
- `Env.DestroyBuilding(building) -> bool`；示例：`local ok=Env.DestroyBuilding(bd)`
- `Env.MovePropTo(prop,newPos) -> bool`；示例：`local ok=Env.MovePropTo(prop,{X=2,Y=2})`
- `Env.DestroyProp(prop) -> bool`；示例：`local ok=Env.DestroyProp(prop)`

#### Connection/Auto/Generation/SaveBuild
- `Env.AddRoad(map,a,b,width,roadType) -> ConnectionHandle`；示例：`local c=Env.AddRoad(map,b1,b2,4,"Dirt")`
- `Env.AddBridge(map,a,b,width) -> ConnectionHandle`；示例：`local c=Env.AddBridge(map,b1,b2,3)`
- `Env.AddTeleport(map,a,posA,b,posB) -> ConnectionHandle`；示例：`local c=Env.AddTeleport(map,b1,{X=0,Y=0,Z=0},b2,{X=0,Y=0,Z=0})`
- `Env.AddStairs(map,a,b,width) -> ConnectionHandle`；示例：`local c=Env.AddStairs(map,b1,b2,2)`
- `Env.SetConnectionProperty(conn,key,val) -> nil`；示例：`Env.SetConnectionProperty(c,"Cost","5")`
- `Env.GetConnections(map,block) -> ConnectionHandle[]`；示例：`local arr=Env.GetConnections(map,b1)`
- `Env.AreBlocksConnected(map,a,b) -> bool`；示例：`local ok=Env.AreBlocksConnected(map,b1,b2)`
- `Env.AutoGenerateRoads(map) -> nil`；示例：`Env.AutoGenerateRoads(map)`
- `Env.GenMapFromTemplate(template,seed) -> MapHandle`；示例：`local m=Env.GenMapFromTemplate("VillageA",123)`
- `Env.GenDungeonBlock(map,pos,size,seed) -> BlockHandle`；示例：`local b=Env.GenDungeonBlock(map,{X=0,Y=0},{X=20,Y=20},1)`
- `Env.GenVillageBlock(map,pos,size,bldgs,seed) -> BlockHandle`；示例：`local b=Env.GenVillageBlock(map,{X=0,Y=0},{X=20,Y=20},8,1)`
- `Env.GenForestBlock(map,pos,size,density,seed) -> BlockHandle`；示例：`local b=Env.GenForestBlock(map,{X=0,Y=0},{X=20,Y=20},0.7,1)`
- `Env.GenMountainRange(map,start,end,height,width) -> nil`；示例：`Env.GenMountainRange(map,{X=0,Y=0},{X=20,Y=20},200,3)`
- `Env.SaveMap(map,slot) -> bool`；示例：`local ok=Env.SaveMap(map,"slot_1")`
- `Env.LoadMap(slot) -> MapHandle`；示例：`local map=Env.LoadMap("slot_1")`
- `Env.ValidateMap(map) -> string[]`；示例：`local errs=Env.ValidateMap(map)`
- `Env.Build(map) -> Actor(LevelRoot)`；示例：`local root=Env.Build(map)`
- `Env.BuildAsync(map) -> Actor|nil`（异步）
示例：`local root=Env.BuildAsync(map)`

## 4. `Doc/datatable` 表格分析（按代码使用）

### 4.1 每张表的代码使用关系

| 表名 | 主要行键示例 | 代码读取位置 | 关联 API | 返回结果 |
|---|---|---|---|---|
| `DT_SpawnNPCTable.csv` | `Default`, `BaseNPC` | `NarrativeWorldLibrary.cpp` `FindRow<FNarrativeSpawnRow>` | `World.SpawnNPC`, `World.SpawnEncounter` | `ActorClass` -> 生成 `AActor*` |
| `DT_EnemyDataTable.csv` | `Spider_Minion_1` 等 | `NarrativeWorldLibrary.cpp` `FindRow<FEnemyData>` | `World.SpawnEnemy`, `World.SpawnEnemyAtPlayer` | `EnemyClass` -> `AEnemyBase*[]` |
| `DT_Items.csv` | `TestSword`, `Money`, `Helmet` 等 | `NarrativePerformerInterface.cpp`（通过 `itemRowName` + `ItemReInit`） | `npc:GiveItem/GiveEquip/GiveWeapon` | 生成道具 Actor，函数本身 `nil` |
| `DT_EquipmentDataTable.csv` | `Helmet`, `WindRing`, `HeavyShackle` | 由物品系统/装备系统间接读取 | 间接（由 `DT_Items` 的装备项驱动） | 装备词条与显示数据 |
| `DT_WeaponDataTable.csv` | `TestSword`, `Spear`, `FireSword` | 战斗组件/武器链路读取 | 间接（武器装备后） | 攻击链、范围、技能等 |
| `DT_AffixDataTable.csv` | `ATK_ADD_10`, `MSPD_ADD_200` 等 | CombatComponent `AddAffixByID` 读取 | 间接（装备/技能触发） | 词条类与描述 |
| `DT_Equipment.csv` | `TestSword`, `Helmet` 等 | 装备展示系统读取 | 间接（装备外观） | 网格、插槽、处理器 |
| `PropVilligeData.csv` | `Prop_Tent`, `Prop_Fountain` 等 | 环境/摆件系统（非 Narrative Lua 直接） | 间接（`Env.AddProp` 使用 ID） | Prop 资源与尺寸 |

### 4.2 遇脚本中的“代码调用 -> 表 -> 返回”

| 脚本代码 | 实际表查询 | 返回 |
|---|---|---|
| `World.SpawnEncounter(loc, r, npcData, "EnterVolume", code)` | `npcData` 的 value（`Default`）查 `DT_SpawnNPCTable` | 当前函数返回 `nil`（内部会异步生成 NPC + 触发器） |
| `World.GetByID("enc01_smith")` | 不查表，按 Actor Tag 查找 | `Actor|nil` |
| `smith:ApproachAndSay(player, text)` | 不查 `Doc/datatable`，是行为接口 | 异步完成，恢复值通常 `nil` |
| `UI.Toast("你获得了TestSword")` | 不查表（仅显示文本） | 异步，恢复 `nil` |

关键点：你当前 `Doc/lua_encounters/*.lua` 里“获得物品”只是 `UI.Toast` 文本，不会发放物品。要真正发放，需要调用：
- `smith:GiveWeapon("TestSword",1)`
- `smith:GiveEquip("Helmet",1)`
- `smith:GiveItem("Money",1)`
这些 ID 会走 `DT_Items.csv` 的 row key。

### 4.3 你这批 6 个遇脚本里的表键覆盖

- NPC类型键（用于 `DT_SpawnNPCTable`）：`Default`
- 文本提及的物品键（在 `DT_Items.csv` 中存在）：
`TestSword`, `TestSpear`, `Spear`, `Sword`, `FireSword`, `Helmet`, `WindRing`, `HeavyShackle`, `BloodChain`, `Money`

## 5. 组合调用参考（真发奖励）

```lua
local player = World.GetByID("Player")
local smith = World.GetByID("enc01_smith")

if smith and player then
    smith:ApproachAndSay(player, "完成试炼，给你装备。")
    smith:GiveEquip("Helmet", 1)
    smith:GiveWeapon("TestSword", 1)
    smith:GiveItem("Money", 1)
    UI.Toast("已发放：Helmet / TestSword / Money")
end
```
