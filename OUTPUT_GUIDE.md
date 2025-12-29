# Lua 代码输出说明

## 📋 生成的文件结构

系统会生成 **3 个 Lua 文件**，按照以下顺序：

### 1. `stage_lua` (场务Lua代码 / set.lua)
- **作用**：场景设置和触发器代码
- **内容**：生成场景对象、逻辑对象、效果和触发器
- **文件名建议**：`Stage.lua` 或 `set.lua`

### 2. `cast_lua` (角色Lua代码 / cast.lua)
- **作用**：角色和道具管理代码
- **内容**：生成角色、物品、关键对象的生成和控制函数
- **文件名建议**：`Cast.lua` 或 `cast.lua`

### 3. `main_lua` (主程序Lua代码 / main.lua) ⭐
- **作用**：**主程序入口文件**
- **内容**：整合所有模块，实现游戏流程控制
- **文件名**：`main.lua`

## 🎯 应该执行哪个文件？

### ✅ **执行 `main.lua`**

`main.lua` 是**唯一需要执行的主入口文件**，它会：
- 自动加载 `Stage.lua` 和 `Cast.lua` 模块
- 初始化游戏场景和角色
- 控制游戏流程和节拍
- 处理胜利/失败条件

## 📁 文件保存建议

将生成的代码保存为以下文件：

```
your_game/
├── main.lua          ← 执行这个文件
├── Stage.lua         ← 场景模块（main.lua 会自动加载）
└── Cast.lua          ← 角色模块（main.lua 会自动加载）
```

## 🔧 使用方法

### 方法1：在游戏引擎中执行
1. 将 `main.lua` 设置为入口脚本
2. 确保 `Stage.lua` 和 `Cast.lua` 在同一目录或可访问路径
3. 运行游戏

### 方法2：直接运行（如果支持）
```lua
-- 在 Lua 环境中
dofile("main.lua")
```

## 📝 代码结构说明

### main.lua 的结构
```lua
local Stage = require("Stage")  -- 加载场景模块
local Cast = require("Cast")    -- 加载角色模块

-- Director state (游戏状态管理)
-- Beat handlers (节拍处理函数)
-- Win/fail checks (胜利/失败检查)
-- Main flow (主流程)

main()  -- 执行主函数
```

### Stage.lua 的结构
```lua
-- 场景对象生成
-- 触发器注册
-- 环境设置
```

### Cast.lua 的结构
```lua
Cast = {}
Cast.SpawnAll(spawn_context)  -- 生成所有角色和道具
Cast.Get(uid)                 -- 获取对象
Cast.Say(uid, text)           -- 控制函数
-- ... 其他控制函数
```

## ⚠️ 注意事项

1. **模块名称**：确保 `main.lua` 中的 `require()` 语句与你的文件名匹配
   - 如果文件是 `Stage.lua`，使用 `require("Stage")`
   - 如果文件是 `set.lua`，可能需要修改为 `require("set")`

2. **文件路径**：确保所有文件在同一目录，或正确配置 Lua 的模块搜索路径

3. **依赖关系**：
   - `main.lua` 依赖 `Stage.lua` 和 `Cast.lua`
   - 确保这两个文件先于 `main.lua` 加载或可访问

## 🎮 执行流程

```
启动游戏
  ↓
加载 main.lua
  ↓
main.lua 自动加载 Stage.lua 和 Cast.lua
  ↓
初始化场景和角色
  ↓
开始游戏流程
  ↓
执行各个节拍 (beats)
  ↓
检查胜利/失败条件
  ↓
游戏结束
```

## 💡 提示

- **只执行 `main.lua`**，其他文件会被自动加载
- 如果遇到模块加载错误，检查文件名和路径
- 所有代码都是纯 Lua，可以直接在支持 Lua 5.1+ 的环境中运行

