from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from openai import OpenAI
import re

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
        
        # 验证必需的模块是否存在
        required_modules = ["grid_planner", "layout_guard", "lua_builder", "lua_validator"]
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
Do NOT generate any map, ASCII grid, or Lua code.

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
  }}
}}

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
                    }
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
                }
            }
        
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
        
        draft_layout = call_gpt_module("grid_planner", grid_planner_prompt, config)
        results["draft_layout"] = draft_layout
        print("Grid Planner模块完成")
        
        draft_layout_str = json.dumps(draft_layout, ensure_ascii=False)
        
        # Module 1.5: LayoutGuard
        print("开始LayoutGuard模块...")
        layout_guard_config = config["modules"]["layout_guard"]
        layout_guard_prompt = layout_guard_config.get("prompt_template", "").format(
            intent=intent_str,
            draft_layout=draft_layout_str
        )
        if not layout_guard_prompt:
            layout_guard_prompt = f"""System:
You are LayoutGuard, a layout validation and auto-fix module.
Your job is to ensure the layout is fully valid.
If the input layout is already valid, return it unchanged.
If any issue exists, fix it with minimal changes and return the corrected layout.
Do NOT output any extra text.

Developer:
Output MUST be strict JSON.
Use exactly the following structure:

{{
  "status": "unchanged" | "fixed",
  "errors": [
    {{"code": "string", "detail": "string"}}
  ],
  "fixes": [
    {{"action": "string", "detail": "string"}}
  ],
  "layout": {{
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
}}

Hard constraints (MUST ALL PASS):
1. grid_ascii dimensions must match grid_meta
2. only allowed characters: . # S C E N D
3. exactly ONE 'S'
4. entity coordinates must exactly match symbols in grid_ascii (bidirectional)
5. if doors exist: S must be able to reach at least one D
   - walkable: . S C E N D N
   - blocked: #

Fix rules:
- Prefer minimal changes
- Fix order:
  (1) dimensions / illegal chars
  (2) unique S
  (3) grid ↔ entities mismatch
  (4) reachability (carve minimal path through '#')
  (5) count mismatch (last resort)
- design_notes: max 3 short sentences

User:
{{
  "intent": {intent_str},
  "draft_layout": {draft_layout_str}
}}"""
        
        validated_result = call_gpt_module("layout_guard", layout_guard_prompt, config)
        results["validated_result"] = validated_result
        print("LayoutGuard模块完成")
        
        # 提取validated_layout
        validated_layout = validated_result.get("layout", draft_layout) if isinstance(validated_result, dict) else draft_layout
        validated_layout_str = json.dumps(validated_layout, ensure_ascii=False)
        
        # Module 2: Lua Builder
        print("开始Lua Builder模块...")
        lua_builder_config = config["modules"]["lua_builder"]
        
        # 获取语言和environment设置
        language = intent_data.get("language", "zh")
        environment = {
            "weather": "Foggy",
            "time": "Night"
        }
        
        lua_builder_prompt = lua_builder_config.get("prompt_template", "").format(
            language=language,
            validated_layout=validated_layout_str,
            environment=json.dumps(environment, ensure_ascii=False)
        )
        if not lua_builder_prompt:
            lua_builder_prompt = f"""System:
You are a Lead Level Designer generating Lua scripts for a top-down RPG.
Convert a validated level layout into Lua code.
Strictly use the provided API only.

Developer:
You may ONLY use the following API functions:

- block = Env.AllocBlock(Width, Height, X_Index, Y_Index)
- Env.PlaceItem(block, "AssetID", LocalX, LocalY)
- Env.SpawnNPC(block, "NpcID", LocalX, LocalY, "TeamTag")
- Env.SetEnvironment("WeatherID", "TimeID")
- World.AddTrigger(TargetActor, "InteractPress", Radius, LuaCode)

Asset whitelist:
Props: Well_Dry, Tree_Dead, Grave_Stone, Wall_Stone
NPCs: Ghost_Nun, Skeleton_Warrior

CONVERSION METHOD - LINE BY LINE:
You MUST convert the ASCII grid line by line, character by character:
1. Start with row Y=0 (first line of grid_ascii)
2. For each row, process from left to right (X=0 to width-1)
3. For each character in the row:
   - '#' → Env.PlaceItem(block, "Wall_Stone", X, Y)
   - 'S' → player_start (note position, spawn player at X, Y)
   - 'D' → Env.PlaceItem(block, "Wall_Stone", X, Y)  (door is Wall_Stone)
   - 'C' → Env.PlaceItem(block, "Grave_Stone", X, Y)  (chest)
   - 'E' → Env.SpawnNPC(block, "Skeleton_Warrior", X, Y, "Enemy")
   - 'N' → Env.SpawnNPC(block, "Ghost_Nun", X, Y, "Neutral")
   - '.' → skip (empty/walkable space)
4. Move to next row (Y+1) and repeat
5. This ensures every character is processed exactly once

Output rules:
1. Output ONLY pure Lua code - NO markdown code blocks (no ```lua or ```)
2. Start directly with Lua code, DO NOT wrap in markdown
3. ALWAYS allocate blocks first, then place items / spawn NPCs
4. Process grid_ascii line by line, character by character
5. Coordinates: X=column index (0 to width-1), Y=row index (0 to height-1)
6. Language rule:
   - Chinese input → Chinese comments
   - English input → English comments

Implementation conventions:
- Use ONE block covering the entire grid:
  Width = grid_meta.width
  Height = grid_meta.height
  X_Index = 0, Y_Index = 0
- Process grid_ascii array line by line:
  for Y = 0 to height-1:
    row = grid_ascii[Y]
    for X = 0 to width-1:
      char = row[X]
      convert char to appropriate Lua command
- Enemies → TeamTag = "Enemy"
- NPCs → TeamTag = "Neutral"
- CRITICAL: Process EVERY character in EVERY row - do not skip any
- The line-by-line approach ensures 100% accuracy and completeness

User:
{{
  "language": "{language}",
  "validated_layout": {validated_layout_str},
  "environment": {json.dumps(environment, ensure_ascii=False)}
}}"""
        
        level_lua = call_gpt_module("lua_builder", lua_builder_prompt, config)
        results["level_lua"] = level_lua
        print("Lua Builder模块完成")
        
        # 提取Lua代码（如果被包装在代码块中）
        if isinstance(level_lua, str):
            # 尝试提取lua代码块
            lua_match = re.search(r'```(?:lua)?\s*(.*?)\s*```', level_lua, re.DOTALL)
            if lua_match:
                level_lua = lua_match.group(1)
        
        # Module 2.5: Lua Validator (验证Lua代码与ASCII地图的一致性)
        print("开始Lua Validator模块...")
        lua_validator_config = config["modules"]["lua_validator"]
        
        level_lua_str = level_lua if isinstance(level_lua, str) else json.dumps(level_lua, ensure_ascii=False)
        
        lua_validator_prompt = lua_validator_config.get("prompt_template", "").format(
            validated_layout=validated_layout_str,
            lua_code=json.dumps(level_lua_str, ensure_ascii=False)
        )
        if not lua_validator_prompt:
            lua_validator_prompt = f"""System:
You are a Lua Code Validator and Fixer for level generation.
Your task is to verify that the generated Lua code correctly implements the ASCII grid layout.
If there are inconsistencies, you must fix the Lua code to match the ASCII grid exactly.

Developer:
You will receive:
1. A validated ASCII grid layout with entity positions
2. The generated Lua code

VALIDATION METHOD - LINE BY LINE:
You MUST verify line by line, character by character:
1. Extract grid_ascii array from validated_layout
2. For each row Y (0 to height-1):
   - Get the row string: row = grid_ascii[Y]
   - For each column X (0 to width-1):
     - Get character: char = row[X]
     - Check if Lua code has the correct placement for (X, Y)
     - Verify mapping:
       * '#' → must have Env.PlaceItem(block, "Wall_Stone", X, Y)
       * 'S' → must have player_start at (X, Y)
       * 'D' → must have Env.PlaceItem(block, "Wall_Stone", X, Y)
       * 'C' → must have Env.PlaceItem(block, "Grave_Stone", X, Y)
       * 'E' → must have Env.SpawnNPC(block, "Skeleton_Warrior", X, Y, "Enemy")
       * 'N' → must have Env.SpawnNPC(block, "Ghost_Nun", X, Y, "Neutral")
       * '.' → should NOT have any placement
3. If any character is missing or incorrect, fix it
4. If code is correct, return it unchanged

Mapping rules:
- ASCII '#' = wall positions (MUST use Env.PlaceItem with Wall_Stone) - ALL '#' characters must be placed
- ASCII 'S' = player_start position
- ASCII 'D' = door positions (use Env.PlaceItem with Wall_Stone)
- ASCII 'C' = chest positions (use Env.PlaceItem with Grave_Stone)
- ASCII 'E' = enemy positions (use Env.SpawnNPC with Skeleton_Warrior, TeamTag="Enemy")
- ASCII 'N' = NPC positions (use Env.SpawnNPC with Ghost_Nun, TeamTag="Neutral")
- ASCII '.' = empty/walkable space (no placement needed)
- ASCII '.' = empty/walkable space (no placement needed)

CRITICAL REQUIREMENTS:
- Output ONLY pure Lua code - NO markdown code blocks (no ```lua or ```)
- Start directly with Lua code, DO NOT wrap in markdown
- NO explanations or comments about what you changed
- NO JSON output
- Use line-by-line conversion: process grid_ascii row by row, character by character
- If code is correct, return it unchanged
- If code needs fixes, regenerate using line-by-line approach:
  for Y = 0 to height-1:
    row = grid_ascii[Y]
    for X = 0 to width-1:
      char = row[X]
      generate appropriate Lua command for char at (X, Y)
- Ensure ALL entities from ASCII grid are placed in Lua code (including ALL walls marked as '#')
- Ensure ALL '#' characters in ASCII grid have corresponding Env.PlaceItem(block, "Wall_Stone", X, Y) calls
- Ensure NO extra entities are placed that don't exist in ASCII grid
- Coordinate system: X=column index (0 to width-1), Y=row index (0 to height-1)
- The line-by-line approach ensures every character is checked and converted correctly

User:
{{
  "validated_layout": {validated_layout_str},
  "lua_code": {json.dumps(level_lua_str, ensure_ascii=False)}
}}

Analyze the Lua code and ASCII grid. If they match, return the Lua code unchanged. If they don't match, return the corrected Lua code that exactly matches the ASCII grid."""
        
        validated_lua = call_gpt_module("lua_validator", lua_validator_prompt, config)
        results["validated_lua"] = validated_lua
        print("Lua Validator模块完成")
        
        # 提取验证后的Lua代码（如果被包装在代码块中）
        if isinstance(validated_lua, str):
            # 尝试提取lua代码块
            lua_match = re.search(r'```(?:lua)?\s*(.*?)\s*```', validated_lua, re.DOTALL)
            if lua_match:
                validated_lua = lua_match.group(1)
        
        # 使用验证后的Lua代码（如果验证模块返回了结果）
        final_lua = validated_lua if (validated_lua and isinstance(validated_lua, str) and validated_lua.strip()) else level_lua
        
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

