#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的配置测试脚本
"""

import json
import os

def test_config():
    """测试配置文件是否正确"""
    if not os.path.exists('config.json'):
        print("❌ config.json 不存在，请先运行系统以自动创建")
        return False
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检查必需的配置项
        required_keys = ['modules', 'api_config']
        for key in required_keys:
            if key not in config:
                print(f"❌ 缺少配置项: {key}")
                return False
        
        # 检查模块配置
        required_modules = [
            'screenwriter', 'stage_design', 'stage_programmer',
            'casting_design', 'character_config', 'executive_director'
        ]
        
        for module in required_modules:
            if module not in config['modules']:
                print(f"❌ 缺少模块配置: {module}")
                return False
            
            module_config = config['modules'][module]
            if 'prompt_template' not in module_config:
                print(f"❌ 模块 {module} 缺少 prompt_template")
                return False
        
        print("✅ 配置文件检查通过")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ 配置文件JSON格式错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 配置文件读取错误: {e}")
        return False

if __name__ == '__main__':
    test_config()

