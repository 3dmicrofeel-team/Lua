"""
对话 / NPC 思考 Skill 加载器。
从 skills 加载 SKILL.md；LUA API 从 ChronicleForge/Doc/Lua_Function(for AI) **每次调用时**重新读磁盘合并（见 lua_reference_loader）。
若目录无 .md 则使用各 skill 内置 reference.md 作为 fallback。
"""
from pathlib import Path

from lua_reference_loader import load_merged_lua_function_markdown

SKILLS_DIR = Path(__file__).parent / "skills"


def _load_skill_file(skill_name: str, filename: str) -> str:
    """从 skill 目录加载文件。"""
    path = SKILLS_DIR / skill_name / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_dialogue_skill_and_reference() -> str:
    """
    返回对话 Skill 完整内容：SKILL.md + API Reference。
    Reference 来自 load_merged_lua_function_markdown()（动态）；若为空则使用 skills/lua-dialogue/reference.md。
    """
    skill_md = _load_skill_file("lua-dialogue", "SKILL.md")
    if not skill_md:
        return ""

    ref_md = load_merged_lua_function_markdown()
    if not ref_md:
        ref_md = _load_skill_file("lua-dialogue", "reference.md")

    return f"{skill_md}\n\n---\n## API Reference（来自 Lua_Function 或 fallback）\n{ref_md}"


def get_npc_think_skill_and_reference() -> str:
    """
    返回 NPC 思考 Skill：lua-npc-interaction-performance/SKILL.md + 与对话相同的动态 LUA API 合并文档。
    """
    skill_md = _load_skill_file("lua-npc-interaction-performance", "SKILL.md")
    if not skill_md:
        return ""

    ref_md = load_merged_lua_function_markdown()
    if not ref_md:
        ref_md = _load_skill_file("lua-dialogue", "reference.md")

    return f"{skill_md}\n\n---\n## API Reference（来自 Lua_Function 或 fallback）\n{ref_md}"
