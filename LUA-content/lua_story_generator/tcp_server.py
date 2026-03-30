"""
TCP Socket Server for LUA Story Generator.
Unreal Engine connects as TCP client to send story input and receive LUA script.

Protocol: JSON lines (each message = one JSON line, UTF-8).
Request:  {"cmd": "generate", "story_input": "...", "api_key": "...", ...}
Response: {"ok": true, "full_script": "...", "expanded_story": "...", ...}
"""
import json
import socket
import threading
from pathlib import Path

import config
from orchestrator import run_full_pipeline

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
ASSETS_FILE = Path(__file__).parent / "assets.json"

# 已连接的 Unreal 客户端，用于前端「发送」时推送
_connected_clients: set = set()
_clients_lock = threading.Lock()

# UE 端反馈消息队列，供前端展示
_ue_messages: list = []
_ue_messages_lock = threading.Lock()
_UE_MESSAGES_MAX = 200
DEFAULT_ASSETS = Path(__file__).parent / "assets_default.json"


def get_connected_count() -> int:
    """返回当前连接的 TCP 客户端数量。"""
    with _clients_lock:
        return len(_connected_clients)


def push_ue_message(msg: dict) -> None:
    """存入 UE 端发来的反馈消息，供前端拉取。"""
    import time
    entry = {"ts": time.time(), "time": time.strftime("%H:%M:%S", time.localtime()), **msg}
    with _ue_messages_lock:
        _ue_messages.append(entry)
        while len(_ue_messages) > _UE_MESSAGES_MAX:
            _ue_messages.pop(0)


def get_ue_messages(limit: int = 50, clear: bool = False) -> list:
    """获取 UE 端反馈消息列表，可选的 clear 会在返回后清空。"""
    with _ue_messages_lock:
        out = list(_ue_messages[-limit:]) if _ue_messages else []
        if clear:
            _ue_messages.clear()
    return out


def send_to_unreal_clients(obj: dict) -> int:
    """向前端已连接的 Unreal 客户端推送 JSON 消息，返回成功发送的客户端数量。"""
    msg = json.dumps(obj, ensure_ascii=False) + "\n"
    payload = msg.encode("utf-8")
    with _clients_lock:
        clients = list(_connected_clients)
    count = 0
    for conn in clients:
        try:
            conn.sendall(payload)
            count += 1
        except (BrokenPipeError, ConnectionResetError, OSError):
            with _clients_lock:
                _connected_clients.discard(conn)
    return count


def _load_assets() -> dict:
    """Use same asset loading as main.py (DataTable or fallback)."""
    try:
        from datatable_loader import get_assets_for_agents
        return get_assets_for_agents()
    except ImportError:
        pass
    data = {"npcs": [], "enemies": [], "props": [], "items": [], "minigames": ["TTT"]}
    if ASSETS_FILE.exists():
        try:
            data = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    elif DEFAULT_ASSETS.exists():
        try:
            data = json.loads(DEFAULT_ASSETS.read_text(encoding="utf-8"))
        except Exception:
            pass
    if "minigames" not in data or not data["minigames"]:
        data.setdefault("minigames", ["TTT"])
    return data


def _handle_request(raw: str) -> dict:
    """Parse JSON request and execute, return response dict."""
    try:
        req = json.loads(raw)
    except json.JSONDecodeError as e:
        # Log first 200 chars for debugging (avoid full content in case of API key)
        preview = repr(raw[:200]) if len(raw) > 200 else repr(raw)
        import sys
        print(f"[TCP] JSON parse error: {e}", file=sys.stderr)
        print(f"[TCP] Raw preview (repr): {preview}", file=sys.stderr)
        return {"ok": False, "error": f"Invalid JSON: {e}"}

    cmd = req.get("cmd") or req.get("action") or req.get("Type") or req.get("type")
    if not cmd:
        return {"ok": False, "error": "Missing 'cmd'、'action' or 'Type' field"}

    if cmd == "generate":
        story_input = req.get("story_input") or req.get("content", "")
        api_key = req.get("api_key", "")
        if not api_key or not str(api_key).strip():
            return {"ok": False, "error": "API Key is required"}
        if not story_input or not str(story_input).strip():
            return {"ok": False, "error": "Story input is required"}

        story_model = req.get("story_model") or config.STORY_MODELS[0]
        planning_model = req.get("planning_model") or config.PLANNING_MODELS[0]
        coding_model = req.get("coding_model") or config.CODING_MODELS[0]
        if story_model not in config.STORY_MODELS:
            story_model = config.STORY_MODELS[0]
        if planning_model not in config.PLANNING_MODELS:
            planning_model = config.PLANNING_MODELS[0]
        if coding_model not in config.CODING_MODELS:
            coding_model = config.CODING_MODELS[0]

        assets = req.get("assets") or _load_assets()
        if "minigames" not in assets or not assets["minigames"]:
            assets.setdefault("minigames", ["TTT"])

        try:
            result = run_full_pipeline(
                story_input=str(story_input or "").strip(),
                api_key=str(api_key).strip(),
                story_model=story_model,
                planning_model=planning_model,
                coding_model=coding_model,
                assets=assets,
            )
            # 返回完整结果供 UE 使用（stages + full_script）
            return {
                "ok": True,
                "stages": result.get("stages", []),
                "full_script": result.get("full_script", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif cmd == "ping" or cmd == "health":
        return {"ok": True, "msg": "pong"}

    # 统一格式：Type + Code + AdditionalContent + MessageId
    # Request:
    #   {"Type":"NPC_Think_Begin"/"NPC_Dialogue_Request"/"NPC_Persuade_Request",
    #    "Code":{...},
    #    "AdditionalContent": TagList(Think) | CurrentDialogue(Dialogue) | PlayerInput(Persuade),
    #    "MessageId":"..."}
    # Response:
    #   Think/Dialogue: {"Type":"NPC_Think_End"/"NPC_Dialogue_Reply", "Code":"<lua>", ...}
    #   Persuade: {"Type":"NPC_Persuade_Reply", "Code":"<json string of {NPCInfo:{LUA,Stance,Response}}>", ...}
    msg_type = req.get("Type") or req.get("type") or cmd
    message_id = (
        req.get("MessageId")
        or req.get("message_id")
        or req.get("messageId")
        or ""
    )
    api_key = (req.get("api_key") or req.get("apiKey") or "").strip()
    if not api_key:
        try:
            from runtime_api_key import get_default_api_key
            api_key = get_default_api_key()
        except ImportError:
            api_key = None
    if not api_key:
        api_key = None
    code = req.get("Code") or req.get("code")
    add_content = req.get("AdditionalContent") or req.get("Additional_content")

    def _ensure_dict(obj):
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, str) and obj.strip():
            try:
                parsed = json.loads(obj)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                pass
        return {}

    def _ensure_str(obj):
        return (str(obj).strip() if obj is not None else "") or ""

    def _ensure_int(obj, default=0):
        try:
            return int(float(obj))
        except (TypeError, ValueError):
            return default

    if msg_type == "NPC_Dialogue_Request":
        if not api_key:
            return {"ok": False, "error": "API Key is required"}
        code = _ensure_dict(code)
        npc_info = code.get("NPCInfo") or code.get("npc_info") or code
        if not isinstance(npc_info, dict):
            npc_info = code if isinstance(code, dict) else {}
        current_dialogue = (
            add_content if isinstance(add_content, str)
            else code.get("CurrentDialogue") or code.get("current_dialogue")
            or code.get("AdditionalContent")
            or ""
        )
        code = {"NPCInfo": npc_info, "CurrentDialogue": _ensure_str(current_dialogue) if current_dialogue else ""}
        push_ue_message({
            "msg": "收到对话请求，可去 NPC 对话 页面查看",
            "type": "dialogue",
            "data": {"Type": "NPC_Dialogue_Request", "Code": code, "MessageId": message_id},
        })
        try:
            from datatable_loader import load_resources
            res = load_resources()
            animations = res.get("animations", [])
            if not animations:
                animations = ["Happy", "Frustrated", "Wave", "Drink", "Eat", "Idle", "Sit", "Dance", "Shy", "Dialogue"]
            anim_play = res.get("animations_play") or []
            anim_loop = res.get("animations_loop") or []
            from npc_dialogue import generate_npc_dialogue_reply_lua
            lua = generate_npc_dialogue_reply_lua(
                api_key=api_key, code=code, animations=animations,
                animations_play=anim_play,
                animations_loop=anim_loop,
            )
            return {
                "Type": "NPC_Dialogue_Reply",
                "Code": lua,
                "AdditionalContent": "",
                "MessageId": message_id,
                "ok": True,
                "lua": lua,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif msg_type == "NPC_Persuade_Request":
        if not api_key:
            return {"ok": False, "error": "API Key is required"}
        code = _ensure_dict(code)
        npc_info = code.get("NPCInfo") or code.get("npc_info") or {}
        if not isinstance(npc_info, dict):
            npc_info = {}
        round_val = _ensure_int(code.get("Round") or code.get("round") or npc_info.get("Round"), 0)
        code = {"NPCInfo": npc_info, "Round": round_val}
        push_ue_message({
            "msg": "收到说服请求，可去 NPC 说服 页面查看",
            "type": "persuade",
            "data": {"Type": "NPC_Persuade_Request", "Code": code, "AdditionalContent": _ensure_str(add_content), "MessageId": message_id},
        })
        try:
            from datatable_loader import load_resources
            res = load_resources()
            anim_play = res.get("animations_play", [])
            anim_loop = res.get("animations_loop", [])
            from npc_persuade import generate_npc_persuade_reply
            out_code = generate_npc_persuade_reply(
                api_key=api_key,
                code=code,
                additional_content=_ensure_str(add_content),
                animations_play=anim_play,
                animations_loop=anim_loop,
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
                "MessageId": message_id,
                "ok": True,
                "lua": (out_code.get("NPCInfo", {}).get("LUA") if isinstance(out_code, dict) else ""),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif msg_type == "NPC_Think_Begin" or cmd in ("npc_interaction", "npc-interaction", "npc_think"):
        if not api_key:
            return {"ok": False, "error": "API Key is required"}
        code = _ensure_dict(code)
        npc_info = code.get("NPCInfo") or code.get("npc_info") or code
        if not isinstance(npc_info, dict):
            npc_info = code if isinstance(code, dict) else {}
        tag_list = add_content if isinstance(add_content, list) else code.get("TagList") or code.get("tag_list") or []
        if not isinstance(tag_list, list):
            tag_list = [{"UID": req.get("PropTag") or req.get("prop_tag") or "", "Tags": [req.get("PropTag") or req.get("prop_tag")] or []}]
        code = {"NPCInfo": npc_info, "TagList": tag_list}
        push_ue_message({
            "msg": "收到思考请求，可去 NPC 思考 页面查看",
            "type": "thinking",
            "data": {"Type": "NPC_Think_Begin", "Code": code, "MessageId": message_id},
        })
        try:
            from datatable_loader import load_resources
            res = load_resources()
            animations = res.get("animations", [])
            if not animations:
                animations = ["Happy", "Frustrated", "Wave", "Drink", "Eat", "Idle", "Sit", "Dance", "Shy", "Dialogue"]
            anim_play = res.get("animations_play", [])
            anim_loop = res.get("animations_loop", [])
            from npc_interaction import generate_npc_think_lua
            lua = generate_npc_think_lua(
                api_key=api_key, code=code, animations=animations,
                animations_play=anim_play,
                animations_loop=anim_loop,
            )
            return {
                "Type": "NPC_Think_End",
                "Code": lua,
                "AdditionalContent": "",
                "MessageId": message_id,
                "ok": True,
                "lua": lua,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif cmd == "report" or cmd == "ue_feedback" or cmd == "feedback":
        # UE 端主动上报信息，存入队列供前端展示
        push_ue_message({
            "msg": req.get("msg") or req.get("message") or req.get("content", "(无内容)"),
            "type": req.get("type") or req.get("source", ""),
            "data": req.get("data"),
            "level": req.get("level", "info"),
        })
        return {"ok": True, "received": True}

    elif cmd == "get_assets":
        return {"ok": True, "assets": _load_assets()}

    else:
        return {"ok": False, "error": f"Unknown command: {cmd}"}


def _read_line(conn: socket.socket, buf_size: int = 65536) -> str | None:
    """Read until newline (\\n). Returns None on disconnect. Handles UTF-8, BOM, UTF-16."""
    data = b""
    while True:
        chunk = conn.recv(buf_size)
        if not chunk:
            return None
        data += chunk
        if b"\n" in data:
            line, _ = data.split(b"\n", 1)
            raw = line.strip()
            if not raw:
                return ""
            # Strip UTF-8 BOM
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]
            # UE on Windows may send UTF-16 LE; detect via 0x00 after '{'
            if len(raw) >= 2 and raw[0:1] == b"{" and raw[1:2] == b"\x00":
                try:
                    return raw.decode("utf-16-le", errors="replace").strip()
                except Exception:
                    pass
            return raw.decode("utf-8", errors="replace").strip()


def _handle_client(conn: socket.socket):
    """Handle one client connection (request-response loop)."""
    with _clients_lock:
        _connected_clients.add(conn)
    try:
        while True:
            line = _read_line(conn)
            if line is None:
                break
            if not line:
                continue
            resp = _handle_request(line)
            out = json.dumps(resp, ensure_ascii=False) + "\n"
            conn.sendall(out.encode("utf-8"))
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        with _clients_lock:
            _connected_clients.discard(conn)
        try:
            conn.close()
        except OSError:
            pass


def run_tcp_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Run TCP server (blocking)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    print(f"[TCP] LUA Story Generator listening on tcp://{host}:{port}")

    while True:
        conn, addr = sock.accept()
        t = threading.Thread(target=_handle_client, args=(conn,), daemon=True)
        t.start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run_tcp_server(args.host, args.port)
