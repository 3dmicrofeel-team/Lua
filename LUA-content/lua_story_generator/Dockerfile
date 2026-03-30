# LUA Story Generator - 阿里云容器部署
FROM python:3.11-slim

WORKDIR /app

# 复制项目根目录的 rule.md、lua_atomic_modules_call_guide.md
COPY rule.md lua_atomic_modules_call_guide.md ./

# 复制 lua_story_generator 应用
COPY lua_story_generator/ ./lua_story_generator/

WORKDIR /app/lua_story_generator

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
