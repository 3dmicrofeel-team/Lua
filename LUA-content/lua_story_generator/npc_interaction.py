"""NPC 思考功能：根据 UE 传入的 Type=NPC_Think_Begin、Code={NPCInfo, TagList} 生成 LUA 表演脚本。"""
import json
import re
from openai import OpenAI

from dialogue_skill_loader import get_npc_think_skill_and_reference
from prompts.npc_think import NPC_THINK_MAIN_PROMPT


def _safe_str(v, default=""):
    if v is None:
        return default
    return str(v).strip() or default


def _parse_code(code: dict | None) -> tuple[dict, list]:
    """从 Code 中解析 NPCInfo 和 TagList。"""
    if not isinstance(code, dict):
        return {}, []
    npc_info = code.get("NPCInfo") or code.get("npc_info") or {}
    tag_list = code.get("TagList") or code.get("tag_list") or []
    if not isinstance(npc_info, dict):
        npc_info = {}
    if not isinstance(tag_list, list):
        tag_list = []
    return npc_info, tag_list


def generate_npc_think_lua(
    api_key: str,
    code: dict | None = None,
    animations: list[str] | None = None,
    animations_play: list[str] | None = None,
    animations_loop: list[str] | None = None,
) -> str:
    """
    根据 Type=NPC_Think_Begin 的 Code 生成 NPC 思考 LUA。
    Code 包含 NPCInfo 与 TagList。
    返回 LUA 脚本：可含 _self_:Say / PlayAnim / PlayAnimLoop，以及按需的 MoveTo、World.Find、Time、Math 等。
    """
    npc_info, tag_list = _parse_code(code)

    # 构建供模型参考的 NPCInfo 摘要
    info_parts = []
    info_parts.append(f"Name: {_safe_str(npc_info.get('Name'))} | Title: {_safe_str(npc_info.get('Title'))} | Gender: {_safe_str(npc_info.get('Gender'))}")
    info_parts.append(f"BackgroundStory: {_safe_str(npc_info.get('BackgroundStory'), '未提供')}")
    info_parts.append(f"Favorability（对玩家好感）: {npc_info.get('Favorability', '未提供')}")
    info_parts.append(f"MoralTendency（道德倾向）: {npc_info.get('MoralTendency', '未提供')}")

    pers = npc_info.get("Personality") or npc_info.get("personality")
    if isinstance(pers, dict):
        info_parts.append(f"Personality（大五人格）: {json.dumps(pers, ensure_ascii=False)}")
    else:
        info_parts.append("Personality: 未提供")

    goals = npc_info.get("Goals") or npc_info.get("goals")
    if isinstance(goals, dict):
        info_parts.append(f"Goals - LongTerm（人生信念）: {_safe_str(goals.get('LongTerm') or goals.get('long_term'))}")
        info_parts.append(f"Goals - MediumTerm（阶段性规划）: {_safe_str(goals.get('MediumTerm') or goals.get('medium_term'))}")
        info_parts.append(f"Goals - ShortTerm（当下行为）: {_safe_str(goals.get('ShortTerm') or goals.get('short_term'))}")
    else:
        info_parts.append("Goals: 未提供")

    for key in ["ShortTermMemory", "MediumTermMemory", "LongTermMemory"]:
        v = npc_info.get(key) or npc_info.get(key[0].lower() + key[1:])
        if v:
            info_parts.append(f"{key}: {_safe_str(v)}")

    npc_info_str = "\n".join(info_parts) if info_parts else "未提供"

    # TagList 格式化
    tag_items = []
    for item in tag_list:
        if isinstance(item, dict):
            uid = item.get("UID") or item.get("uid") or ""
            tags = item.get("Tags") or item.get("tags") or []
            tag_items.append({"UID": uid, "Tags": tags if isinstance(tags, list) else []})
        else:
            tag_items.append({"UID": "", "Tags": []})
    tag_list_str = json.dumps(tag_items, ensure_ascii=False, indent=2) if tag_items else "[]（无周围可互动对象）"

    # 两表互不共用：PlayAnim 仅用 DT_MontageTable，PlayAnimLoop 仅用 DT_AnimStartTable
    fallback_play = ["Attack", "Drink"]
    fallback_loop = ["Happy", "Frustrated", "Wave", "Scared", "Shy", "Dance", "Drink", "Eat", "Idle", "PickUp", "Dialogue", "Admiring"]
    anim_play = animations_play if (animations_play is not None and len(animations_play) > 0) else fallback_play
    anim_loop = animations_loop if (animations_loop is not None and len(animations_loop) > 0) else fallback_loop
    anim_play_str = ", ".join(anim_play[:40])
    anim_loop_str = ", ".join(anim_loop[:40])

    think_skill = get_npc_think_skill_and_reference()
    if not think_skill:
        think_skill = "（未加载思考 Skill 或 LUA API 文档，请检查 skills/lua-npc-interaction-performance/SKILL.md 与 LUA_REFERENCE_DIR）"

    prompt = NPC_THINK_MAIN_PROMPT.format(
        think_skill=think_skill,
        npc_info_json=npc_info_str,
        tag_list_json=tag_list_str,
        anim_play_str=anim_play_str,
        anim_loop_str=anim_loop_str,
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
    )
    text = (response.choices[0].message.content or "").strip()
    if text.startswith("```"):
        m = re.search(r"```(?:lua)?\s*\n([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    text = (
        text.replace("npc:Speak(", "_self_:Say(")
        .replace("_self_:Speak(", "_self_:Say(")
        .replace("npc:Say(", "_self_:Say(")
        .replace("npc:PlayAnim(", "_self_:PlayAnim(")
        .replace("npc:PlayAnimLoop(", "_self_:PlayAnimLoop(")
        .replace("npc:MoveTo(", "_self_:MoveTo(")
        .replace("npc:MoveToActor(", "_self_:MoveToActor(")
        .replace("npc:LookAt(", "_self_:LookAt(")
        .replace("npc:ApproachAndSay(", "_self_:ApproachAndSay(")
        .replace("npc:GetPos(", "_self_:GetPos(")
    )
    # 兜底：统一 self: 前缀到 _self_:
    text = re.sub(r"\bself:", "_self_:", text)
    return text


def generate_npc_interaction_lua(
    api_key: str,
    prop_tag: str = "",
    prop_pos: dict | None = None,
    personality: dict | None = None,
    goal: dict | None = None,
    animations: list[str] | None = None,
) -> str:
    """
    兼容旧版 API：将 PropTag/Personality/Goal 转为 Code 格式后调用 generate_npc_think_lua。
    """
    goals = {}
    if goal and isinstance(goal, dict):
        g = goal.get("CurrentGoal") or goal.get("current_goal")
        if g:
            goals["ShortTerm"] = str(g)
    code = {
        "NPCInfo": {
            "Personality": personality if isinstance(personality, dict) else {},
            "Goals": goals,
        },
        "TagList": [{"UID": prop_tag or "", "Tags": [prop_tag] if prop_tag else []}],
    }
    return generate_npc_think_lua(api_key=api_key, code=code, animations=animations)
