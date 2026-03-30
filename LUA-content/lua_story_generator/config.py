"""Configuration for LUA Story Generator."""
import os
from pathlib import Path

# Model identifiers - 若 API 模型名不同可替换为 gpt-4o、gpt-4-turbo 等
STORY_MODELS = ["gpt-4.1", "gpt-5.1"]
PLANNING_MODELS = ["gpt-4.1", "gpt-5.1"]
CODING_MODELS = ["gpt-4.1", "gpt-5.1", "gpt-5.1-codex-max", "gpt-5.2-codex"]  # Codex 使用 Responses API

# Document paths (relative to project root, used by skills_loader)
LUA_API_DOC = "lua_atomic_modules_call_guide.md"
RULE_DOC = "rule.md"

# Project root (parent of lua_story_generator)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DataTable CSV 路径：素材库 NPC/Enemy/Prop/Item 从此读取
# PlayAnim 用 DT_MontageTable.csv，PlayAnimLoop 用 DT_AnimStartTable.csv
# 默认指向 ChronicleForge/Doc/DataTable（与 LUA 同级的 ChronicleForge 工程）
# 通过环境变量 DATATABLE_DIR 覆盖
_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_DATATABLE = _CONFIG_DIR / ".." / ".." / ".." / ".." / "ChronicleForge" / "Doc" / "DataTable"
DATATABLE_DIR = Path(os.environ.get("DATATABLE_DIR", str(_DEFAULT_DATATABLE.resolve())))

# LUA Reference：对话 / NPC 思考 从 ChronicleForge/Doc/Lua_Function(for AI) 按需读取（见 lua_reference_loader）
# 默认路径；运行时请用 get_lua_reference_dir()，以便 LUA_REFERENCE_DIR 在进程内被更新后仍能读到新路径
_DEFAULT_LUA_REFERENCE = _CONFIG_DIR / ".." / ".." / ".." / ".." / "ChronicleForge" / "Doc" / "Lua_Function(for AI)"


def get_lua_reference_dir() -> Path:
    """解析 LUA API 文档目录。每次调用重新读环境变量，避免写死；重启服务或改 env 后生效。"""
    env = os.environ.get("LUA_REFERENCE_DIR")
    if env and str(env).strip():
        return Path(env.strip()).expanduser().resolve()
    return _DEFAULT_LUA_REFERENCE.resolve()


# 兼容旧代码：模块导入时快照（若需与 env 同步请用 get_lua_reference_dir）
LUA_REFERENCE_DIR = get_lua_reference_dir()

# 地图地面高度与玩家出生区域（玩家落地后约 X=11536, Y=11963, Z=90）
GROUND_Z = 90
# 奇遇基准坐标：靠近玩家落地位置，确保触发盒子在地面层级
ENCOUNTER_BASE_X = 11600
ENCOUNTER_BASE_Y = 12000
