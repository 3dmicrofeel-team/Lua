"""Validate generated LUA Encounter code against rule.md hard rules."""
import re
from typing import List, Tuple


def validate_encounter(code: str, assets: dict | None = None) -> List[str]:
    """
    Check Encounter code for rule.md compliance.
    Returns list of error messages; empty list = passes.
    """
    errors: List[str] = []
    code_clean = code.strip()

    # Rule 1: 防重复触发
    if "_G.enc" not in code_clean or "_done" not in code_clean:
        errors.append("缺少 _G.encXX_done 防重复逻辑（if _G.encXX_done then return end / _G.encXX_done = true）")

    # Rule 2: 对象合法性检查
    if "IsValid()" not in code_clean and "IsValid" not in code_clean:
        errors.append("缺少对象 IsValid() 检查，必须对 player 和所有 NPC 做 if not obj or not obj:IsValid() then return end")

    if "World.GetByID" in code_clean and "IsValid" not in code_clean:
        errors.append("使用了 World.GetByID 但未对返回对象做 IsValid 检查")

    # Rule 5: 奖励必须用 GiveItem/GiveWeapon/GiveEquip
    reward_keywords = ["获得", "奖励", "给", "得到", "拿到"]
    has_reward_hint = any(kw in code_clean for kw in reward_keywords)
    has_give_call = "GiveItem" in code_clean or "GiveWeapon" in code_clean or "GiveEquip" in code_clean
    if has_reward_hint and "Toast" in code_clean and not has_give_call:
        # Toast 提及获得但无 Give* 调用
        if re.search(r'Toast\s*\(\s*["\'].*[获给得].*["\']', code_clean):
            errors.append("奖励必须调用 npc:GiveItem/GiveWeapon/GiveEquip，Toast 仅用于提示，不能代替发奖")

    # Rule 4: UI.Ask/AskMany 必须用选项文案比较，禁止 "A"、"B"、true
    if re.search(r'==\s*["\']A["\']', code_clean) or re.search(r'==\s*true\b', code_clean):
        errors.append("UI.Ask/AskMany 返回值必须用选项的实际文案比较（如 if r == \"答应\"），禁止用 == \"A\" 或 == true")

    # Rule 6: 奇遇位置不要离玩家出生点太远
    if re.search(r'return\s*\{\s*X\s*=\s*0\s*,?\s*Y\s*=\s*0\s*,?\s*Z\s*=\s*0\s*\}', code_clean):
        errors.append("ResolveEncounterLoc() 禁止返回 {X=0,Y=0,Z=0}，应返回靠近玩家落地位置(约11536,11963,90)的坐标，Z 须为地面高度 90")

    # Rule 7: 敌人必须用 World.SpawnEnemy，禁止放 npcData
    if re.search(r'npcData\s*=\s*\{[^}]*["\']Enemy[_A-Za-z0-9]+["\']', code_clean):
        errors.append("敌人不得放入 npcData，必须用 World.SpawnEnemy(id, loc, count) 或 World.SpawnEnemyAtPlayer(id, count) 生成")

    # Rule 8: PlayMiniGame gameType 必须来自素材库 minigames
    if "PlayMiniGame" in code_clean and assets:
        allowed = set(assets.get("minigames", []) or [])
        match = re.search(r'PlayMiniGame\s*\(\s*["\']([^"\']+)["\']', code_clean)
        if match:
            used = match.group(1)
            if allowed and used not in allowed:
                errors.append(f"UI.PlayMiniGame 的 gameType \"{used}\" 不在素材库 minigames 中，仅可用: {', '.join(sorted(allowed))}")

    # Rule 9: GiveItem/GiveWeapon/GiveEquip 的道具 ID 必须来自素材库 items
    if assets and (allowed_items := set(assets.get("items", []) or [])):
        for method in ["GiveItem", "GiveWeapon", "GiveEquip"]:
            for m in re.finditer(rf'{method}\s*\(\s*["\']([^"\']+)["\']', code_clean):
                used = m.group(1)
                if used not in allowed_items:
                    errors.append(f"npc:{method}(\"{used}\") 的道具不在素材库 items 中，仅可用: {', '.join(sorted(allowed_items)[:20])}{'...' if len(allowed_items) > 20 else ''}")

    # 基本结构
    if "World.SpawnEncounter" not in code_clean and "encounter" in code_clean.lower():
        pass  # 可能是片段
    if "SpawnEncounter_" not in code_clean and "function " in code_clean:
        if "encXX" in code_clean or "enc_" in code_clean:
            errors.append("应有 function SpawnEncounter_XXX() 并调用 World.SpawnEncounter")

    return errors


def validate_all(generated_files: dict) -> Tuple[dict, List[str]]:
    """
    Validate all generated LUA files.
    Returns (file_errors: {filename: [errors]}, all_errors: flat list).
    """
    file_errors = {}
    all_errors = []

    for filename, code in generated_files.items():
        if filename == "Main.lua":
            continue
        if "encounter" in filename.lower() or "Encounters" in filename:
            errs = validate_encounter(code)
            if errs:
                file_errors[filename] = errs
                all_errors.extend([f"[{filename}] {e}" for e in errs])

    return file_errors, all_errors
