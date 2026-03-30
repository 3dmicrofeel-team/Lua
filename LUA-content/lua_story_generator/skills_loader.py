"""
Skills loader: Progressive disclosure for LUA generation.
Loads Skill metadata first, full instructions when step type matches.
"""
from pathlib import Path

import config

SKILLS_DIR = Path(__file__).parent / "skills"


def _load_skill_file(skill_name: str, filename: str) -> str:
    """Load a file from a skill directory."""
    path = SKILLS_DIR / skill_name / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_skill_for_step(step_type: str, step_name: str) -> str:
    """
    Load the relevant Skill for a coding step (progressive disclosure).
    Returns full Skill instructions + reference when needed.
    """
    step_lower = f"{step_name} {step_type}".lower()

    if "encounter" in step_lower or "奇遇" in step_lower or "spawnencounter" in step_lower:
        skill_md = _load_skill_file("lua-encounter", "SKILL.md")
        ref_md = _load_skill_file("lua-encounter", "reference.md")
        return f"{skill_md}\n\n---\n## API Reference\n{ref_md}"

    if "setup" in step_lower or "世界" in step_lower or "地图" in step_lower:
        skill_md = _load_skill_file("lua-setup-world", "SKILL.md")
        ref_md = _load_skill_file("lua-setup-world", "reference.md")
        return f"{skill_md}\n\n---\n## API Reference\n{ref_md}"

    # Fallback: load both encounter + planning overview
    enc = _load_skill_file("lua-encounter", "SKILL.md")
    plan = _load_skill_file("lua-planning", "SKILL.md")
    return f"{plan}\n\n{enc}"


def get_planning_skill() -> str:
    """Load planning Skill for Planner agent."""
    return _load_skill_file("lua-planning", "SKILL.md")


def get_full_docs() -> str:
    """Full rule + API docs for Planner (from project root)."""
    from pathlib import Path
    root = Path(config.PROJECT_ROOT)
    rule = (root / config.RULE_DOC).read_text(encoding="utf-8") if (root / config.RULE_DOC).exists() else ""
    api = (root / config.LUA_API_DOC).read_text(encoding="utf-8") if (root / config.LUA_API_DOC).exists() else ""
    return f"# RULE (rule.md)\n{rule}\n\n# LUA API\n{api}"
