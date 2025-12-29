#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试API连接和配置
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

def test_config():
    """测试配置加载"""
    print("=" * 50)
    print("1. 测试配置加载")
    print("=" * 50)
    
    if not os.path.exists('config.json'):
        print("❌ config.json 不存在")
        return False
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ 配置文件加载成功")
        
        # 检查API配置
        api_config = config.get("api_config", {})
        api_key = api_config.get("api_key", "")
        model = api_config.get("model", "")
        
        if not api_key:
            print("❌ API密钥未配置")
            return False
        else:
            print(f"✅ API密钥已配置: {api_key[:20]}...")
        
        print(f"✅ 默认模型: {model}")
        
        # 检查模块配置
        modules = config.get("modules", {})
        print(f"✅ 找到 {len(modules)} 个模块")
        
        for name, module_config in modules.items():
            module_model = module_config.get("model", "")
            print(f"  - {name}: {module_model}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def create_client(api_key):
    """创建OpenAI客户端（处理环境变量问题）"""
    # 清除可能影响初始化的环境变量
    env_backup = {}
    problematic_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in problematic_vars:
        if var in os.environ:
            env_backup[var] = os.environ.pop(var)
    
    try:
        client = OpenAI(api_key=api_key)
        return client, env_backup
    except Exception as e:
        # 恢复环境变量
        for var, value in env_backup.items():
            os.environ[var] = value
        raise e

def restore_env(env_backup):
    """恢复环境变量"""
    for var, value in env_backup.items():
        os.environ[var] = value

def test_api_connection():
    """测试API连接"""
    print("\n" + "=" * 50)
    print("2. 测试API连接")
    print("=" * 50)
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_config = config.get("api_config", {})
        api_key = api_config.get("api_key", "")
        
        if not api_key:
            print("❌ API密钥未配置")
            return False
        
        client, env_backup = create_client(api_key)
        
        try:
            # 测试一个简单的API调用
            print("正在测试API调用...")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": "Hello"}
                ],
                max_tokens=10
            )
            
            print("✅ API连接成功")
            print(f"✅ 响应: {response.choices[0].message.content}")
            return True
        finally:
            restore_env(env_backup)
        
    except Exception as e:
        print(f"❌ API连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        return False

def test_model_availability():
    """测试模型可用性"""
    print("\n" + "=" * 50)
    print("3. 测试模型可用性")
    print("=" * 50)
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_config = config.get("api_config", {})
        api_key = api_config.get("api_key", "")
        
        if not api_key:
            print("❌ API密钥未配置")
            return False
        
        client, env_backup = create_client(api_key)
        
        try:
            # 测试常用模型
            test_models = ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
            
            for model in test_models:
                try:
                    print(f"测试模型 {model}...", end=" ")
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                    print("✅ 可用")
                except Exception as e:
                    print(f"❌ 不可用: {str(e)[:50]}")
            
            return True
        finally:
            restore_env(env_backup)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == '__main__':
    print("\n开始诊断...\n")
    
    config_ok = test_config()
    if not config_ok:
        print("\n❌ 配置检查失败，请先修复配置问题")
        exit(1)
    
    api_ok = test_api_connection()
    if not api_ok:
        print("\n❌ API连接失败，请检查API密钥和网络连接")
        exit(1)
    
    test_model_availability()
    
    print("\n" + "=" * 50)
    print("诊断完成")
    print("=" * 50)
