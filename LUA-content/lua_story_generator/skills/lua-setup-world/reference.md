# Env API 参考（Setup 用）

## 地图
- Env.CreateMap(w, h, cellSize) -> MapHandle
- Env.SetMapName(map, name)
- Env.SetMapTheme(map, theme)
- Env.ValidateMap(map) -> string[]
- Env.BuildAsync(map) -> Actor

## 地形
- Env.SetTerrainHeight(map, x, y, h)
- Env.FlattenTerrain(map, center, radius, height)
- Env.RaiseTerrain(map, center, radius, height, falloff)
- Env.LowerTerrain(map, center, radius, depth, falloff)
- Env.GridToWorld(map, x, y) -> FVector

## Block/Building
- Env.AddBlock(map, name, pos, size) -> BlockHandle
- Env.SetBlockType(block, type)
- Env.AddBuilding(block, pos, size, style, rot)
- Env.AddProp(block, id, pos, rot)
- Env.AddSpawnPoint(block, tag, pos)
- Env.AddNPCSpawn(block, id, pos, rot)
- Env.AddEnemySpawn(block, id, pos, radius)
- Env.FindEmptySpace(block, size2D) -> FVector
- Env.IsSpaceEmpty(block, pos, size2D) -> bool
