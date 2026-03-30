"""Simple TCP client to test LUA Story Generator socket server."""
import json
import socket
import sys


def tcp_request(host: str = "127.0.0.1", port: int = 9000, req: dict | None = None) -> dict:
    """Send JSON request, receive JSON response."""
    req = req or {"cmd": "ping"}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30.0)
    try:
        sock.connect((host, port))
        out = json.dumps(req, ensure_ascii=False) + "\n"
        sock.sendall(out.encode("utf-8"))
        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                line = data.split(b"\n", 1)[0].decode("utf-8")
                return json.loads(line)
        return {"ok": False, "error": "No response"}
    finally:
        sock.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000

    # Ping test
    r = tcp_request(port=port, req={"cmd": "ping"})
    print("Ping:", json.dumps(r, ensure_ascii=False, indent=2))

    # Generate test (requires API key in env)
    import os
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        r = tcp_request(port=port, req={
            "cmd": "generate",
            "story_input": "酒馆门口一个老人请玩家下棋，赢了得剑。",
            "api_key": api_key,
        })
        print("Generate ok:", r.get("ok"))
        if r.get("ok") and r.get("full_script"):
            print("Script length:", len(r["full_script"]))
    else:
        print("Set OPENAI_API_KEY to test generate.")
