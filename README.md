# Lua AI 生成系统

这是一个基于多模块协作的Lua游戏脚本生成系统，支持两种生成模式：
1. **游戏脚本生成** - 根据用户的一句话想法，自动生成完整的Lua游戏脚本
2. **关卡生成** - 根据自然语言描述，生成基于ASCII网格的关卡Lua代码

## 系统架构

系统包含两个独立的生成流程：

### 流程1：游戏脚本生成（6个模块）

1. **编剧模块 (Screenwriter)** - 将用户想法转换为剧情蓝图JSON
2. **场务设计模块 (Stage Design)** - 设计场景结构和触发器布局JSON
3. **场务程序模块 (Stage Programmer)** - 生成场景Lua代码 (Stage.lua)
4. **选角设计模块 (Casting Design)** - 设计角色/怪物/道具JSON
5. **角色配置程序模块 (Character Config)** - 生成角色Lua代码 (Cast.lua)
6. **执行导演模块 (Executive Director)** - 生成主程序Lua代码 (main.lua)

### 流程2：关卡生成（5个模块）

1. **Intent Parser模块**（可选）- 将自然语言解析为结构化关卡约束JSON
2. **Grid Planner模块** - 生成ASCII网格布局和实体坐标JSON
3. **LayoutGuard模块** - 验证和自动修复ASCII布局JSON
4. **Lua Builder模块** - 将ASCII布局转换为Lua代码（逐行转换）
5. **Lua Validator模块** - 验证Lua代码与ASCII地图的一致性并修复

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务器

```bash
python app.py
```

服务器将在 `http://localhost:5000` 启动

### 3. 打开浏览器

访问 `http://localhost:5000/static/index.html`

## 使用步骤

### 第一步：配置API

1. 点击"API配置"标签页
2. 输入你的OpenAI API密钥
3. 选择模型（推荐GPT-4）
4. 点击"保存配置"

### 第二步：生成Lua代码

系统提供两种生成模式：

#### 模式1：游戏脚本生成

1. 点击"生成Lua"标签页
2. 在输入框中输入你的游戏想法（一句话），例如：
   - "玩家需要在一个废弃的工厂中找到钥匙，打开大门逃离，但要小心巡逻的机器人守卫"
   - "玩家扮演一个盗贼，需要潜入城堡偷取宝物，避开守卫和陷阱"
3. 点击"生成Lua代码"按钮
4. 等待系统依次调用6个模块生成结果
5. 查看生成的各个模块的输出

#### 模式2：关卡生成

1. 点击"关卡生成"标签页
2. 在输入框中输入关卡描述（自然语言），例如：
   - "创建一个20x12的废弃墓地关卡，有2个敌人，1个NPC，1个宝箱，1个门，难度中等"
   - "生成一个简单的10x10地牢，有3个敌人和2个宝箱"
3. 选择是否使用Intent Parser（推荐开启，可解析自然语言为结构化约束）
4. 点击"生成关卡Lua代码"按钮
5. 等待系统依次调用模块生成结果：
   - Intent Parser（可选）- 解析关卡需求
   - Grid Planner - 生成ASCII地图
   - LayoutGuard - 验证和修复地图
   - Lua Builder - 转换为Lua代码
   - Lua Validator - 验证Lua代码与地图一致性
6. 查看生成的ASCII地图和Lua代码

### 第三步：自定义Prompt（可选）

1. 点击"Prompt配置"标签页
2. 修改各个模块的Prompt模板、Temperature、Max Tokens等参数
3. 点击"保存此模块配置"

## 配置文件

系统使用 `config.json` 存储配置，包括：
- API配置（密钥、模型、Base URL）
- 各模块的Prompt模板
- 各模块的参数（Temperature、Max Tokens、JSON Mode）

## 输出文件

### 游戏脚本生成模式

系统会生成三个Lua文件：
- `Stage.lua` - 场景和触发器代码
- `Cast.lua` - 角色和道具代码
- `main.lua` - 主程序入口（执行这个文件）

### 关卡生成模式

系统会生成一个Lua文件：
- `Level.lua` - 关卡Lua代码（包含所有墙、实体、NPC的生成命令）

所有文件都会自动保存到 `output/` 目录，可以直接下载使用。

## 关卡生成功能特点

### ASCII网格系统

关卡生成使用ASCII网格表示地图：
- `#` - 墙（Wall_Stone）
- `.` - 空/可行走空间
- `S` - 玩家起始位置
- `D` - 门（Wall_Stone）
- `C` - 宝箱（Grave_Stone）
- `E` - 敌人（Skeleton_Warrior）
- `N` - NPC（Ghost_Nun）

### 逐行转换方法

- Lua Builder采用逐行转换方法，确保每个ASCII字符都被正确处理
- 从Y=0开始，逐行从左到右处理每个字符
- 确保100%准确性和完整性，包含所有墙的生成命令

### 自动验证

- LayoutGuard验证ASCII地图的有效性（尺寸、字符、可达性等）
- Lua Validator验证Lua代码与ASCII地图的一致性
- 如果发现不一致，自动修复Lua代码

### 随机数量生成

如果用户未指定实体数量，Intent Parser会生成随机值：
- enemy: 0-4之间的随机整数
- npc: 0-3之间的随机整数
- chest: 0-3之间的随机整数
- door: 0-3之间的随机整数

每次生成都会使用不同的随机值，增加关卡多样性。

## 注意事项

1. 首次使用前必须配置API密钥
2. 生成过程可能需要几分钟，请耐心等待
3. 建议使用GPT-4或GPT-5.1模型以获得更好的效果
4. 可以根据需要调整各模块的Prompt模板
5. 关卡生成功能会生成包含所有墙的完整Lua代码
6. 如果使用Intent Parser，未指定数量时会自动生成随机值

## 模块详细说明

### 游戏脚本生成模块

| 模块 | 输入 | 输出 | 说明 |
|------|------|------|------|
| Screenwriter | 用户一句话想法 | JSON蓝图 | 纯设计层，不涉及代码 |
| Stage Design | 剧情蓝图 | JSON场景设计 | 设计场景、交互对象、触发器 |
| Stage Programmer | 场景设计 | Lua代码 | 生成Stage.lua，包含场景对象和触发器 |
| Casting Design | 剧情蓝图+场景设计 | JSON选角设计 | 设计角色、物品、关键对象 |
| Character Config | 选角设计 | Lua代码 | 生成Cast.lua，包含角色管理API |
| Executive Director | 蓝图+Stage.lua+Cast.lua | Lua代码 | 生成main.lua，编排游戏流程 |

### 关卡生成模块

| 模块 | 输入 | 输出 | 说明 |
|------|------|------|------|
| Intent Parser | 自然语言描述 | JSON约束 | 解析关卡需求，未指定数量时生成随机值 |
| Grid Planner | 关卡约束 | JSON ASCII地图 | 生成ASCII网格和实体坐标 |
| LayoutGuard | ASCII地图 | JSON验证结果 | 验证并修复地图（尺寸、可达性等） |
| Lua Builder | 验证后的地图 | Lua代码 | 逐行转换ASCII为Lua代码 |
| Lua Validator | 地图+Lua代码 | Lua代码 | 验证一致性，不一致时修复 |

## 技术栈

- 后端：Flask + OpenAI API
- 前端：HTML + CSS + JavaScript
- 配置：JSON文件存储
- 支持模型：GPT-4, GPT-4 Turbo, GPT-4.1, GPT-5.1等

