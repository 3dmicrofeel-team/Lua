# Lua AI 生成系统

这是一个基于多模块协作的Lua游戏脚本生成系统，可以根据用户的一句话想法，自动生成完整的Lua游戏脚本。

## 系统架构

系统包含6个模块，按照流水线方式工作：

1. **编剧模块 (Screenwriter)** - 将用户想法转换为剧情蓝图JSON
2. **场务设计模块 (Stage Design)** - 设计场景结构和触发器布局JSON
3. **场务程序模块 (Stage Programmer)** - 生成场景Lua代码 (set.lua)
4. **选角设计模块 (Casting Design)** - 设计角色/怪物/道具JSON
5. **角色配置程序模块 (Character Config)** - 生成角色Lua代码 (cast.lua)
6. **执行导演模块 (Executive Director)** - 生成主程序Lua代码 (main.lua)

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

1. 点击"生成Lua"标签页
2. 在输入框中输入你的游戏想法（一句话）
3. 点击"生成Lua代码"按钮
4. 等待系统依次调用6个模块生成结果
5. 查看生成的各个模块的输出

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

系统会生成三个Lua文件：
- `set.lua` - 场景和触发器代码
- `cast.lua` - 角色和道具代码
- `main.lua` - 主程序入口

## 注意事项

1. 首次使用前必须配置API密钥
2. 生成过程可能需要几分钟，请耐心等待
3. 建议使用GPT-4模型以获得更好的效果
4. 可以根据需要调整各模块的Prompt模板

## 技术栈

- 后端：Flask + OpenAI API
- 前端：HTML + CSS + JavaScript
- 配置：JSON文件存储

