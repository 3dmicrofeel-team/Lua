#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 gpt-5.1-codex 的 responses API
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

def test_codex_responses_api():
    """测试 codex 模型的 responses API"""
    print("=" * 60)
    print("测试 gpt-5.1-codex 的 responses API")
    print("=" * 60)
    
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
            print("\n测试 responses.create API...")
            
            # 测试代码生成任务
            test_input = "Write a Lua function to calculate the factorial of a number."
            
            try:
                # 检查是否有 responses 属性
                if not hasattr(client, 'responses'):
                    print("❌ 当前 SDK 版本不支持 responses API")
                    print("   请升级到最新版本的 OpenAI SDK: pip install --upgrade openai")
                    return False
                
                print(f"   输入: {test_input[:50]}...")
                response = client.responses.create(
                    model="gpt-5.1-codex",
                    input=test_input,
                    reasoning={"effort": "high"}
                )
                
                print("✅ responses API 调用成功")
                print(f"   输出: {response.output_text[:100]}...")
                return True
                
            except AttributeError as e:
                print(f"❌ responses API 不存在: {e}")
                print("   请升级到最新版本的 OpenAI SDK: pip install --upgrade openai")
                return False
            except Exception as e:
                error_msg = str(e)
                print(f"❌ API 调用失败: {error_msg}")
                
                # 检查是否是模型不存在的问题
                if "model" in error_msg.lower() or "not found" in error_msg.lower() or "404" in error_msg:
                    print("   提示: 模型可能不存在或不可用")
                elif "401" in error_msg or "403" in error_msg or "auth" in error_msg.lower():
                    print("   提示: API 密钥可能无效")
                else:
                    print("   提示: 请检查 API 调用参数")
                
                return False
                
        finally:
            restore_env(env_backup)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_codex_responses_api()
    if success:
        print("\n✅ Codex API 测试通过")
    else:
        print("\n❌ Codex API 测试失败")

