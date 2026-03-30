"""
模拟 Unreal TCP 客户端，用于测试「发送到 Unreal」功能。
用法：
  1. 先启动 backend（startup.bat）
  2. 运行本脚本：python tcp_client_test.py
  3. 在网页或 Postman 中点击「发送到 Unreal」/ 调用 API
  4. 本窗口会打印收到的 JSON
"""
import json
import socket

HOST = "127.0.0.1"
PORT = 9010

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    print(f"已连接到 tcp://{HOST}:{PORT}，等待接收推送... (Ctrl+C 退出)\n")
    try:
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    obj = json.loads(line.decode("utf-8"))
                    t = obj.get("Type") or obj.get("type", "?")
                    c = obj.get("Code") or obj.get("code", "")
                    print("[收到] Type:", t, "| Code 长度:", len(c))
                    print("---")
                    print(c[:500] + ("..." if len(c) > 500 else ""))
                    print("---\n")
                except Exception as e:
                    print("[原始]", line[:200], "..." )
    except KeyboardInterrupt:
        pass
    finally:
        s.close()

if __name__ == "__main__":
    main()
