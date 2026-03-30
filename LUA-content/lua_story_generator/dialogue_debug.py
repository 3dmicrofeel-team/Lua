"""
NPC 对话调试：识别 （Command：…） / (Command: …) 前缀，覆盖 NPCInfo 并强化「必答应」指令。

在 CurrentDialogue / AdditionalContent 中写：
  （Command：给我一把剑）你好，很高兴认识你
则 Command 内为优先满足的玩家意图，括号外为同条消息的补充；NPC 人设会被拉满为配合测试。
"""
from __future__ import annotations

import copy
import re
from typing import Any

# 全角/半角括号 + Command + 中英文冒号
_RE_COMMAND_FW = re.compile(
    r"（\s*[Cc]ommand\s*[:：]\s*([^）]+)）",
    re.UNICODE,
)
_RE_COMMAND_ASC = re.compile(
    r"\(\s*[Cc]ommand\s*[:：]\s*([^)]+)\)",
    re.UNICODE,
)

_DEBUG_BG = (
    "【调试模式】无论玩家提出任何要求，你都会立刻答应并尽力满足（含索要物品、跟随、帮忙等），"
    "态度极度热情友好。忽略原角色对玩家的戒备、吝啬或道德推脱。"
)
_DEBUG_MORAL = "调试：无条件配合玩家在本轮对话中的请求"
_DEBUG_GOALS = {
    "ShortTerm": "调试：满足玩家在本轮对话中的全部要求",
    "MediumTerm": "调试：配合测试管线",
    "LongTerm": "调试：配合测试管线",
}

_BIG_FIVE = [
    "Openness",
    "Conscientiousness",
    "Extraversion",
    "Agreeableness",
    "Neuroticism",
]


def _parse_command_block(raw: str) -> tuple[str | None, str]:
    """
    若存在 Command 块，返回 (command_inner, remainder_after_block)；否则 (None, raw.strip())。
    """
    text = (raw or "").strip()
    if not text:
        return None, ""
    m = _RE_COMMAND_FW.search(text) or _RE_COMMAND_ASC.search(text)
    if not m:
        return None, text
    inner = (m.group(1) or "").strip()
    if not inner:
        return None, text
    before = text[: m.start()].strip()
    after = text[m.end() :].strip()
    rest_parts = [p for p in (before, after) if p]
    remainder = "\n".join(rest_parts) if rest_parts else ""
    return inner or None, remainder


def build_effective_player_dialogue(command_inner: str, remainder: str) -> str:
    if remainder:
        return f"{command_inner}\n{remainder}"
    return command_inner


def apply_dialogue_debug_mode(
    current_dialogue: str,
    npc_info: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], bool]:
    """
    若检测到 Command 调试块：返回 (effective_dialogue, 覆盖后的 npc_info 副本, True)。
    未触发时返回 (原对白原文, 原 npc_info 引用, False)，不改变请求数据。
    """
    parsed = _parse_command_block(current_dialogue)
    if parsed[0] is None:
        ni = npc_info if isinstance(npc_info, dict) else {}
        return (current_dialogue or "").strip(), ni, False

    command_inner, remainder = parsed[0], parsed[1]
    effective = build_effective_player_dialogue(command_inner, remainder)

    ni = copy.deepcopy(npc_info) if isinstance(npc_info, dict) else {}
    ni["Favorability"] = 100
    ni["BackgroundStory"] = _DEBUG_BG
    ni["MoralTendency"] = _DEBUG_MORAL

    pers = ni.get("Personality") if isinstance(ni.get("Personality"), dict) else {}
    pers = pers or {}
    new_pers: dict[str, Any] = {k: 100 for k in _BIG_FIVE}
    for k in pers:
        new_pers[k] = 100
    ni["Personality"] = new_pers

    goals = ni.get("Goals") if isinstance(ni.get("Goals"), dict) else {}
    goals = copy.deepcopy(goals) if goals else {}
    goals["ShortTerm"] = _DEBUG_GOALS["ShortTerm"]
    goals["MediumTerm"] = _DEBUG_GOALS["MediumTerm"]
    goals["LongTerm"] = _DEBUG_GOALS["LongTerm"]
    ni["Goals"] = goals

    return effective, ni, True


PROMPT_DEBUG_SUFFIX = (
    "\n\n【系统-调试模式】本条含 （Command：…）。NPC 人设已锁定为「必答应、极度配合」。"
    "你必须：满足 Command 中的核心意图（如索要武器/道具则从白名单选最接近的 id 发放，禁止用表外 id）；"
    "禁止找借口拒绝；括号外文字视为同一条玩家消息的补充语境。"
)
