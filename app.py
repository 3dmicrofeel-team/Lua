from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from openai import OpenAI
import re
from collections import deque

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

CONFIG_FILE = "config.json"

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_client(api_config):
    """创建OpenAI客户端"""
    api_key = api_config.get("api_key", "")
    base_url = api_config.get("base_url", "")
    model = api_config.get("model", "gpt-4")
    
    if not api_key:
        raise ValueError("API密钥未配置，请在API配置页面设置API密钥")
    
    try:
        # OpenAI SDK 初始化 - 只传递支持的参数
        import os
        # 清除可能影响初始化的环境变量
        env_backup = {}
        problematic_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
        for var in problematic_vars:
            if var in os.environ:
                env_backup[var] = os.environ.pop(var)
        
        try:
            # 使用最简单的初始化方式
            if base_url:
                client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                client = OpenAI(api_key=api_key)
            return client
        finally:
            # 恢复环境变量
            for var, value in env_backup.items():
                os.environ[var] = value
    except TypeError as e:
        # 如果还是失败，尝试最基础的方式
        try:
            return OpenAI(api_key=api_key)
        except Exception as e2:
            raise ValueError(f"无法创建OpenAI客户端: {str(e2)}")
    except Exception as e:
        raise ValueError(f"无法创建OpenAI客户端: {str(e)}")

def extract_json_from_response(text):
    """从响应中提取JSON"""
    if not text:
        return {}
    
    # 尝试找到JSON代码块
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    # 尝试找到第一个{到最后一个}之间的内容
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 如果JSON不完整，尝试修复常见的截断问题
            # 检查是否在字符串中间截断
            if e.pos and e.pos < len(json_str):
                # 尝试找到最后一个完整的键值对
                try:
                    # 移除最后一个不完整的部分
                    last_comma = json_str.rfind(',', 0, e.pos)
                    last_brace = json_str.rfind('}', 0, e.pos)
                    if last_comma > last_brace:
                        # 尝试移除最后一个不完整的键值对
                        fixed_json = json_str[:last_comma] + '\n}'
                        return json.loads(fixed_json)
                    elif last_brace > 0:
                        # 尝试直接关闭JSON
                        fixed_json = json_str[:last_brace+1]
                        return json.loads(fixed_json)
                except:
                    pass
    
    # 如果都失败了，尝试直接解析整个文本
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 返回原始文本和错误信息，但尝试提取部分JSON
        error_info = {
            "raw": text,
            "error": "Failed to parse JSON",
            "error_position": e.pos if hasattr(e, 'pos') else None,
            "error_message": str(e)
        }
        # 如果文本很长，只保存前1000个字符
        if len(text) > 1000:
            error_info["raw_preview"] = text[:1000] + "..."
        return error_info

def call_gpt_module(module_name, prompt, config, system_prompt=None):
    """调用GPT模块"""
    if module_name not in config.get("modules", {}):
        raise ValueError(f"模块 {module_name} 不存在于配置中")
    
    module_config = config["modules"][module_name]
    api_config = config.get("api_config", {})
    
    if not api_config:
        raise ValueError("api_config 配置不存在")
    
    try:
        client = get_client(api_config)
    except Exception as e:
        raise ValueError(f"无法创建API客户端: {str(e)}")
    
    response_format = {"type": "json_object"} if module_config.get("json_mode") else None
    
    # 优先使用模块特定的模型，否则使用全局模型
    model = module_config.get("model") or api_config.get("model", "gpt-4")
    
    # 直接使用用户指定的模型，不进行自动映射
    
    # 使用自定义system prompt或默认值
    if system_prompt is None:
        system_prompt = "你是一个专业的Lua游戏脚本生成助手。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    # 检查是否为 codex 模型（使用 responses API）
    codex_models = ["gpt-5.1-codex", "gpt-5.2-pro"]
    is_codex_model = model in codex_models or "codex" in model.lower()
    
    if is_codex_model:
        # 使用 responses.create API for codex models
        # 将 system + user messages 合并为单个 input
        full_prompt = prompt  # prompt 已经包含了完整的内容
        
        # 构建 responses API 参数
        responses_params = {
            "model": model,
            "input": full_prompt,
        }
        
        # 添加 reasoning 参数（codex 模型支持）
        reasoning_effort = module_config.get("reasoning_effort", "high")
        responses_params["reasoning"] = {"effort": reasoning_effort}
        
        # 注意：codex 模型不支持 temperature 参数，所以不添加
        
        try:
            response = client.responses.create(**responses_params)
            result = response.output_text
            
            # 如果是JSON模式，尝试解析
            if module_config.get("json_mode"):
                result = extract_json_from_response(result)
            
            return result
        except AttributeError:
            # 如果 responses API 不存在，尝试使用 chat API
            raise ValueError(f"模型 '{model}' 需要使用 responses API，但当前 SDK 版本可能不支持。\n请确保使用最新版本的 OpenAI SDK (>=1.12.0)。")
        except Exception as e:
            error_msg = str(e)
            if "responses" in error_msg.lower() or "attribute" in error_msg.lower():
                raise ValueError(f"模型 '{model}' 需要使用 responses API，但当前 SDK 版本可能不支持。\n请确保使用最新版本的 OpenAI SDK (>=1.12.0)。\n错误: {error_msg}")
            raise ValueError(f"Codex 模型 '{model}' 调用失败: {error_msg}")
    else:
        # 使用标准的 chat.completions API
        # 检查模型是否支持 max_tokens 参数
        # gpt-5.1 系列模型不支持 max_tokens 参数
        models_without_maxtokens = ["gpt-5.1", "gpt-5.2", "gpt-5.2-chat-latest", "gpt-5-mini"]
        use_maxtokens = model not in models_without_maxtokens
        
        # 构建API调用参数
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": module_config.get("temperature", 0.5),
        }
        
        # 只在支持的模型上添加 max_tokens
        if use_maxtokens:
            api_params["max_tokens"] = module_config.get("max_tokens", 2000)
        
        # 只在支持的模型上添加 response_format
        # 注意：某些新模型可能不支持 response_format，如果失败会在异常处理中重试
        if response_format:
            api_params["response_format"] = response_format
        
        try:
            response = client.chat.completions.create(**api_params)
        except Exception as e:
            error_msg = str(e)
            
            # 处理不支持 max_tokens 的情况，重试不带该参数
            if "max_tokens" in error_msg.lower() and "not supported" in error_msg.lower():
                try:
                    api_params_no_maxtokens = {k: v for k, v in api_params.items() if k != "max_tokens"}
                    if "response_format" in api_params_no_maxtokens:
                        del api_params_no_maxtokens["response_format"]
                    response = client.chat.completions.create(**api_params_no_maxtokens)
                except Exception as e2:
                    raise ValueError(f"模型 '{model}' 调用失败: {str(e2)}")
            
            # 处理非聊天模型错误
            elif "not a chat model" in error_msg.lower() or "404" in error_msg:
                raise ValueError(f"模型 '{model}' 不是聊天模型，无法用于对话API。\n错误: {error_msg}\n提示：codex/pro 模型需要使用 responses API。")
            
            # 处理模型不存在或无效
            elif "model" in error_msg.lower() or "invalid" in error_msg.lower():
                raise ValueError(f"模型 '{model}' 不可用。错误: {error_msg}\n提示：请检查模型名称是否正确。")
            
            # 处理API认证错误
            elif "api" in error_msg.lower() or "key" in error_msg.lower() or "auth" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                raise ValueError(f"API认证失败: {error_msg}\n请检查API密钥是否正确。")
            
            # 其他错误
            else:
                raise ValueError(f"API调用失败: {error_msg}")
        
        result = response.choices[0].message.content
    
    # 如果是JSON模式，尝试解析
    if module_config.get("json_mode"):
        result = extract_json_from_response(result)
    
    return result

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = load_config()
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    data = request.json
    config = load_config()
    
    if "api_config" in data:
        config["api_config"] = {**config.get("api_config", {}), **data["api_config"]}
    
    if "modules" in data:
        if "modules" not in config:
            config["modules"] = {}
        for module_name, module_data in data["modules"].items():
            if module_name in config["modules"]:
                config["modules"][module_name].update(module_data)
            else:
                config["modules"][module_name] = module_data
    
    save_config(config)
    return jsonify({"success": True, "config": config})

@app.route('/api/generate', methods=['POST'])
def generate_lua():
    """生成Lua代码的主流程"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
            
        user_input = data.get("user_input", "")
        
        if not user_input:
            return jsonify({"error": "用户输入不能为空"}), 400
        
        config = load_config()
        
        if not config:
            return jsonify({"error": "配置文件不存在或为空"}), 500
        
        if "modules" not in config:
            return jsonify({"error": "配置文件中缺少modules配置"}), 500
        
        if "api_config" not in config:
            return jsonify({"error": "配置文件中缺少api_config配置"}), 500
        
        api_key = config.get("api_config", {}).get("api_key", "")
        if not api_key:
            return jsonify({"error": "请先配置API密钥"}), 400
        
        # 验证所有必需的模块是否存在
        required_modules = ["screenwriter", "stage_design", "stage_programmer", 
                          "casting_design", "character_config", "executive_director"]
        missing_modules = [m for m in required_modules if m not in config.get("modules", {})]
        if missing_modules:
            return jsonify({"error": f"缺少必需的模块配置: {', '.join(missing_modules)}"}), 500
        
        # 验证每个模块是否有prompt_template
        for module_name in required_modules:
            module_config = config["modules"][module_name]
            if "prompt_template" not in module_config:
                return jsonify({"error": f"模块 {module_name} 缺少 prompt_template"}), 500
    
    except KeyError as e:
        return jsonify({"error": f"配置错误: 缺少必需的配置项 {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"配置加载失败: {str(e)}"}), 500
    
    try:
        results = {}
        
        # 1. 编剧模块
        print("开始编剧模块...")
        try:
            screenwriter_prompt = config["modules"]["screenwriter"]["prompt_template"].format(
                user_input=user_input
            )
        except KeyError as e:
            raise ValueError(f"编剧模块prompt模板格式错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"编剧模块prompt模板处理失败: {str(e)}")
        
        blueprint = call_gpt_module("screenwriter", screenwriter_prompt, config)
        results["blueprint"] = blueprint
        print("编剧模块完成")
        
        blueprint_str = json.dumps(blueprint, ensure_ascii=False) if isinstance(blueprint, dict) else str(blueprint)
        
        # 2. 场务设计模块
        print("开始场务设计模块...")
        stage_design_prompt = config["modules"]["stage_design"]["prompt_template"].format(
            blueprint=blueprint_str
        )
        stage_design = call_gpt_module("stage_design", stage_design_prompt, config)
        results["stage_design"] = stage_design
        print("场务设计模块完成")
        
        stage_design_str = json.dumps(stage_design, ensure_ascii=False) if isinstance(stage_design, dict) else str(stage_design)
        
        # 3. 场务程序模块
        print("开始场务程序模块...")
        stage_programmer_prompt = config["modules"]["stage_programmer"]["prompt_template"].format(
            stage_design=stage_design_str
        )
        stage_lua = call_gpt_module("stage_programmer", stage_programmer_prompt, config)
        results["stage_lua"] = stage_lua
        print("场务程序模块完成")
        
        # 4. 选角设计模块
        print("开始选角设计模块...")
        casting_design_prompt = config["modules"]["casting_design"]["prompt_template"].format(
            blueprint=blueprint_str,
            stage_design=stage_design_str
        )
        casting_design = call_gpt_module("casting_design", casting_design_prompt, config)
        results["casting_design"] = casting_design
        print("选角设计模块完成")
        
        casting_design_str = json.dumps(casting_design, ensure_ascii=False) if isinstance(casting_design, dict) else str(casting_design)
        
        # 5. 角色配置程序模块
        print("开始角色配置程序模块...")
        character_config_prompt = config["modules"]["character_config"]["prompt_template"].format(
            casting_design=casting_design_str
        )
        cast_lua = call_gpt_module("character_config", character_config_prompt, config)
        results["cast_lua"] = cast_lua
        print("角色配置程序模块完成")
        
        # 6. 执行导演模块
        print("开始执行导演模块...")
        executive_director_prompt = config["modules"]["executive_director"]["prompt_template"].format(
            blueprint=blueprint_str,
            stage_lua=stage_lua if isinstance(stage_lua, str) else json.dumps(stage_lua, ensure_ascii=False),
            cast_lua=cast_lua if isinstance(cast_lua, str) else json.dumps(cast_lua, ensure_ascii=False)
        )
        main_lua = call_gpt_module("executive_director", executive_director_prompt, config)
        results["main_lua"] = main_lua
        print("执行导演模块完成")
        
        # 自动保存生成的 Lua 文件
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        saved_files = {}
        
        # 保存 stage_lua
        if isinstance(stage_lua, str) and stage_lua.strip():
            stage_file = os.path.join(output_dir, "Stage.lua")
            with open(stage_file, 'w', encoding='utf-8') as f:
                f.write(stage_lua)
            saved_files["Stage.lua"] = stage_file
            print(f"已保存: {stage_file}")
        
        # 保存 cast_lua
        if isinstance(cast_lua, str) and cast_lua.strip():
            cast_file = os.path.join(output_dir, "Cast.lua")
            with open(cast_file, 'w', encoding='utf-8') as f:
                f.write(cast_lua)
            saved_files["Cast.lua"] = cast_file
            print(f"已保存: {cast_file}")
        
        # 保存 main_lua
        if isinstance(main_lua, str) and main_lua.strip():
            main_file = os.path.join(output_dir, "main.lua")
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(main_lua)
            saved_files["main.lua"] = main_file
            print(f"已保存: {main_file}")
        
        return jsonify({
            "success": True,
            "results": results,
            "saved_files": saved_files,
            "output_dir": output_dir
        })
        
    except ValueError as e:
        # 业务逻辑错误，返回友好的错误信息
        import traceback
        error_trace = traceback.format_exc()
        print(f"业务错误：\n{error_trace}")
        return jsonify({
            "error": str(e),
            "error_type": "ValueError"
        }), 500
    except Exception as e:
        # 其他未预期的错误
        import traceback
        error_trace = traceback.format_exc()
        print(f"未预期的错误：\n{error_trace}")
        return jsonify({
            "error": f"服务器内部错误: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": error_trace if app.debug else None
        }), 500

@app.route('/api/modules', methods=['GET'])
def get_modules():
    """获取所有模块的prompt模板"""
    config = load_config()
    modules = {}
    for name, module_config in config.get("modules", {}).items():
        modules[name] = {
            "name": module_config.get("name", name),
            "model": module_config.get("model", ""),
            "prompt_template": module_config.get("prompt_template", ""),
            "temperature": module_config.get("temperature", 0.5),
            "max_tokens": module_config.get("max_tokens", 2000),
            "json_mode": module_config.get("json_mode", False)
        }
    return jsonify(modules)

@app.route('/api/modules/<module_name>', methods=['POST'])
def update_module(module_name):
    """更新特定模块的配置"""
    data = request.json
    config = load_config()
    
    if "modules" not in config:
        config["modules"] = {}
    if module_name not in config["modules"]:
        config["modules"][module_name] = {}
    
    config["modules"][module_name].update(data)
    save_config(config)
    
    return jsonify({"success": True, "module": config["modules"][module_name]})

@app.route('/')
def index():
    """返回首页"""
    return app.send_static_file('index.html')

@app.route('/favicon.ico')
def favicon():
    """处理favicon请求"""
    return '', 204

@app.route('/api/download/<filename>')
def download_file(filename):
    """下载生成的文件"""
    output_dir = "output"
    file_path = os.path.join(output_dir, filename)
    
    if os.path.exists(file_path) and filename.endswith('.lua'):
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        return jsonify({"error": "文件不存在"}), 404

@app.route('/api/files')
def list_files():
    """列出所有生成的文件"""
    output_dir = "output"
    files = []
    
    if os.path.exists(output_dir):
        for filename in sorted(os.listdir(output_dir)):
            if filename.endswith('.lua'):
                file_path = os.path.join(output_dir, filename)
                file_size = os.path.getsize(file_path)
                files.append({
                    "name": filename,
                    "size": file_size,
                    "path": f"/api/download/{filename}"
                })
    
    return jsonify({"files": files})

def validate_layout(intent_data, draft_layout):
    """
    验证ASCII布局是否符合要求（Python实现，不调用LLM）
    返回: (is_valid, errors, validated_layout)
    """
    errors = []
    
    if not isinstance(draft_layout, dict):
        return False, [{"code": "invalid_format", "detail": "布局格式无效"}], None
    
    grid_meta = draft_layout.get("grid_meta", {})
    grid_ascii = draft_layout.get("grid_ascii", [])
    entities = draft_layout.get("entities", {})
    
    width = grid_meta.get("width", 0)
    height = grid_meta.get("height", 0)
    
    # 验证1: grid_ascii长度必须等于height
    if len(grid_ascii) != height:
        errors.append({"code": "dimension_mismatch", "detail": f"grid_ascii长度({len(grid_ascii)})不等于height({height})"})
        return False, errors, None
    
    # 验证2: 每行长度必须等于width
    for i, row in enumerate(grid_ascii):
        if len(row) != width:
            errors.append({"code": "row_length_mismatch", "detail": f"第{i}行长度({len(row)})不等于width({width})"})
            return False, errors, None
    
    # 验证3: 只允许特定字符
    allowed_chars = set('. #SCEND')
    for i, row in enumerate(grid_ascii):
        for j, char in enumerate(row):
            if char not in allowed_chars:
                errors.append({"code": "illegal_char", "detail": f"位置({j},{i})包含非法字符: '{char}'"})
                return False, errors, None
    
    # 验证4: 必须恰好有一个'S'
    s_count = sum(row.count('S') for row in grid_ascii)
    if s_count != 1:
        errors.append({"code": "player_start_count", "detail": f"玩家起始位置'S'的数量({s_count})不等于1"})
        return False, errors, None
    
    # 验证5: 统计ASCII中的实体数量
    ascii_counts = {
        'enemy': sum(row.count('E') for row in grid_ascii),
        'npc': sum(row.count('N') for row in grid_ascii),
        'chest': sum(row.count('C') for row in grid_ascii),
        'door': sum(row.count('D') for row in grid_ascii)
    }
    
    # 验证6: 实体数量必须匹配intent中的要求
    intent_counts = intent_data.get("counts", {})
    for entity_type in ['enemy', 'npc', 'chest', 'door']:
        expected = intent_counts.get(entity_type, 0)
        actual = ascii_counts.get(entity_type, 0)
        if actual != expected:
            errors.append({"code": "count_mismatch", "detail": f"{entity_type}数量不匹配: 期望{expected}, 实际{actual}"})
            return False, errors, None
    
    # 验证7: 实体坐标必须匹配ASCII中的符号
    player_start = entities.get("player_start", {})
    if player_start:
        px, py = player_start.get("x", -1), player_start.get("y", -1)
        if py < len(grid_ascii) and px < len(grid_ascii[py]) and grid_ascii[py][px] != 'S':
            errors.append({"code": "player_start_mismatch", "detail": f"玩家起始位置({px},{py})在ASCII中不是'S'"})
            return False, errors, None
    
    # 验证门、宝箱、敌人、NPC的坐标
    for door in entities.get("doors", []):
        dx, dy = door.get("x", -1), door.get("y", -1)
        if dy < len(grid_ascii) and dx < len(grid_ascii[dy]) and grid_ascii[dy][dx] != 'D':
            errors.append({"code": "door_mismatch", "detail": f"门位置({dx},{dy})在ASCII中不是'D'"})
            return False, errors, None
    
    for chest in entities.get("chests", []):
        cx, cy = chest.get("x", -1), chest.get("y", -1)
        if cy < len(grid_ascii) and cx < len(grid_ascii[cy]) and grid_ascii[cy][cx] != 'C':
            errors.append({"code": "chest_mismatch", "detail": f"宝箱位置({cx},{cy})在ASCII中不是'C'"})
            return False, errors, None
    
    for enemy in entities.get("enemies", []):
        ex, ey = enemy.get("x", -1), enemy.get("y", -1)
        if ey < len(grid_ascii) and ex < len(grid_ascii[ey]) and grid_ascii[ey][ex] != 'E':
            errors.append({"code": "enemy_mismatch", "detail": f"敌人位置({ex},{ey})在ASCII中不是'E'"})
            return False, errors, None
    
    for npc in entities.get("npcs", []):
        nx, ny = npc.get("x", -1), npc.get("y", -1)
        if ny < len(grid_ascii) and nx < len(grid_ascii[ny]) and grid_ascii[ny][nx] != 'N':
            errors.append({"code": "npc_mismatch", "detail": f"NPC位置({nx},{ny})在ASCII中不是'N'"})
            return False, errors, None
    
    # 验证8: 如果存在门，玩家必须能到达至少一个门（简单的BFS可达性检查）
    if len(entities.get("doors", [])) > 0:
        if not check_reachability(grid_ascii, player_start, entities.get("doors", [])):
            errors.append({"code": "unreachable_door", "detail": "玩家无法到达任何门"})
            return False, errors, None
    
    # 所有验证通过
    return True, [], draft_layout

def check_reachability(grid_ascii, start_pos, doors):
    """检查玩家是否能到达至少一个门（BFS）"""
    if not start_pos or not doors:
        return True
    
    height = len(grid_ascii)
    if height == 0:
        return False
    
    width = len(grid_ascii[0])
    sx, sy = start_pos.get("x", -1), start_pos.get("y", -1)
    
    if sx < 0 or sy < 0 or sx >= width or sy >= height:
        return False
    
    # 可行走字符
    walkable = set('. S C E N D')
    
    # BFS
    visited = set()
    queue = deque([(sx, sy)])
    visited.add((sx, sy))
    
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    
    while queue:
        x, y = queue.popleft()
        
        # 检查是否到达任何门
        for door in doors:
            dx, dy = door.get("x", -1), door.get("y", -1)
            if (x, y) == (dx, dy):
                return True
        
        # 探索四个方向
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                if (nx, ny) not in visited:
                    char = grid_ascii[ny][nx]
                    if char in walkable:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
    
    return False

def ascii_to_lua(validated_layout, environment_lua=""):
    """
    将ASCII布局直接转换为Lua代码（Python实现，不调用LLM）
    """
    grid_meta = validated_layout.get("grid_meta", {})
    grid_ascii = validated_layout.get("grid_ascii", [])
    entities = validated_layout.get("entities", {})
    
    width = grid_meta.get("width", 0)
    height = grid_meta.get("height", 0)
    
    lua_lines = []
    
    # 分配block
    lua_lines.append(f"local block = Env.AllocBlock({width}, {height}, 0, 0)")
    lua_lines.append("")
    
    # 逐行处理ASCII网格
    for y in range(height):
        row = grid_ascii[y]
        for x in range(width):
            char = row[x]
            
            if char == '#':
                # 墙
                lua_lines.append(f'Env.PlaceItem(block, "Wall_Stone", {x}, {y})')
            elif char == 'S':
                # 玩家起始位置（注意：这里只是标记位置，实际玩家生成可能需要其他API）
                # 根据entities中的player_start信息
                lua_lines.append(f'-- Player start at ({x}, {y})')
            elif char == 'D':
                # 门（使用Wall_Stone）
                lua_lines.append(f'Env.PlaceItem(block, "Wall_Stone", {x}, {y})')
            elif char == 'C':
                # 宝箱（使用Grave_Stone）
                lua_lines.append(f'Env.PlaceItem(block, "Grave_Stone", {x}, {y})')
            elif char == 'E':
                # 敌人
                lua_lines.append(f'Env.SpawnNPC(block, "Skeleton_Warrior", {x}, {y}, "Enemy")')
            elif char == 'N':
                # NPC
                lua_lines.append(f'Env.SpawnNPC(block, "Ghost_Nun", {x}, {y}, "Neutral")')
            # '.' 字符跳过，不需要生成代码
    
    # 合并环境Lua代码
    final_lua = "\n".join(lua_lines)
    if environment_lua:
        final_lua = environment_lua + "\n\n" + final_lua
    
    return final_lua

@app.route('/api/generate-level', methods=['POST'])
def generate_level():
    """生成关卡Lua代码的主流程"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
            
        user_input = data.get("user_input", "")
        use_intent_parser = data.get("use_intent_parser", True)
        
        if not user_input:
            return jsonify({"error": "用户输入不能为空"}), 400
        
        config = load_config()
        
        if not config:
            return jsonify({"error": "配置文件不存在或为空"}), 500
        
        if "api_config" not in config:
            return jsonify({"error": "配置文件中缺少api_config配置"}), 500
        
        api_key = config.get("api_config", {}).get("api_key", "")
        if not api_key:
            return jsonify({"error": "请先配置API密钥"}), 400
        
        # 验证必需的模块是否存在（只需要grid_planner，layout_guard/lua_builder/lua_validator用Python实现）
        required_modules = ["grid_planner"]
        if use_intent_parser:
            required_modules.insert(0, "intent_parser")
        
        missing_modules = [m for m in required_modules if m not in config.get("modules", {})]
        if missing_modules:
            return jsonify({"error": f"缺少必需的模块配置: {', '.join(missing_modules)}"}), 500
    
    except KeyError as e:
        return jsonify({"error": f"配置错误: 缺少必需的配置项 {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"配置加载失败: {str(e)}"}), 500
    
    try:
        results = {}
        
        # Module 0: Intent Parser (可选)
        intent_data = None
        if use_intent_parser:
            print("开始Intent Parser模块...")
            try:
                intent_parser_config = config["modules"]["intent_parser"]
                intent_prompt = intent_parser_config.get("prompt_template", "").format(
                    user_input=user_input
                )
                if not intent_prompt:
                    # 如果没有prompt_template，使用默认prompt
                    intent_prompt = f"""System:
You are a level requirement parser.
Your task is to convert the user's natural language description into structured level constraints.
You also need to generate environment-related Lua code (non-ASCII content).
Do NOT generate any map or ASCII grid.

Developer:
Output MUST be strict JSON. Do not include explanations or markdown.
Use exactly the following structure:

{{
  "language": "zh" | "en",
  "theme": "string",
  "grid": {{
    "width": int,
    "height": int,
    "meters_per_char": number
  }},
  "counts": {{
    "enemy": int,
    "npc": int,
    "chest": int,
    "door": int
  }},
  "constraints": {{
    "must_have_path_to_door": bool,
    "chest_on_side_path": bool,
    "difficulty": "easy" | "medium" | "hard",
    "notes": ["string"]
  }},
  "environment_lua": "string"
}}

The environment_lua field should contain Lua code for:
- Env.SetEnvironment("WeatherID", "TimeID")
- Any other non-ASCII-grid-related setup code
- Use appropriate weather and time based on theme and difficulty
- Weather options: "Clear", "Foggy", "Rain", "Storm"
- Time options: "Day", "Night", "Dawn", "Dusk"
- Output ONLY pure Lua code, NO markdown blocks, NO comments

Default rules:
- If size is not specified: width=20, height=12, meters_per_char=1
- If counts are not specified: generate random values:
  * enemy = random integer from 0 to 4 (inclusive)
  * npc = random integer from 0 to 3 (inclusive)
  * chest = random integer from 0 to 3 (inclusive)
  * door = random integer from 0 to 3 (inclusive)
- must_have_path_to_door defaults to true when door > 0
- chest_on_side_path defaults to true when chest > 0
- Detect language automatically from user input
- IMPORTANT: Each time you generate counts, use different random values to add variety
- For environment_lua: generate appropriate Env.SetEnvironment() call based on theme

User:
{user_input}"""
                
                intent_data = call_gpt_module("intent_parser", intent_prompt, config)
                results["intent"] = intent_data
                print("Intent Parser模块完成")
            except Exception as e:
                print(f"Intent Parser模块失败: {str(e)}")
                # Intent Parser是可选的，失败时继续使用默认值
                intent_data = {
                    "language": "zh",
                    "theme": "default",
                    "grid": {"width": 20, "height": 12, "meters_per_char": 1},
                    "counts": {"enemy": 2, "npc": 1, "chest": 1, "door": 1},
                    "constraints": {
                        "must_have_path_to_door": True,
                        "chest_on_side_path": True,
                        "difficulty": "medium",
                        "notes": []
                    },
                    "environment_lua": 'Env.SetEnvironment("Foggy", "Night")'
                }
                results["intent"] = intent_data
        
        # 如果没有intent_data，创建默认值
        if intent_data is None:
            intent_data = {
                "language": "zh",
                "theme": "default",
                "grid": {"width": 20, "height": 12, "meters_per_char": 1},
                "counts": {"enemy": 2, "npc": 1, "chest": 1, "door": 1},
                "constraints": {
                    "must_have_path_to_door": True,
                    "chest_on_side_path": True,
                    "difficulty": "medium",
                    "notes": []
                },
                "environment_lua": 'Env.SetEnvironment("Foggy", "Night")'
            }
        
        # 提取环境Lua代码
        environment_lua = intent_data.get("environment_lua", "")
        if not environment_lua:
            # 如果没有，根据theme和difficulty生成默认值
            theme = intent_data.get("theme", "default").lower()
            difficulty = intent_data.get("constraints", {}).get("difficulty", "medium")
            
            # 根据主题选择天气和时间
            if "墓地" in theme or "墓" in theme or "grave" in theme:
                weather, time = "Foggy", "Night"
            elif "地牢" in theme or "dungeon" in theme:
                weather, time = "Rain", "Night"
            else:
                weather, time = "Foggy", "Night"
            
            environment_lua = f'Env.SetEnvironment("{weather}", "{time}")'
        
        intent_str = json.dumps(intent_data, ensure_ascii=False)
        
        # Module 1: Grid Planner
        print("开始Grid Planner模块...")
        grid_planner_config = config["modules"]["grid_planner"]
        grid_planner_prompt = grid_planner_config.get("prompt_template", "").format(
            intent=intent_str
        )
        if not grid_planner_prompt:
            grid_planner_prompt = f"""System:
You are a top-down RPG level layout designer.
Your task is to design an ASCII grid layout and entity coordinates.
Do NOT generate Lua code.

Developer:
Output MUST be strict JSON. Do not include explanations or markdown.
Use exactly the following structure:

{{
  "grid_meta": {{
    "width": int,
    "height": int,
    "meters_per_char": number,
    "origin": "top_left_(0,0)"
  }},
  "grid_ascii": ["string"],
  "entities": {{
    "player_start": {{"x": int, "y": int}},
    "doors": [{{"x": int, "y": int}}],
    "chests": [{{"x": int, "y": int}}],
    "enemies": [{{"x": int, "y": int, "type": "Skeleton_Warrior"}}],
    "npcs": [{{"x": int, "y": int, "type": "Ghost_Nun"}}]
  }},
  "design_notes": ["string"]
}}

Hard rules:
1. grid_ascii length must equal height
2. each row length must equal width
3. allowed characters only: . # S C E N D
4. exactly ONE 'S'
5. symbol counts must match counts in intent
6. entity coordinates must match symbols in grid_ascii

Design goals:
- Main path should be clear
- Chest should be on a side path if possible
- Respect difficulty and notes from intent

design_notes:
- max 3 short bullet-style sentences

User:
{{
  "intent": {intent_str}
}}"""
        
        # Module 1: Grid Planner (带重试机制)
        max_retries = 3
        validated_layout = None
        validation_errors = []
        
        for attempt in range(max_retries):
            print(f"开始Grid Planner模块 (尝试 {attempt + 1}/{max_retries})...")
            draft_layout = call_gpt_module("grid_planner", grid_planner_prompt, config)
            results["draft_layout"] = draft_layout
            print("Grid Planner模块完成")
            
            # Module 1.5: LayoutGuard (Python验证)
            print("开始LayoutGuard模块 (Python验证)...")
            is_valid, errors, validated_layout = validate_layout(intent_data, draft_layout)
            
            if is_valid:
                print("LayoutGuard验证通过")
                results["validated_result"] = {
                    "status": "valid",
                    "errors": [],
                    "layout": validated_layout
                }
                break
            else:
                validation_errors = errors
                print(f"LayoutGuard验证失败: {errors}")
                results["validated_result"] = {
                    "status": "invalid",
                    "errors": errors,
                    "layout": draft_layout
                }
                if attempt < max_retries - 1:
                    print(f"验证失败，将重新调用Grid Planner...")
                else:
                    print(f"已达到最大重试次数，使用最后一次生成的布局")
                    validated_layout = draft_layout  # 使用最后一次的布局，即使验证失败
        
        if validated_layout is None:
            return jsonify({"error": "无法生成有效的布局"}), 500
        
        # Module 2: ASCII转Lua (Python转换，不再使用LLM)
        print("开始ASCII转Lua转换 (Python实现)...")
        level_lua = ascii_to_lua(validated_layout, environment_lua)
        results["level_lua"] = level_lua
        print("ASCII转Lua转换完成")
        
        final_lua = level_lua
        
        # 自动保存生成的 Lua 文件
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        saved_files = {}
        
        # 保存最终验证后的 level_lua
        if isinstance(final_lua, str) and final_lua.strip():
            level_file = os.path.join(output_dir, "Level.lua")
            with open(level_file, 'w', encoding='utf-8') as f:
                f.write(final_lua)
            saved_files["Level.lua"] = level_file
            print(f"已保存: {level_file}")
        
        return jsonify({
            "success": True,
            "results": results,
            "saved_files": saved_files,
            "output_dir": output_dir
        })
        
    except ValueError as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"业务错误：\n{error_trace}")
        return jsonify({
            "error": str(e),
            "error_type": "ValueError"
        }), 500
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"未预期的错误：\n{error_trace}")
        return jsonify({
            "error": f"服务器内部错误: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": error_trace if app.debug else None
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

