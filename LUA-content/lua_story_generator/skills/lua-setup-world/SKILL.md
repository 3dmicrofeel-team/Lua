---
name: lua-setup-world
description: Generates LUA Setup_World scripts for map/terrain/block/building. Use when generating setup, 地图, 世界初始化, Env.CreateMap, Env.AddBlock. Enforces rule.md Setup规范.
---

# LUA Setup World Skill

## 何时加载

当步骤类型为 `setup` 或名称包含 `Setup_World`、`地图`、`世界` 时应用本 Skill。

## 标准流程

1. Env.CreateMap(w, h, cellSize)
2. Env.SetMapName / SetMapTheme
3. 地形：SetTerrainHeight, FlattenTerrain, RaiseTerrain
4. Block：AddBlock, AddBuilding, AddProp
5. Spawn：AddSpawnPoint, AddNPCSpawn, AddEnemySpawn
6. Env.ValidateMap -> Env.BuildAsync
7. 输出 _G.WorldAnchors 供 Encounter 选点

## 必须 API（仅用这些）

- Env.CreateMap, SetMapName, SetMapTheme
- Env.SetTerrainHeight, FlattenTerrain, RaiseTerrain, LowerTerrain
- Env.AddBlock, SetBlockType, AddBuilding, AddProp
- Env.AddSpawnPoint, AddNPCSpawn, AddEnemySpawn
- Env.ValidateMap, Env.BuildAsync

## 参考

- 完整 Env API 见 [reference.md](reference.md)
