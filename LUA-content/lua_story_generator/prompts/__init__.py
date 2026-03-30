# prompts package - 所有 Prompt 集中管理，便于策划/开发者调整
from prompts.npc_think import NPC_THINK_MAIN_PROMPT
from prompts.npc_dialogue import NPC_DIALOGUE_MAIN_PROMPT
from prompts.story_expert import (
    STORY_BASE_RULES,
    STORY_CONTINUE_SYSTEM,
    STORY_CONTINUE_USER,
    STORY_EXPAND_SYSTEM,
    STORY_EXPAND_USER,
)
from prompts.planner import PLANNER_SYSTEM, PLANNER_USER, PLANNING_SKILL
from prompts.coding_agent import CODING_BASE, CODING_FIX, CODING_USER

__all__ = [
    "NPC_THINK_MAIN_PROMPT",
    "NPC_DIALOGUE_MAIN_PROMPT",
    "STORY_BASE_RULES",
    "STORY_CONTINUE_SYSTEM",
    "STORY_CONTINUE_USER",
    "STORY_EXPAND_SYSTEM",
    "STORY_EXPAND_USER",
    "PLANNER_SYSTEM",
    "PLANNER_USER",
    "PLANNING_SKILL",
    "CODING_BASE",
    "CODING_FIX",
    "CODING_USER",
]
