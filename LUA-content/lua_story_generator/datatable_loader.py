"""
Load NPC, Enemy, Prop, Item, Animations from DataTable CSV files.
每次 load_resources() 调用时从磁盘读取；策划修改 CSV 后下次请求即生效，无需重启服务。
DT_AnimStartTable.csv → PlayAnimLoop 可用列表；DT_MontageTable.csv → PlayAnim 可用列表。
"""
import csv
import re
from pathlib import Path
from typing import Any

import config

DATATABLE_DIR = Path(config.DATATABLE_DIR)

FILENAMES = {
    "npcs": "DT_SpawnNPCTable.csv",
    "enemies": "DT_EnemyDataTable.csv",
    "props": "PropVilligeData.csv",
    "items": "DT_Items.csv",
    "anim_start": "DT_AnimStartTable.csv",
    "anim_montage": "DT_MontageTable.csv",
}


def _extract_nsloctext(text: str) -> str:
    """Extract readable display name from NSLOCTEXT(..., ..., \"Name\") format."""
    if not text or "NSLOCTEXT" not in text:
        return text or ""
    # Unreal NSLOCTEXT: last argument is display string. Formats: ""Name"" or "Name"
    m = re.search(r',\s*""([^"]*)""\s*\)', text)  # "", ""Name"")
    if m:
        return m.group(1)
    m = re.search(r',\s*"([^"]*)"\s*\)', text)  # , "Name")
    if m:
        return m.group(1)
    m = re.search(r",\s*'([^']*)'\s*\)", text)
    if m:
        return m.group(1)
    return text


def _load_csv(path: Path, encoding: str | None = None) -> list[dict[str, str]]:
    """Load CSV as list of dicts. Return [] on missing/invalid file.
    Tries utf-8 first; if content has UTF-16 null bytes, retries with utf-16-le."""
    if not path.exists():
        return []
    encodings = [encoding] if encoding else ["utf-8", "utf-16-le", "utf-16"]
    for enc in encodings:
        try:
            with open(path, encoding=enc, newline="", errors="replace") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if rows and enc == "utf-8":
                first_val = str(list(rows[0].values())[0]) if rows[0] else ""
                if "\x00" in first_val:
                    continue
            return rows
        except Exception:
            continue
    return []


def _get_first_column_value(row: dict) -> str:
    """Get value of first column (key often '---' in Unreal DataTable exports)."""
    if not row:
        return ""
    keys = list(row.keys())
    if not keys:
        return ""
    return (row.get(keys[0]) or "").strip()


def _load_npcs() -> list[str]:
    """Load NPC type IDs from DT_SpawnNPCTable.csv (first column)."""
    path = DATATABLE_DIR / FILENAMES["npcs"]
    rows = _load_csv(path)
    ids = []
    for row in rows:
        val = _get_first_column_value(row)
        if val and val != "---":
            ids.append(val)
    return sorted(set(ids))


def _load_enemies() -> list[str]:
    """Load Enemy IDs from DT_EnemyDataTable.csv (first column)."""
    path = DATATABLE_DIR / FILENAMES["enemies"]
    rows = _load_csv(path)
    ids = []
    for row in rows:
        val = _get_first_column_value(row)
        if val:
            ids.append(val)
    return sorted(set(ids))


def _load_props() -> list[dict[str, Any]]:
    """Load Prop entries from PropVilligeData.csv. Returns [{id, symbol, description}, ...]."""
    path = DATATABLE_DIR / FILENAMES["props"]
    rows = _load_csv(path)
    result = []
    for row in rows:
        symbol = (row.get("Symbol") or "").strip()
        if symbol:
            result.append({
                "id": symbol,
                "symbol": symbol,
                "description": (row.get("Description") or "").strip(),
                "actor": (row.get("Actor") or "").strip(),
            })
    return sorted(result, key=lambda x: x["id"])


def _load_anim_ids(csv_key: str) -> list[str]:
    """Load animation IDs from a CSV (first column)."""
    path = DATATABLE_DIR / FILENAMES[csv_key]
    rows = _load_csv(path)
    ids = []
    for row in rows:
        val = _get_first_column_value(row)
        if val and val != "---":
            ids.append(val)
    return sorted(set(ids))


def _load_animations() -> tuple[list[str], list[str], list[str]]:
    """Load animations: PlayAnim 用 DT_MontageTable，PlayAnimLoop 用 DT_AnimStartTable。返回 (anim_start, anim_montage, animations_merged)。"""
    anim_start = _load_anim_ids("anim_start")   # PlayAnimLoop 持续
    anim_montage = _load_anim_ids("anim_montage")  # PlayAnim 一次性
    merged = sorted(set(anim_start) | set(anim_montage))
    return anim_start, anim_montage, merged


def _load_items() -> list[dict[str, Any]]:
    """Load Item entries from DT_Items.csv. Returns [{id, name, item_type, quality}, ...]."""
    path = DATATABLE_DIR / FILENAMES["items"]
    rows = _load_csv(path)
    result = []
    for row in rows:
        row_id = _get_first_column_value(row)
        if not row_id or row_id == "---":
            continue
        item_name = row.get("ItemName", "") or ""
        display_name = _extract_nsloctext(item_name) or row_id
        result.append({
            "id": row_id,
            "name": display_name,
            "item_type": (row.get("ItemType") or "").strip(),
            "quality": (row.get("ItemQuality") or "").strip() or "null",
        })
    return sorted(result, key=lambda x: x["id"])


def load_resources() -> dict[str, Any]:
    """
    Load all resources from DataTable CSVs.
    Returns: {
        npcs: [id, ...],
        enemies: [id, ...],
        props: [{id, symbol, description, actor}, ...],
        items: [{id, name, item_type, quality}, ...],
        minigames: ["TTT"],  # fallback if no table
        source: "datatable",
        datatable_dir: str
    }
    """
    npcs = _load_npcs()
    enemies = _load_enemies()
    props = _load_props()
    items = _load_items()
    prop_ids = [p["id"] for p in props]
    item_ids = [i["id"] for i in items]
    anim_start, anim_montage, anims_merged = _load_animations()
    return {
        "npcs": npcs,
        "enemies": enemies,
        "props": prop_ids,
        "items": item_ids,
        "props_detail": props,
        "items_detail": items,
        "animations": anims_merged,
        "animations_play": anim_montage,  # PlayAnim 用 DT_MontageTable.csv
        "animations_loop": anim_start,    # PlayAnimLoop 用 DT_AnimStartTable.csv
        "minigames": ["TTT"],
        "source": "datatable",
        "datatable_dir": str(DATATABLE_DIR.resolve()),
    }


def get_assets_for_agents() -> dict[str, list]:
    """Return assets dict suitable for agents/orchestrator: {npcs, enemies, props, items, minigames}."""
    res = load_resources()
    return {
        "npcs": res["npcs"],
        "enemies": res["enemies"],
        "props": res["props"],
        "items": res["items"],
        "minigames": res["minigames"],
    }
