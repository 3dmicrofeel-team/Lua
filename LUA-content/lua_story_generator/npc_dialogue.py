"""NPC 对话功能：根据 Type=NPC_Dialogue_Request、Code={NPCInfo, CurrentDialogue} 生成回复 LUA。"""
import json
import re
from openai import OpenAI

from datatable_loader import load_resources
from dialogue_debug import PROMPT_DEBUG_SUFFIX, apply_dialogue_debug_mode
from dialogue_skill_loader import get_dialogue_skill_and_reference
from prompts.npc_dialogue import NPC_DIALOGUE_GIVE_ID_FIX_PROMPT, NPC_DIALOGUE_MAIN_PROMPT

_GIVE_CALL_RE = re.compile(
    r"Give(?:Item|Weapon|Equip)\s*\(\s*\"([^\"]+)\"\s*,",
    re.MULTILINE,
)


def _safe_str(v, default=""):
    if v is None:
        return default
    return str(v).strip() or default


def _parse_dialogue_code(code: dict | None) -> tuple[dict, str]:
    """从 Code 中解析 NPCInfo 和 CurrentDialogue。"""
    if not isinstance(code, dict):
        return {}, ""
    npc_info = code.get("NPCInfo") or code.get("npc_info") or {}
    current = (
        code.get("CurrentDialogue") or code.get("current_dialogue")
        or code.get("AdditionalContent")
        or ""
    )
    if not isinstance(npc_info, dict):
        npc_info = {}
    return npc_info, _safe_str(current)


def _format_items_catalog_str_from_res(res: dict) -> str:
    """DT_Items 列表，供 Prompt 约束 Give* 的 id。"""
    details = res.get("items_detail") or []
    if not details:
        return "（当前未读到 DT_Items.csv：请勿使用 Give*，仅生成台词；或只写拒绝赠予的回复。）"
    lines: list[str] = []
    for it in sorted(details, key=lambda x: str(x.get("id", ""))):
        iid = _safe_str(it.get("id"))
        if not iid:
            continue
        name = _safe_str(it.get("name")) or iid
        itype = _safe_str(it.get("item_type")) or "?"
        lines.append(f"- {iid}（{name}，{itype}）")
    return "\n".join(lines)


def _format_items_id_whitelist_str_from_res(res: dict) -> str:
    items = res.get("items") or []
    if not items:
        return "（无 — 请勿使用 GiveItem/GiveWeapon/GiveEquip）"
    return ", ".join(sorted(items))


def _invalid_give_ids_in_lua(lua: str, allowed: set[str]) -> list[str]:
    """按出现顺序去重列出不在白名单内的 Give* 第一参数。"""
    out: list[str] = []
    seen: set[str] = set()
    for m in _GIVE_CALL_RE.finditer(lua):
        gid = m.group(1)
        if gid in allowed or gid in seen:
            continue
        seen.add(gid)
        out.append(gid)
    return out


def _strip_lua_fenced_block(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        m = re.search(r"```(?:lua)?\s*\n([\s\S]*?)```", t)
        if m:
            return m.group(1).strip()
    return t


def _normalize_dialogue_lua_aliases(text: str) -> str:
    text = (
        text.replace("npc:SayWithDialoguebox(", "_self_:SayWithDialoguebox(")
        .replace("npc:Speak(", "_self_:SayWithDialoguebox(")
        .replace("_self_:Speak(", "_self_:SayWithDialoguebox(")
        .replace("npc:Say(", "_self_:SayWithDialoguebox(")
        .replace("_self_:Say(", "_self_:SayWithDialoguebox(")
        .replace("npc:PlayAnim(", "_self_:PlayAnim(")
        .replace("npc:PlayAnimLoop(", "_self_:PlayAnimLoop(")
    )
    text = text.replace("npc:", "_self_:")
    text = re.sub(r"\bself:", "_self_:", text)
    return text


def _ensure_player_preamble(text: str) -> str:
    _preamble = """local player = World.GetByID("Player")
if not player or not player:IsValid() then return end

"""
    if "World.GetByID" not in text:
        return _preamble + text.strip()
    return text


def generate_npc_dialogue_reply_lua(
    api_key: str,
    code: dict | None = None,
    animations: list[str] | None = None,
    animations_play: list[str] | None = None,
    animations_loop: list[str] | None = None,
) -> str:
    """
    根据 Type=NPC_Dialogue_Request 的 Code 生成 NPC 对话回复 LUA。
    Code 包含 NPCInfo 与 CurrentDialogue。
    返回包含 _self_:SayWithDialoguebox() 等的 LUA 脚本。
    """
    npc_info, current_dialogue = _parse_dialogue_code(code)
    current_dialogue, npc_info, dialogue_debug = apply_dialogue_debug_mode(current_dialogue, npc_info)

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
        info_parts.append(f"Goals - LongTerm: {_safe_str(goals.get('LongTerm') or goals.get('long_term'))}")
        info_parts.append(f"Goals - MediumTerm: {_safe_str(goals.get('MediumTerm') or goals.get('medium_term'))}")
        info_parts.append(f"Goals - ShortTerm: {_safe_str(goals.get('ShortTerm') or goals.get('short_term'))}")

    for key in ["ShortTermMemory", "MediumTermMemory", "LongTermMemory"]:
        v = npc_info.get(key) or npc_info.get(key[0].lower() + key[1:])
        if v:
            info_parts.append(f"{key}: {_safe_str(v)}")

    npc_info_str = "\n".join(info_parts) if info_parts else "未提供"
    current_str = current_dialogue or "（无）"
    if dialogue_debug:
        current_str = current_str + PROMPT_DEBUG_SUFFIX

    fallback_play = ["Attack", "Drink"]
    fallback_loop = ["Happy", "Wave", "Drink", "Dialogue", "Admiring"]
    anim_play = animations_play if (animations_play is not None and len(animations_play) > 0) else fallback_play
    anim_loop = animations_loop if (animations_loop is not None and len(animations_loop) > 0) else fallback_loop
    anim_play_str = ", ".join(anim_play[:40])
    anim_loop_str = ", ".join(anim_loop[:40])

    dialogue_skill = get_dialogue_skill_and_reference()
    if not dialogue_skill:
        dialogue_skill = "（未加载 dialogue skill，请检查 skills/lua-dialogue/SKILL.md 与 LUA_REFERENCE_DIR 指向的 Lua_Function(for AI)）"

    try:
        res = load_resources()
    except Exception:
        res = {}
    items_allowed = set(res.get("items") or [])
    if res.get("items_detail"):
        items_catalog_str = _format_items_catalog_str_from_res(res)
    else:
        items_catalog_str = "（加载 DataTable 失败或为空：请勿使用 GiveItem/GiveWeapon/GiveEquip，仅生成台词与动作。）"
    items_id_whitelist_str = _format_items_id_whitelist_str_from_res(res)

    prompt = NPC_DIALOGUE_MAIN_PROMPT.format(
        dialogue_skill=dialogue_skill,
        npc_info_json=npc_info_str,
        current_dialogue=current_str,
        anim_play_str=anim_play_str,
        anim_loop_str=anim_loop_str,
        items_catalog_str=items_catalog_str,
        items_id_whitelist_str=items_id_whitelist_str,
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
    )
    text = _strip_lua_fenced_block(response.choices[0].message.content or "")
    text = _normalize_dialogue_lua_aliases(text)

    invalid = _invalid_give_ids_in_lua(text, items_allowed)
    if invalid and items_allowed:
        fix_prompt = (
            NPC_DIALOGUE_GIVE_ID_FIX_PROMPT.replace("__INVALID_IDS__", ", ".join(invalid))
            .replace("__WHITELIST__", items_id_whitelist_str)
            .replace("__LUA__", text)
        )
        fix_resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": fix_prompt}],
        )
        text = _strip_lua_fenced_block(fix_resp.choices[0].message.content or "")
        text = _normalize_dialogue_lua_aliases(text)

    text = _ensure_player_preamble(text)

    return text
