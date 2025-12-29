#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 gpt-5.1 和 gpt-5.1-codex 模型是否可用
"""

import json
import os
import sys
from openai import OpenAI

# 设置Windows控制台编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def create_client(api_key):
    """创建OpenAI客户端"""
    env_backup = {}
    problematic_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in problematic_vars:
        if var in os.environ:
            env_backup[var] = os.environ.pop(var)
    
    try:
        client = OpenAI(api_key=api_key)
        return client, env_backup
    except Exception as e:
        for var, value in env_backup.items():
            os.environ[var] = value
        raise e

def restore_env(env_backup):
    """恢复环境变量"""
    for var, value in env_backup.items():
        os.environ[var] = value

def test_model(model_name, client):
    """测试单个模型"""
    try:
        print(f"测试模型 '{model_name}'...", end=" ")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("✅ 可用")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 不可用")
        print(f"   错误: {error_msg[:100]}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("测试 gpt-5.1 系列模型")
    print("=" * 60)
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_config = config.get("api_config", {})
        api_key = api_config.get("api_key", "")
        
        if not api_key:
            print("❌ API密钥未配置")
            exit(1)
        
        client, env_backup = create_client(api_key)
        
        try:
            # 测试用户要求的模型
            models_to_test = [
                "gpt-5.1",
                "gpt-5.1-codex",
                "gpt-5.2",
                "gpt-5.2-pro",
                "gpt-5.2-chat-latest",
                "gpt-5-mini"
            ]
            
            print("\n测试模型可用性:\n")
            available_models = []
            unavailable_models = []
            
            for model in models_to_test:
                if test_model(model, client):
                    available_models.append(model)
                else:
                    unavailable_models.append(model)
                print()
            
            print("=" * 60)
            print("测试结果总结")
            print("=" * 60)
            print(f"\n✅ 可用模型 ({len(available_models)}):")
            for model in available_models:
                print(f"  - {model}")
            
            if unavailable_models:
                print(f"\n❌ 不可用模型 ({len(unavailable_models)}):")
                for model in unavailable_models:
                    print(f"  - {model}")
            
        finally:
            restore_env(env_backup)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

