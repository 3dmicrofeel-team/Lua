"""
ChronicleForge/Doc/Lua_Function(for AI) 合并加载。

- 不在模块内缓存合并结果：每次调用重新读磁盘，策划更新 .md 后下一轮请求即生效。
- 路径由 config.get_lua_reference_dir() 解析（每次调用可读最新 LUA_REFERENCE_DIR 环境变量）。
"""
from pathlib import Path

import config


def load_merged_lua_function_markdown() -> str:
    """合并 LUA_REFERENCE_DIR 下全部 *.md，按文件名排序。目录不存在或为空则返回空字符串。"""
    return _merge_md_files_in_dir(config.get_lua_reference_dir())


def _merge_md_files_in_dir(ref_dir: Path) -> str:
    if not ref_dir.exists() or not ref_dir.is_dir():
        return ""
    parts: list[str] = []
    for p in sorted(ref_dir.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        parts.append(f"## {p.stem}\n\n{text}")
    return "\n\n---\n\n".join(parts) if parts else ""
