# Unreal Engine TCP 客户端集成说明

LUA Story Generator 提供 TCP Socket 服务，Unreal 可作为客户端连接并请求生成 LUA 脚本。

## 服务端

### 启动方式

1. **HTTP + TCP 同时运行**（默认）：
   ```bash
   python main.py
   ```
   - HTTP: `http://localhost:9000`（Web 前端）
   - TCP: `tcp://127.0.0.1:9010`（UE 插件使用，与 main.py 一起启动）

2. **仅 TCP 服务**：
   ```bash
   python tcp_server.py --host 127.0.0.1 --port 9000
   ```

3. **自定义 TCP 端口**：
   ```bash
   set TCP_PORT=9100
   python main.py
   ```

4. **禁用 TCP（仅 HTTP）**：
   ```bash
   set SKIP_TCP=1
   python main.py
   ```

## 通信协议

- **编码**：UTF-8
- **格式**：JSON 行（每行一个完整 JSON，以 `\n` 结尾）
- **请求**：发送一行 JSON，以 `\n` 结束
- **响应**：接收一行 JSON，以 `\n` 结束

### 请求示例

```json
{"cmd": "generate", "story_input": "酒馆里 Alice 和老板因为两杯酒吵架，玩家帮 Alice 下棋赢老板，Alice 成为同伴", "api_key": "sk-xxx"}
```

**generate 完整参数**：

| 字段 | 必填 | 说明 |
|------|------|------|
| cmd | 是 | `"generate"` |
| story_input | 是 | 故事梗概 |
| api_key | 是 | OpenAI API Key |
| story_model | 否 | 默认 gpt-4.1 |
| planning_model | 否 | 默认 gpt-4.1 |
| coding_model | 否 | 默认 gpt-5.1-codex-max |
| assets | 否 | `{npcs:[], enemies:[], props:[], minigames:[]}` |

### 响应示例（成功）

TCP 的 `generate` 成功时**直接返回 stages 数组**，无其他字段：

```json
[
  {"Type": "InitMap", "Code": "Time.Pause()\n\n..."},
  {"Type": "InitEvent", "Code": "local function ResolveEncounterLoc()\n..."},
  {"Type": "StartGame", "Code": "World.StartGame()\nTime.Resume()\nUI.Toast(\"游戏开始\")"}
]
```

按执行顺序：InitMap → InitEvent → StartGame。

### 响应示例（失败）

```json
{"error": "API Key is required"}
```

客户端可判断：若为数组则为成功（stages）；若为对象且含 `error` 则为失败。

### 其他命令

**ping**：
```json
{"cmd": "ping"}
```
响应：`{"ok": true, "msg": "pong"}`

**get_assets**：
```json
{"cmd": "get_assets"}
```
响应：`{"ok": true, "assets": {"npcs": [...], "enemies": [...], ...}}`

**report（UE 端上报反馈，供前端展示）**：
```json
{"cmd": "report", "msg": "InitMap 执行完成", "type": "InitMap", "level": "info"}
```
| 字段 | 必填 | 说明 |
|------|------|------|
| cmd | 是 | `"report"` 或 `"ue_feedback"` |
| msg | 是 | 消息内容，将显示在前端「UE 端反馈」面板 |
| type | 否 | 来源类型，如 InitMap、InitEvent、StartGame |
| level | 否 | info / warn / error，用于颜色区分 |
| data | 否 | 附加数据（任意 JSON） |

响应：`{"ok": true, "received": true}`。前端会每 2 秒轮询并展示。

---

## Unreal C++ 示例

```cpp
// StoryGeneratorClient.h
#pragma once

#include "CoreMinimal.h"
#include "Sockets.h"
#include "SocketSubsystem.h"

class LUASTORYGENERATOR_API FStoryGeneratorClient
{
public:
    FStoryGeneratorClient();
    ~FStoryGeneratorClient();

    bool Connect(const FString& Host = TEXT("127.0.0.1"), int32 Port = 9000);
    void Disconnect();
    bool IsConnected() const { return Socket != nullptr && Socket->GetConnectionState() == SCS_Connected; }

    bool GenerateLua(const FString& StoryInput, const FString& ApiKey, FString& OutFullScript, FString& OutError);

private:
    FSocket* Socket;
    bool SendJson(const FString& Json);
    bool RecvJson(FString& OutJson);
};
```

```cpp
// StoryGeneratorClient.cpp
#include "StoryGeneratorClient.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

FStoryGeneratorClient::FStoryGeneratorClient() : Socket(nullptr) {}

FStoryGeneratorClient::~FStoryGeneratorClient()
{
    Disconnect();
}

bool FStoryGeneratorClient::Connect(const FString& Host, int32 Port)
{
    ISocketSubsystem* SSS = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if (!SSS) return false;

    TSharedRef<FInternetAddr> Addr = SSS->CreateInternetAddr();
    bool bValid;
    Addr->SetIp(*Host, bValid);
    if (!bValid) return false;
    Addr->SetPort(Port);

    Socket = SSS->CreateSocket(NAME_Stream, TEXT("StoryGenTCP"), false);
    if (!Socket) return false;

    return Socket->Connect(*Addr);
}

void FStoryGeneratorClient::Disconnect()
{
    if (Socket)
    {
        Socket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
        Socket = nullptr;
    }
}

bool FStoryGeneratorClient::SendJson(const FString& Json)
{
    if (!IsConnected()) return false;
    FString Line = Json + TEXT("\n");
    FTCHARToUTF8 Encoded(*Line);
    int32 Sent = 0;
    return Socket->Send(reinterpret_cast<const uint8*>(Encoded.Get()), Encoded.Length(), Sent);
}

bool FStoryGeneratorClient::RecvJson(FString& OutJson)
{
    if (!IsConnected()) return false;
    TArray<uint8> Buffer;
    Buffer.SetNumUninitialized(65536);
    int32 BytesRead = 0;
    if (!Socket->Recv(Buffer.GetData(), Buffer.Num(), BytesRead)) return false;
    if (BytesRead <= 0) return false;
    Buffer.SetNum(BytesRead);
    FTCHARToUTF8::UTF8ToTCHAR_Convert Convert;
    OutJson = Convert.Convert(reinterpret_cast<ANSICHAR*>(Buffer.GetData()));
    OutJson = OutJson.TrimStartAndEnd();  // 去掉尾部 \n
    return true;
}

bool FStoryGeneratorClient::GenerateLua(const FString& StoryInput, const FString& ApiKey, FString& OutFullScript, FString& OutError)
{
    TSharedPtr<FJsonObject> Req = MakeShareable(new FJsonObject);
    Req->SetStringField(TEXT("cmd"), TEXT("generate"));
    Req->SetStringField(TEXT("story_input"), StoryInput);
    Req->SetStringField(TEXT("api_key"), ApiKey);

    FString ReqStr;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&ReqStr);
    FJsonSerializer::Serialize(Req.ToSharedRef(), Writer);
    if (!SendJson(ReqStr)) { OutError = TEXT("Send failed"); return false; }
    if (!RecvJson(ReqStr)) { OutError = TEXT("Recv failed"); return false; }

    TSharedPtr<FJsonObject> Resp;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ReqStr);
    if (!FJsonSerializer::Deserialize(Reader, Resp) || !Resp.IsValid())
    {
        OutError = TEXT("Invalid response JSON");
        return false;
    }
    if (!Resp->GetBoolField(TEXT("ok")))
    {
        OutError = Resp->GetStringField(TEXT("error"));
        return false;
    }
    OutFullScript = Resp->GetStringField(TEXT("full_script"));
    return true;
}
```

---

## Unreal Blueprint 思路

若用蓝图，可借助 **Plugin: TCP Socket** 或 **SocketIO Client**，或自写蓝图节点：

1. 创建 TCP Socket，连接 `127.0.0.1:9000`
2. 将 JSON 字符串（含 `\n`）转为 UTF-8 发送
3. 接收数据直到 `\n`，解析 JSON
4. 从 `stages` 数组按顺序取出各阶段的 `Code`，根据 `Type`（InitMap/InitEvent/StartGame）分别执行或传给 Lua 执行环境

---

## 测试（命令行）

使用 `netcat` 或 PowerShell 测试：

```powershell
# PowerShell
$msg = '{"cmd":"ping"}' + "`n"
$client = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 9000)
$stream = $client.GetStream()
$bytes = [System.Text.Encoding]::UTF8.GetBytes($msg)
$stream.Write($bytes, 0, $bytes.Length)
$buffer = New-Object byte[] 1024
$read = $stream.Read($buffer, 0, 1024)
[System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
$client.Close()
```

或用 Python 客户端测试：

```python
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 9000))
s.send((json.dumps({"cmd": "ping"}) + "\n").encode("utf-8"))
print(s.recv(4096).decode("utf-8"))
s.close()
```
