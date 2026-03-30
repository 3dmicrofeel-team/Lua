"""Multi-agent system: Story Expert, Planner, Coding Agent with Skills + TPA + Feedback."""
import json
import re
from typing import Optional

from openai import OpenAI

import config
from skills_loader import get_full_docs, get_skill_for_step
from prompts.story_expert import (
    STORY_BASE_RULES,
    STORY_CONTINUE_SYSTEM,
    STORY_CONTINUE_USER,
    STORY_EXPAND_SYSTEM,
    STORY_EXPAND_USER,
)
from prompts.planner import PLANNER_SYSTEM, PLANNER_USER, PLANNING_SKILL
from prompts.coding_agent import CODING_BASE, CODING_FIX, CODING_USER


def _call_chat(
    client: OpenAI,
    model: str,
    messages: list,
) -> str:
    """Call Chat Completions API (for GPT 4.1, 5.1)."""
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content or ""


def _call_responses(
    client: OpenAI,
    model: str,
    input_text: str,
) -> str:
    """Call Responses API (for Codex). client.responses.create()"""
    result = client.responses.create(
        model=model,
        input=input_text,
        reasoning={"effort": "high"},
    )
    if hasattr(result, "output_text") and result.output_text:
        return result.output_text
    if hasattr(result, "output") and result.output:
        texts = []
        for item in result.output:
            if hasattr(item, "content") and item.content:
                for block in item.content:
                    if hasattr(block, "text") and block.text:
                        texts.append(block.text)
        if texts:
            return "\n".join(texts)
    return str(result) if result else ""


def run_story_expert(
    client: OpenAI,
    story_input: str,
    model: str,
    story_mode: str = "expand",
    previous_npc_info: list[dict] | None = None,
) -> str:
    """Agent 1: Story Expert - expand or continue story into full 奇遇剧本.
    story_mode: 'expand'=扩写（自然语言梗概→完整剧本）, 'continue'=续写（前一章→下一章）
    """
    base_rules = STORY_BASE_RULES
    if story_mode == "continue":
        npc_block = ""
        if previous_npc_info:
            lines = ["=== 【前一幕 NPC 信息】（续写时可复用这些角色，保持 resource 与身份一致）==="]
            for n in previous_npc_info:
                rid = n.get("id", "")
                res = n.get("resource", "")
                hint = n.get("role_hint", "")
                disp = n.get("role_display", "")
                ident = f"，身份/称呼：{disp}" if disp else f"，角色提示：{hint}" if hint else ""
                lines.append(f"- {rid} → resource={res}{ident}")
            npc_block = "\n".join(lines) + "\n\n"
        system_prompt = STORY_CONTINUE_SYSTEM.format(base_rules=base_rules)
        user_content = STORY_CONTINUE_USER.format(npc_block=npc_block, story_input=story_input)
    else:
        system_prompt = STORY_EXPAND_SYSTEM.format(base_rules=base_rules)
        user_content = STORY_EXPAND_USER.format(story_input=story_input)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return _call_chat(client, model, messages)


def run_planner(
    client: OpenAI,
    expanded_story: str,
    model: str,
    assets: dict | None = None,
) -> str:
    """Agent 2: Planner - 仅规划 Encounter 步骤（Setup 固定不生成）"""
    asset_note = ""
    if assets:
        npcs = ", ".join(assets.get("npcs", [])) or "无"
        enemies = ", ".join(assets.get("enemies", [])) or "无"
        items = ", ".join(assets.get("items", [])) or "无"
        asset_note = f"\n素材库限制：NPC 仅可用 [{npcs}]，Enemy 仅可用 [{enemies}]，奖励道具（GiveItem/GiveWeapon/GiveEquip）仅可用 [{items}]。"
    full_docs = get_full_docs()
    system_prompt = PLANNER_SYSTEM.format(asset_note=asset_note, planning_skill=PLANNING_SKILL)
    user_msg = PLANNER_USER.format(full_docs=full_docs[:12000], expanded_story=expanded_story)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]
    return _call_chat(client, model, messages)


def run_coding_agent(
    client: OpenAI,
    step: dict,
    expanded_story: str,
    previous_code: str,
    model: str,
    validation_errors: Optional[list] = None,
    assets: dict | None = None,
    all_steps: Optional[list] = None,
    step_index: int = 0,
    npc_located_context: str = "",
    encounter_locations: Optional[list[dict]] = None,
    previous_npc_info: Optional[list[dict]] = None,
) -> str:
    """
    Agent 3: Coding Agent - generate LUA using Skills.
    仅使用素材库内的 NPC/Enemy/Prop，禁止库外 ID。
    """
    step_name = step.get("name", "unknown")
    step_desc = step.get("description", "")
    step_type = step.get("type", "general")

    skill_content = get_skill_for_step(step_type, step_name)

    asset_constraint = ""
    if assets:
        npcs = assets.get("npcs", [])
        enemies = assets.get("enemies", [])
        props = assets.get("props", [])
        items = assets.get("items", [])
        minigames = assets.get("minigames", []) or []
        asset_constraint = f"""
=== 【强制】素材库约束（禁止使用库外 ID）===
- npcData 中的 NPC 类型仅可使用: {", ".join(npcs) if npcs else "（无）"}
- World.SpawnEnemy / AddEnemySpawn 仅可用 Enemy: {", ".join(enemies) if enemies else "（无）"}
- Env.AddProp / placeProp 仅可用 Prop: {", ".join(props) if props else "（无）"}
- **npc:GiveItem / GiveWeapon / GiveEquip** 奖励道具仅可使用: {", ".join(items) if items else "（无）"}
- **UI.PlayMiniGame(gameType, lv)** 的 gameType 仅可使用: {", ".join(minigames) if minigames else "（无，禁止使用 PlayMiniGame）"}
- 不得使用以上列表之外的任何 ID。
"""

    use_codex = "codex" in model.lower()
    base_prompt = CODING_BASE.format(asset_constraint=asset_constraint, skill_content=skill_content)

    # 连续奇遇上下文
    chain = step.get("chain")
    chain_order = step.get("chainOrder")
    is_final = step.get("isFinal", False)
    chain_context = ""
    if chain and all_steps:
        chain_steps = [s for s in all_steps if s.get("chain") == chain]
        chain_context = f"""
=== 【连续奇遇】本步骤属于 chain="{chain}"，chainOrder={chain_order}，isFinal={is_final} ===
- 使用 _G.{chain.replace("-", "_")}_* 共享状态（如 _G.drunkard_ring_agreed, _G.drunkard_ring_hasRing）
- **谢礼（GiveWeapon/GiveEquip/金钱）仅能在 isFinal=true 的最后一环发放**；中间环可发放任务道具（GiveItem）供最后一环判定
- 前一环设置状态供后一环读取；最后一环检查状态后发放谢礼
- 每环仍有自己的 _G.encXX_done 防重复
"""
        if is_final and len(chain_steps) > 1:
            chain_context += f"- 本步骤为 chain 最后一环，在此发放奖励。前面 {len(chain_steps)-1} 环不得发奖。\n"

    # 奇遇位置：用户指定优先，否则根据步骤顺序推算
    total_steps = len(all_steps) if all_steps else 1
    order = step_index + 1  # 1-based
    from config import GROUND_Z, ENCOUNTER_BASE_X, ENCOUNTER_BASE_Y
    loc_hint = ""
    user_loc = None
    if encounter_locations and step_index < len(encounter_locations):
        loc = encounter_locations[step_index]
        if isinstance(loc, dict):
            x = loc.get("x") or loc.get("X")
            y = loc.get("y") or loc.get("Y")
            z = loc.get("z") or loc.get("Z") or GROUND_Z
            if x is not None and y is not None:
                user_loc = {"X": int(x), "Y": int(y), "Z": int(z)}
    if user_loc:
        loc_hint = f"\n=== 【奇遇位置】用户已指定本步骤触发点，必须使用以下坐标：{{X={user_loc['X']}, Y={user_loc['Y']}, Z={user_loc['Z']}}} ==="
    elif order == 1:
        loc_hint = f"\n=== 【奇遇位置】本步骤为第 1 步（最先发生），应离玩家落地位置(约11536,11963,90)最近，Z 必须为地面高度 {GROUND_Z}，如 {{X={ENCOUNTER_BASE_X}, Y={ENCOUNTER_BASE_Y}, Z={GROUND_Z}}} ==="
    else:
        offset = (order - 1) * 1100  # 每步 +1100
        loc_hint = f"\n=== 【奇遇位置】本步骤为第 {order} 步（共 {total_steps} 步），应距第 1 步至少 {(order-1)*1000} 单位，Z 必须为地面高度 {GROUND_Z}，如 {{X={ENCOUNTER_BASE_X + offset}, Y={ENCOUNTER_BASE_Y}, Z={GROUND_Z}}} 或 {{X={ENCOUNTER_BASE_X - offset}, Y={ENCOUNTER_BASE_Y - offset}, Z={GROUND_Z}}} ==="

    if validation_errors:
        fix_errors_str = "\n".join("- " + e for e in validation_errors)
        fix_prompt = CODING_FIX.format(validation_errors=fix_errors_str)
    else:
        fix_prompt = ""

    npc_ref = ""
    if npc_located_context and npc_located_context.strip():
        npc_ref = f"""
=== 【前置 NPC 布置参考】(step3_npc_located.lua，地图已放置的 NPC 类型与坐标) ===
{npc_located_context[:3000]}

奇遇可复用这些 NPC 类型（Merchant_Male, Hunter_Male 等），或使用 npcData 生成新的 encounter NPC。
"""

    previous_npc_ref = ""
    if previous_npc_info:
        lines = ["=== 【前一幕 NPC 信息】（续写时复用，保持 resource 与身份一致）==="]
        for n in previous_npc_info:
            rid = n.get("id", "")
            res = n.get("resource", "")
            disp = n.get("role_display") or n.get("role_hint", "")
            lines.append(f"- {rid} → resource={res}，身份/称呼：{disp}")
        previous_npc_ref = "\n".join(lines) + "\n\n"

    user_msg = CODING_USER.format(
        step_name=step_name,
        step_desc=step_desc,
        step_type=step_type,
        chain_context=chain_context,
        loc_hint=loc_hint,
        npc_ref=npc_ref,
        previous_npc_ref=previous_npc_ref,
        fix_prompt=fix_prompt,
        expanded_story=expanded_story[:2500],
        previous_code=previous_code[:2000] if previous_code else "（无）",
    )

    full_input = f"{base_prompt}\n\n{user_msg}"

    if use_codex:
        return _call_responses(client, model, full_input)
    messages = [
        {"role": "system", "content": base_prompt},
        {"role": "user", "content": user_msg},
    ]
    return _call_chat(client, model, messages)


def extract_steps_from_planner_output(plan_output: str) -> list:
    """Parse planner output to get step list."""
    match = re.search(r"\{[\s\S]*\"steps\"[\s\S]*\}", plan_output)
    if match:
        try:
            data = json.loads(match.group(0))
            return data.get("steps", [])
        except json.JSONDecodeError:
            pass
    steps = []
    for m in re.finditer(r"Step\s+(\d+):\s*(\w+)[\s\-]+(.+?)(?=Step\s+\d+:|$)", plan_output, re.DOTALL):
        steps.append({
            "id": int(m.group(1)),
            "name": m.group(2).strip(),
            "description": m.group(3).strip()[:200],
            "type": "encounter" if "enc" in m.group(2).lower() else "setup",
        })
    return steps if steps else [
        {"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "Main encounter from story"}
    ]
