#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试自定义模型名称
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
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print("✅ 可用")
        return True
    except Exception as e:
        error_msg = str(e)
        if "model" in error_msg.lower() or "invalid" in error_msg.lower() or "not found" in error_msg.lower():
            print(f"❌ 不可用: {error_msg[:60]}")
        else:
            print(f"❌ 错误: {error_msg[:60]}")
        return False

def test_model_mapping():
    """测试模型映射逻辑"""
    print("=" * 60)
    print("测试自定义模型名称和映射")
    print("=" * 60)
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_config = config.get("api_config", {})
        api_key = api_config.get("api_key", "")
        
        if not api_key:
            print("❌ API密钥未配置")
            return
        
        client, env_backup = create_client(api_key)
        
        try:
            # 获取配置中的所有模型
            modules = config.get("modules", {})
            custom_models = set()
            
            for name, module_config in modules.items():
                model = module_config.get("model", "")
                if model:
                    custom_models.add(model)
            
            print(f"\n找到 {len(custom_models)} 个自定义模型名称:\n")
            
            # 测试每个自定义模型
            for model in sorted(custom_models):
                print(f"  {model}:")
                available = test_model(model, client)
                
                # 显示映射逻辑
                if not available:
                    if "codex" in model.lower():
                        mapped_model = "gpt-4-turbo"
                    elif model == "gpt-5.1":
                        mapped_model = "gpt-4o"
                    else:
                        mapped_model = None
                    
                    if mapped_model:
                        print(f"    → 系统会自动映射到: {mapped_model}")
                        print(f"    测试映射模型...", end=" ")
                        if test_model(mapped_model, client):
                            print("✅ 映射模型可用")
                        else:
                            print("❌ 映射模型也不可用")
                    print()
            
            print("\n" + "=" * 60)
            print("总结")
            print("=" * 60)
            print("\n配置的模型名称:")
            for model in sorted(custom_models):
                if "codex" in model.lower():
                    print(f"  {model} → 自动映射到 gpt-4-turbo")
                elif model == "gpt-5.1":
                    print(f"  {model} → 自动映射到 gpt-4o")
                else:
                    print(f"  {model} → 直接使用")
            
        finally:
            restore_env(env_backup)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_model_mapping()

