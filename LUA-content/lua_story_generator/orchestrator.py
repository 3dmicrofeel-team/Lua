"""Orchestrator: Story -> Plan -> Code with Skills + Validation Feedback Loop."""
import re
from pathlib import Path

from openai import OpenAI

from agents import (
    extract_steps_from_planner_output,
    run_coding_agent,
    run_planner,
    run_story_expert,
)
from stage_loader import get_init_map_code, get_npc_located_code, get_start_game_code
from config import GROUND_Z
from validate_lua import validate_encounter

MAX_FIX_RETRIES = 2


def _inject_encounter_location(code: str, user_loc: dict) -> str:
    """强制将用户在地图上指定的奇遇点坐标注入到生成代码中，确保故事发生在指定位置。"""
    if not user_loc:
        return code
    x = user_loc.get("X") or user_loc.get("x")
    y = user_loc.get("Y") or user_loc.get("y")
    z = user_loc.get("Z") or user_loc.get("z") or GROUND_Z
    if x is None or y is None:
        return code
    x, y, z = int(x), int(y), int(z)
    target = f"{{X={x}, Y={y}, Z={z}}}"

    # 1. 替换 ResolveEncounterLoc() 的 return 语句（支持 {X=1, Y=2, Z=3} 与 {X=1,Y=2,Z=3}）
    pattern1 = re.compile(
        r"(local\s+function\s+ResolveEncounterLoc\s*\(\)\s*)"
        r"return\s*\{\s*X\s*=\s*[\d.]+\s*,\s*Y\s*=\s*[\d.]+\s*,\s*Z\s*=\s*[\d.]+\s*\}",
        re.IGNORECASE,
    )
    code = pattern1.sub(r"\1return " + target, code)

    # 2. 替换 World.SpawnEncounter 的第一个参数（字面量坐标）
    pattern2 = re.compile(
        r"World\.SpawnEncounter\s*\(\s*\{\s*X\s*=\s*[\d.]+\s*,\s*Y\s*=\s*[\d.]+\s*,\s*Z\s*=\s*[\d.]+\s*\}\s*,",
        re.IGNORECASE,
    )
    code = pattern2.sub(f"World.SpawnEncounter({target}, ", code)

    return code


def _extract_previous_npc_info(init_event_code: str) -> list[dict]:
    """从上一幕 InitEvent 代码中提取 NPC 信息（ID、resource、身份），供续写时参考。"""
    if not init_event_code or not init_event_code.strip():
        return []
    result = []
    code = init_event_code
    # 匹配 npcData = { enc07_drunk = "Merchant_Male", enc08_alice = "Doctor_Female" } 或类似格式
    npc_data_match = re.search(r'npcData\s*=\s*\{([^}]+)\}', code, re.DOTALL)
    if npc_data_match:
        body = npc_data_match.group(1)
        for m in re.finditer(r'(\w+)\s*=\s*["\']([^"\']+)["\']', body):
            enc_id, resource = m.group(1), m.group(2)
            if enc_id.startswith("enc") and resource:
                role_hint = enc_id.split("_")[-1] if "_" in enc_id else enc_id.replace("enc", "")
                result.append({"id": enc_id, "resource": resource, "role_hint": role_hint, "role_display": None})
    # 从 UI.ShowDialogue("角色名", ...) 提取对话中的身份称呼，按出现顺序关联
    dialogue_names = []
    for m in re.finditer(r'UI\.ShowDialogue\s*\(\s*["\']([^"\']+)["\']', code):
        name = m.group(1).strip()
        if name and len(name) <= 20 and not name.startswith("enc") and name not in dialogue_names:
            dialogue_names.append(name)
    for i, r in enumerate(result):
        if i < len(dialogue_names):
            r["role_display"] = dialogue_names[i]
    return result


def run_full_pipeline(
    story_input: str,
    api_key: str,
    story_model: str = "gpt-4.1",
    planning_model: str = "gpt-4.1",
    coding_model: str = "gpt-5.1-codex-max",
    assets: dict | None = None,
    encounter_locations: list[dict] | None = None,
    story_mode: str = "expand",
    init_map_code: str | None = None,
    previous_init_event: str | None = None,
) -> dict:
    """
    Execute: Story Expert -> Planner -> Coding Agent (encounters only).
    输出 stages 数组：InitMap, InitEvent, StartGame。
    """
    client = OpenAI(api_key=api_key)
    assets = assets or {"npcs": [], "enemies": [], "props": [], "items": []}
    # 若用户提供了编辑后的 InitMap，从中提取 NPC 布置供编码参考
    if init_map_code and init_map_code.strip():
        npc_match = re.search(r"-- =+ 放置路人NPC[\s\S]*?(?=\n\n|\Z)", init_map_code)
        npc_located = npc_match.group(0).strip() if npc_match else init_map_code[:3000]
    else:
        npc_located = get_npc_located_code()

    previous_npc_info = []
    if story_mode == "continue" and previous_init_event and previous_init_event.strip():
        previous_npc_info = _extract_previous_npc_info(previous_init_event)

    expanded_story = run_story_expert(client, story_input, story_model, story_mode=story_mode,
                                     previous_npc_info=previous_npc_info)
    plan_output = run_planner(client, expanded_story, planning_model, assets=assets)
    steps = extract_steps_from_planner_output(plan_output)
    steps = [s for s in steps if str(s.get("type", "")).lower() == "encounter"]
    # 【强制单奇遇】仅保留第 1 个 step，禁止多步
    if steps:
        steps = [steps[0]]
    if not steps:
        steps = [{"id": 1, "name": "SpawnEncounter_main", "type": "encounter", "description": "Main encounter"}]
    steps[0]["name"] = "SpawnEncounter_main"

    previous_code = ""
    init_event_parts = []

    for i, step in enumerate(steps):
        code = _generate_step_with_validation(
            client, step, expanded_story, previous_code, coding_model,
            assets=assets, all_steps=steps, step_index=i,
            npc_located_context=npc_located,
            encounter_locations=encounter_locations,
            previous_npc_info=previous_npc_info,
        )
        code = _clean_code_output(code)
        user_loc = None
        if encounter_locations and i < len(encounter_locations):
            loc = encounter_locations[i]
            if isinstance(loc, dict):
                x = loc.get("x") or loc.get("X")
                y = loc.get("y") or loc.get("Y")
                if x is not None and y is not None:
                    user_loc = {"X": int(x), "Y": int(y), "Z": int(loc.get("z") or loc.get("Z") or GROUND_Z)}
        code = _inject_encounter_location(code, user_loc)
        init_event_parts.append(code)
        previous_code += "\n\n" + code

    init_map_final = (init_map_code and init_map_code.strip()) or get_init_map_code()
    init_event_code = "\n\n".join(init_event_parts) if init_event_parts else ""
    # 单奇遇时添加正确格式注释
    if len(steps) == 1 and init_event_code:
        init_event_code = (
            "-- 奇遇：Main encounter from story\n"
            "-- 直接执行：固定坐标生成\n\n"
            + init_event_code
        )
    start_game_code = get_start_game_code()

    stages = [
        {"Type": "InitMap", "Code": init_map_final},
        {"Type": "InitEvent", "Code": init_event_code},
        {"Type": "StartGame", "Code": start_game_code},
    ]
    full_script = "\n\n".join(s["Code"] for s in stages if s["Code"])

    generated_files = {}
    for i, step in enumerate(steps):
        step_name = step.get("name", f"step_{i+1}")
        base = step_name.replace("SpawnEncounter_", "").lower()
        filename = f"Encounters/enc_{base}.lua"
        generated_files[filename] = init_event_parts[i] if i < len(init_event_parts) else ""

    return {
        "expanded_story": expanded_story,
        "plan_output": plan_output,
        "steps": steps,
        "generated_files": generated_files,
        "stages": stages,
        "full_script": full_script,
    }


def _generate_step_with_validation(
    client, step, expanded_story, previous_code, coding_model, assets: dict,
    all_steps: list | None = None,
    step_index: int = 0,
    npc_located_context: str = "",
    encounter_locations: list[dict] | None = None,
    previous_npc_info: list[dict] | None = None,
) -> str:
    """Generate code for one step, with validation feedback loop for Encounter."""
    def _call_agent(errors=None):
        return run_coding_agent(
            client, step, expanded_story, previous_code, coding_model,
            validation_errors=errors, assets=assets, all_steps=all_steps or [],
            step_index=step_index, npc_located_context=npc_located_context,
            encounter_locations=encounter_locations,
            previous_npc_info=previous_npc_info or [],
        )

    code = _call_agent(errors=None)
    code = _clean_code_output(code)

    if step.get("type") != "encounter":
        return code

    errors = validate_encounter(code, assets)
    retries = 0
    while errors and retries < MAX_FIX_RETRIES:
        code = _call_agent(errors=errors)
        code = _clean_code_output(code)
        errors = validate_encounter(code, assets)
        retries += 1

    return code


def _clean_code_output(text: str) -> str:
    """Remove markdown code blocks if present."""
    text = text.strip()
    m = re.search(r"```(?:lua)?\s*\n([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text


