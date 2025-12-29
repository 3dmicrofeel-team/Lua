#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新 OpenAI SDK 到最新版本
"""

import subprocess
import sys

def update_openai():
    """更新 OpenAI SDK"""
    print("正在更新 OpenAI SDK...")
    try:
        # 卸载旧版本
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "openai"])
        print("✅ 已卸载旧版本")
        
        # 安装新版本
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "openai>=1.12.0"])
        print("✅ 已安装新版本")
        
        # 验证安装
        import openai
        print(f"✅ OpenAI SDK 版本: {openai.__version__}")
        return True
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("OpenAI SDK 更新工具")
    print("=" * 50)
    if update_openai():
        print("\n✅ 更新完成！请重启服务器。")
    else:
        print("\n❌ 更新失败，请手动运行: pip install --upgrade openai")

