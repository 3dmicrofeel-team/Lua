# 快速启动指南

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 启动服务器

### Windows:
```bash
start.bat
```

### Linux/Mac:
```bash
chmod +x start.sh
./start.sh
```

### 或直接运行:
```bash
python app.py
```

## 3. 打开浏览器

访问: http://localhost:5000

## 4. 配置API密钥

1. 点击"API配置"标签
2. 输入你的OpenAI API密钥
3. 选择模型（推荐GPT-4）
4. 点击"保存配置"

## 5. 生成Lua代码

1. 点击"生成Lua"标签
2. 输入你的游戏想法，例如：
   - "玩家需要在一个废弃的工厂中找到钥匙，打开大门逃离，但要小心巡逻的机器人守卫"
   - "玩家扮演一个盗贼，需要潜入城堡偷取宝物，避开守卫和陷阱"
3. 点击"生成Lua代码"
4. 等待生成完成（可能需要几分钟）
5. 查看生成的三个Lua文件：
   - set.lua - 场景和触发器代码
   - cast.lua - 角色和道具代码
   - main.lua - 主程序入口

## 6. 自定义Prompt（可选）

1. 点击"Prompt配置"标签
2. 修改各个模块的Prompt模板
3. 调整Temperature和Max Tokens参数
4. 点击"保存此模块配置"

## 注意事项

- 首次使用必须配置API密钥
- 生成过程会依次调用6个模块，请耐心等待
- 建议使用GPT-4模型以获得更好的效果
- 如果某个模块生成失败，检查API密钥和网络连接

