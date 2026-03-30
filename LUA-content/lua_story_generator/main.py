"""FastAPI backend for LUA Story Generator."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, Field

import config
from datatable_loader import load_resources
from orchestrator import run_full_pipeline
from stage_loader import get_init_map_code

app = FastAPI(title="LUA Story to Script Generator")
APP_DIR = Path(__file__).parent
ASSETS_FILE = APP_DIR / "assets.json"
DEFAULT_ASSETS = APP_DIR / "assets_default.json"
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _log_lua_api_reference_source():
    """启动时打印 LUA API 文档路径与 .md 数量；每次请求仍重新读盘合并，此处仅便于确认 ChronicleForge 是否挂载正确。"""
    import sys

    try:
        from config import get_lua_reference_dir
        from lua_reference_loader import load_merged_lua_function_markdown

        d = get_lua_reference_dir()
        n = len(list(d.glob("*.md"))) if d.is_dir() else 0
        blob = load_merged_lua_function_markdown()
        print(
            f"[lua] LUA_REFERENCE_DIR={d} | {n} .md | merged {len(blob)} chars (re-read each request)",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[lua] LUA_REFERENCE_DIR check failed: {e}", file=sys.stderr)


class GenerateRequest(BaseModel):
    story_input: str = Field(..., validation_alias=AliasChoices("story_input", "content"))  # 前端 story_input，UE 插件 content
    api_key: str
    story_model: str = "gpt-4.1"
    planning_model: str = "gpt-4.1"
    coding_model: str = "gpt-5.1-codex-max"
    assets: dict | None = None  # {npcs:[], enemies:[], props:[]}
    stages_only: bool = False  # True 时仅返回 stages，不含 expanded_story 等
    encounter_locations: list[dict] | None = None  # [{x,y,z}, ...] 用户在地图上指定的奇遇触发点，按步骤顺序对应
    story_mode: str = "expand"  # expand=扩写(自然语言→剧本), continue=续写(前一章→下一章)
    init_map_code: str | None = None  # 用户在地图编辑器中编辑后的 InitMap 代码，若提供则优先使用（覆盖 stage_loader 模板）
    previous_init_event: str | None = None  # 续写时上一幕的 InitEvent 代码，用于提取 NPC 信息（id、resource、身份）


class AssetsModel(BaseModel):
    npcs: list[str] = []
    enemies: list[str] = []
    props: list[str] = []
    items: list[str] = []
    minigames: list[str] = []


class StageItem(BaseModel):
    Type: str  # InitMap | InitEvent | StartGame | Reopen | AddEvent | Dialogue
    Code: str


class GenerateResponse(BaseModel):
    expanded_story: str
    plan_output: str
    steps: list
    generated_files: dict
    stages: list  # [{Type, Code}, ...]，按 InitMap -> InitEvent -> StartGame 顺序
    full_script: str  # 所有 stages 的 Code 拼接（兼容旧用法）


@app.get("/")
def root():
    """Serve frontend or API info."""
    from fastapi.responses import FileResponse
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"status": "ok", "app": "LUA Story Generator"}


@app.get("/npc-interaction")
def npc_interaction_redirect():
    """保留旧路径，重定向到 NPC 思考"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/npc-think", status_code=302)


@app.get("/npc-think")
def npc_think_page():
    """NPC 思考页面（NPC_Think_Begin）"""
    from fastapi.responses import FileResponse
    path = STATIC_DIR / "npc_think.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="npc_think.html not found")


@app.get("/npc-dialogue")
def npc_dialogue_page():
    """NPC 对话页面（NPC_Dialogue_Request）"""
    from fastapi.responses import FileResponse
    path = STATIC_DIR / "npc_dialogue.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="npc_dialogue.html not found")


@app.get("/npc-persuade")
def npc_persuade_page():
    """NPC 说服页面（NPC_Persuade_Request）"""
    from fastapi.responses import FileResponse
    path = STATIC_DIR / "npc_persuade.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="npc_persuade.html not found")


@app.get("/npc_persuade")
def npc_persuade_page_alias():
    """与文件名一致的下划线路径，避免误打开返回 404"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/npc-persuade", status_code=302)


@app.get("/npc_think")
def npc_think_page_alias():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/npc-think", status_code=302)


@app.get("/npc_dialogue")
def npc_dialogue_page_alias():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/npc-dialogue", status_code=302)


def _load_assets() -> dict:
    """Load assets from DataTable CSVs at startup. Fallback to assets.json if DataTable empty. Merge minigames."""
    res = load_resources()
    data = {
        "npcs": res["npcs"],
        "enemies": res["enemies"],
        "props": res["props"],
        "items": res["items"],
        "animations": res.get("animations", []),
        "minigames": res["minigames"],
        "source": res.get("source", "datatable"),
        "datatable_dir": res.get("datatable_dir", ""),
    }
    # Fallback to assets.json if DataTable returned empty (e.g. wrong path)
    if not data["npcs"] and not data["enemies"] and not data["props"]:
        if ASSETS_FILE.exists():
            try:
                fallback = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
                data["npcs"] = fallback.get("npcs", [])
                data["enemies"] = fallback.get("enemies", [])
                data["props"] = fallback.get("props", [])
                data["source"] = "fallback"
            except Exception:
                pass
        elif DEFAULT_ASSETS.exists():
            try:
                fallback = json.loads(DEFAULT_ASSETS.read_text(encoding="utf-8"))
                data["npcs"] = fallback.get("npcs", [])
                data["enemies"] = fallback.get("enemies", [])
                data["props"] = fallback.get("props", [])
                data["source"] = "fallback"
            except Exception:
                pass
    # Overlay minigames from assets.json if exists (DataTable has no minigames)
    if ASSETS_FILE.exists():
        try:
            overlay = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
            if overlay.get("minigames"):
                data["minigames"] = overlay["minigames"]
        except Exception:
            pass
    if "minigames" not in data or not data["minigames"]:
        data.setdefault("minigames", ["TTT"])
    return data


def _save_assets(data: dict) -> None:
    """Save only minigames overlay to assets.json (npcs/enemies/props/items come from DataTable)."""
    existing = {}
    if ASSETS_FILE.exists():
        try:
            existing = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["minigames"] = data.get("minigames", ["TTT"])
    with open(ASSETS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


@app.get("/api/preset-map")
def get_preset_map():
    """返回预设地图 LUA（step1+step2+step3），供前端预填 InitMap。"""
    return {"code": get_init_map_code()}


class ApiKeyUpdate(BaseModel):
    api_key: str = ""


@app.post("/api/api-key")
def save_api_key(req: ApiKeyUpdate):
    """前端保存的 API Key 同步到服务端，UE/TCP 请求缺省时使用。"""
    from runtime_api_key import set_default_api_key
    set_default_api_key(req.api_key or "")
    return {"ok": True}


@app.get("/api/assets")
def get_assets():
    """获取素材库（从 DataTable 加载，启动时读取）"""
    return _load_assets()


@app.get("/api/resources")
def get_resources():
    """获取完整资源详情（含描述等，供前端展示）"""
    res = load_resources()
    return {
        "npcs": res["npcs"],
        "enemies": res["enemies"],
        "props": res["props_detail"],
        "items": res["items_detail"],
        "animations": res.get("animations", []),
        "animations_play": res.get("animations_play", []),
        "animations_loop": res.get("animations_loop", []),
        "minigames": res["minigames"],
        "source": res["source"],
        "datatable_dir": res["datatable_dir"],
        "hint": "素材库从 DataTable CSV 加载，策划修改表格后重启服务生效",
    }


@app.post("/api/assets")
def save_assets(data: AssetsModel):
    """保存素材库（仅保存 minigames，其它从 DataTable 加载）"""
    _save_assets({"minigames": data.minigames or ["TTT"]})
    return {"ok": True}


class SendToUnrealRequest(BaseModel):
    """前端发送 LUA 到 Unreal 的请求体"""
    type: str  # InitMap | InitEvent | StartGame
    code: str | dict
    message_id: str = ""


@app.get("/api/tcp-status")
def tcp_status():
    """返回 TCP 已连接客户端数量，供前端显示通信状态。"""
    try:
        from tcp_server import get_connected_count
        return {"connected": get_connected_count()}
    except Exception:
        return {"connected": 0}


@app.get("/api/ue-messages")
def ue_messages(limit: int = 50, clear: bool = False):
    """获取 UE 端反馈消息，供前端展示。clear=true 时返回后清空队列。"""
    try:
        from tcp_server import get_ue_messages
        msgs = get_ue_messages(limit=min(limit, 200), clear=clear)
        return {"messages": msgs, "count": len(msgs)}
    except Exception:
        return {"messages": [], "count": 0}


import time
_send_dedup: dict = {}  # {(type, code): last_send_time} 用于去重

class NpcThinkRequest(BaseModel):
    """统一格式：Type + Code + AdditionalContent + MessageId。Web/UE 端通用。"""
    Type: str = Field(default="NPC_Think_Begin", validation_alias=AliasChoices("Type", "type"))
    Code: dict | None = Field(default=None, validation_alias=AliasChoices("Code", "code"))
    Additional_content: str | list | dict | None = Field(default=None, validation_alias=AliasChoices("AdditionalContent", "Additional_content"))
    Message_id: str = Field(default="", validation_alias=AliasChoices("MessageId", "message_id", "messageId"))
    api_key: str = ""


def _build_code_for_request(msg_type: str, code: dict | None, add_content) -> dict:
    """根据 Type 和 AdditionalContent 构建传给生成器的 Code。"""
    code = code if isinstance(code, dict) else {}
    if msg_type == "NPC_Dialogue_Request":
        npc_info = code.get("NPCInfo") or code.get("npc_info") or code
        npc_info = npc_info if isinstance(npc_info, dict) else {}
        current = (
            add_content if isinstance(add_content, str)
            else code.get("CurrentDialogue") or code.get("current_dialogue")
            or code.get("AdditionalContent")
            or ""
        )
        return {"NPCInfo": npc_info, "CurrentDialogue": (str(current).strip() if current else "")}
    elif msg_type == "NPC_Persuade_Request":
        npc_info = code.get("NPCInfo") or code.get("npc_info") or {}
        if not isinstance(npc_info, dict):
            npc_info = {}
        round_val = code.get("Round") or code.get("round") or npc_info.get("Round") or 0
        return {"NPCInfo": npc_info, "Round": round_val}
    else:
        npc_info = code.get("NPCInfo") or code.get("npc_info") or code
        npc_info = npc_info if isinstance(npc_info, dict) else {}
        tag_list = add_content if isinstance(add_content, list) else code.get("TagList") or code.get("tag_list") or []
        tag_list = tag_list if isinstance(tag_list, list) else []
        return {"NPCInfo": npc_info, "TagList": tag_list}


@app.post("/api/npc-interaction/generate")
def npc_interaction_generate(req: NpcThinkRequest):
    """根据 Type 分发：NPC_Think_Begin/NPC_Dialogue_Request/NPC_Persuade_Request。返回 {Type, Code, AdditionalContent, MessageId} 格式。"""
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key is required")
    msg_type = (req.Type or "").strip()
    code = _build_code_for_request(msg_type, req.Code, req.Additional_content)
    try:
        res = load_resources()
        animations = res.get("animations", [])
        if not animations:
            animations = [
                "Happy", "Frustrated", "Wave", "Scared", "Shy", "Dance",
                "Drink", "Eat", "Idle", "Sit", "Sleep", "Sing", "PickUp",
                "Dialogue", "Admiring",
            ]
        anim_play = res.get("animations_play") or []
        anim_loop = res.get("animations_loop") or []
        if msg_type == "NPC_Dialogue_Request":
            from npc_dialogue import generate_npc_dialogue_reply_lua
            lua = generate_npc_dialogue_reply_lua(
                api_key=req.api_key.strip(),
                code=code,
                animations=animations,
                animations_play=anim_play,
                animations_loop=anim_loop,
            )
            return {
                "Type": "NPC_Dialogue_Reply",
                "Code": lua,
                "AdditionalContent": "",
                "MessageId": req.Message_id or "",
                "ok": True,
                "lua": lua,
            }
        elif msg_type == "NPC_Persuade_Request":
            from npc_persuade import generate_npc_persuade_reply
            out_code = generate_npc_persuade_reply(
                api_key=req.api_key.strip(),
                code=code,
                additional_content=(req.Additional_content if isinstance(req.Additional_content, str) else ""),
                animations_play=anim_play,
                animations_loop=anim_loop,
            )
            lua = (
                out_code.get("NPCInfo", {}).get("LUA")
                if isinstance(out_code, dict) else ""
            )
            code_str = (
                json.dumps(out_code, ensure_ascii=False)
                if isinstance(out_code, dict)
                else (out_code if isinstance(out_code, str) else "")
            )
            return {
                "Type": "NPC_Persuade_Reply",
                "Code": code_str,
                "AdditionalContent": "",
                "MessageId": req.Message_id or "",
                "ok": True,
                "lua": lua,
            }
        else:
            from npc_interaction import generate_npc_think_lua
            lua = generate_npc_think_lua(
                api_key=req.api_key.strip(),
                code=code,
                animations=animations,
                animations_play=anim_play,
                animations_loop=anim_loop,
            )
            return {
                "Type": "NPC_Think_End",
                "Code": lua,
                "AdditionalContent": "",
                "MessageId": req.Message_id or "",
                "ok": True,
                "lua": lua,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/send-to-unreal")
def send_to_unreal(req: SendToUnrealRequest):
    """将 LUA 代码推送给已连接的 Unreal TCP 客户端，仅发送 { Type, Code }"""
    import sys
    code_key = req.code if isinstance(req.code, str) else json.dumps(req.code, ensure_ascii=False, sort_keys=True)
    key = (req.type, code_key)
    now = time.monotonic()
    if key in _send_dedup and (now - _send_dedup[key]) < 0.5:
        print(f"[send-to-unreal] 去重跳过 Type={req.type}", file=sys.stderr)
        from tcp_server import get_connected_count
        return {"ok": True, "sent_to": get_connected_count(), "deduped": True}
    _send_dedup[key] = now
    print(f"[send-to-unreal] Type={req.type} CodeLen={len(code_key)}", file=sys.stderr)
    from tcp_server import send_to_unreal_clients
    payload = {"Type": req.type, "Code": req.code, "AdditionalContent": "", "MessageId": req.message_id or ""}
    count = send_to_unreal_clients(payload)
    return {"ok": True, "sent_to": count}


@app.get("/models")
def get_models():
    """Return available models for each phase."""
    return {
        "story": config.STORY_MODELS,
        "planning": config.PLANNING_MODELS,
        "coding": config.CODING_MODELS,
    }


@app.post("/generate")
def generate(req: GenerateRequest):
    """Run full pipeline: story expansion -> planning -> code generation."""
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key is required")

    if not req.story_input or not req.story_input.strip():
        raise HTTPException(status_code=400, detail="Story input is required")

    if req.story_model not in config.STORY_MODELS:
        req.story_model = config.STORY_MODELS[0]
    if req.planning_model not in config.PLANNING_MODELS:
        req.planning_model = config.PLANNING_MODELS[0]
    if req.coding_model not in config.CODING_MODELS:
        req.coding_model = config.CODING_MODELS[0]

    assets = req.assets or _load_assets()
    if not assets.get("npcs") and not assets.get("enemies") and not assets.get("props") and not assets.get("items"):
        assets = _load_assets()
    if "minigames" not in assets or not assets["minigames"]:
        assets.setdefault("minigames", ["TTT"])

    try:
        result = run_full_pipeline(
            story_input=req.story_input.strip(),
            api_key=req.api_key.strip(),
            story_model=req.story_model,
            planning_model=req.planning_model,
            coding_model=req.coding_model,
            assets=assets,
            encounter_locations=req.encounter_locations,
            story_mode=req.story_mode,
            init_map_code=req.init_map_code.strip() if req.init_map_code else None,
            previous_init_event=req.previous_init_event.strip() if req.previous_init_event else None,
        )
        if req.stages_only:
            return result.get("stages", [])  # 仅返回 stages 数组，与 TCP 一致
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _start_tcp_server_thread(host: str = "127.0.0.1", port: int = 9000):
    """Start TCP server in background thread for Unreal client connection."""
    import threading
    from tcp_server import run_tcp_server

    def run():
        try:
            run_tcp_server(host=host, port=port)
        except OSError as e:
            print(f"[TCP] Failed to start: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    print(f"[TCP] Story generator TCP server running at tcp://{host}:{port}")


if __name__ == "__main__":
    import os
    import uvicorn

    # 默认同时启动 TCP 服务（供 Unreal 连接），可通过 SKIP_TCP=1 禁用
    if os.environ.get("SKIP_TCP", "").strip() != "1":
        tcp_port = int(os.environ.get("TCP_PORT", "9010"))
        _start_tcp_server_thread(port=tcp_port)

    http_port = int(os.environ.get("PORT", "9000"))
    uvicorn.run(app, host="0.0.0.0", port=http_port)
