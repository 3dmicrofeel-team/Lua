"""
Stage loader: 加载固定阶段的 LUA 代码。
InitMap = step1 + step2 + step3
StartGame = step5
InitEvent 由 AI 生成，生成时可读取 step3 作为 NPC 布置参考。
"""
from pathlib import Path

APP_DIR = Path(__file__).parent

STEP1 = APP_DIR / "step1_start.lua"
STEP2 = APP_DIR / "step2_map_generate.lua"
STEP3 = APP_DIR / "step3_npc_located.lua"
STEP5 = APP_DIR / "step5_gamestart.lua"


def load_step(path: Path) -> str:
    """Load a step file, return empty string if missing."""
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def get_init_map_code() -> str:
    """InitMap: step1 + step2 + step3 拼接."""
    s1 = load_step(STEP1)
    s2 = load_step(STEP2)
    s3 = load_step(STEP3)
    parts = [p for p in [s1, s2, s3] if p]
    return "\n\n".join(parts)


def get_start_game_code() -> str:
    """StartGame: step5 固定内容."""
    return load_step(STEP5)


def get_npc_located_code() -> str:
    """step3 内容，供 InitEvent 生成时参考（已布置的 NPC）。"""
    return load_step(STEP3)
