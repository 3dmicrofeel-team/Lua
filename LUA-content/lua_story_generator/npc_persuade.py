"""NPC 说服功能：根据 Type=NPC_Persuade_Request 生成说服回合回复。"""
import json
import re
from typing import Any

from openai import OpenAI

from lua_reference_loader import load_merged_lua_function_markdown
from prompts.npc_persuade import NPC_PERSUADE_PROMPT

MIN_PERSUADE_ROUNDS = 3
MAX_PERSUADE_ROUNDS = 8


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v).strip() or default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _normalize_npc_info(npc_info: dict | None) -> dict:
    if not isinstance(npc_info, dict):
        return {}
    out = dict(npc_info)
    if isinstance(out.get("Personality"), str):
        out["PersonalityText"] = out.get("Personality")
    elif isinstance(out.get("Personality"), dict):
        out["PersonalityText"] = json.dumps(out["Personality"], ensure_ascii=False)
    else:
        out["PersonalityText"] = ""
    return out


def _infer_topic_hardness(text: str) -> int:
    t = (text or "").lower()
    hard_kw = [
        "传家", "祖传", "绝不", "不会给", "誓言", "底线", "禁忌", "信条", "仇", "家族", "荣誉",
        "inherit", "heirloom", "never", "oath", "code", "taboo", "family",
    ]
    easy_kw = ["借", "帮忙", "一会", "暂时", "商量", "交易", "reward", "deal", "help"]
    score = 0
    for k in hard_kw:
        if k in t:
            score += 1
    for k in easy_kw:
        if k in t:
            score -= 1
    return _clamp(score, -2, 4)


def _compute_initial_stance(npc_info: dict) -> int:
    fav = _clamp(_to_int(npc_info.get("Favorability"), 50), 0, 100)
    topic_text = " ".join([
        _safe_str(npc_info.get("Topic")),
        _safe_str(npc_info.get("BackgroundStory")),
        _safe_str(npc_info.get("Stance")),
    ])
    hard = _infer_topic_hardness(topic_text)
    # 默认不要太难：基础偏中，难题再下调。
    stance = int(52 + (fav - 50) * 0.30 - hard * 7)
    return _clamp(stance, 28, 82)


def _player_signal(player_input: str) -> dict:
    text = _safe_str(player_input).lower()
    length = len(text)
    if not text:
        return {"quality": -6, "mode": "none"}

    emotional_kw = ["求你", "拜托", "感激", "家人", "朋友", "信任", "please", "trust", "friend"]
    rational_kw = ["因为", "所以", "理由", "逻辑", "证据", "公平", "because", "reason", "evidence"]
    threat_kw = ["不然", "后果", "威胁", "滚", "打你", "kill", "threat", "or else"]
    deceit_kw = ["骗", "谎", "假装", "保证", "promise", "lie", "fake"]

    emo = sum(1 for k in emotional_kw if k in text)
    rat = sum(1 for k in rational_kw if k in text)
    thr = sum(1 for k in threat_kw if k in text)
    dec = sum(1 for k in deceit_kw if k in text)

    if thr > max(emo, rat, dec):
        mode = "threat"
    elif dec > max(emo, rat, thr):
        mode = "deceit"
    elif rat >= emo:
        mode = "rational"
    else:
        mode = "emotional"

    quality = 0
    quality += min(8, length // 12)
    quality += 5 if rat > 0 else 0
    quality += 4 if emo > 0 else 0
    quality -= 5 if thr > 0 else 0
    quality -= 3 if dec > 0 else 0
    return {"quality": quality, "mode": mode}


def _calc_next_stance(current: int, round_num: int, npc_info: dict, player_input: str) -> int:
    signal = _player_signal(player_input)
    fav = _clamp(_to_int(npc_info.get("Favorability"), 50), 0, 100)
    moral = _clamp(_to_int(npc_info.get("MoralTendency"), 50), 0, 100)
    mode = signal["mode"]
    delta = signal["quality"]

    # 关系越好越容易推进，但幅度不宜过高，避免“总是成功”。
    delta += int((fav - 50) * 0.06)

    # 立场反馈：高立场继续推进会有衰减，低立场的负反馈也会适度削弱，避免极端滚雪球。
    delta += int((current - 50) * 0.04)
    if current >= 70 and delta > 0:
        delta -= int((current - 65) * 0.16)
    if current <= 30 and delta < 0:
        delta += int((35 - current) * 0.10)

    if mode == "threat":
        delta -= 8 if moral >= 45 else 2
    elif mode == "deceit":
        delta -= 6 if moral >= 60 else 1
    elif mode == "rational":
        delta += 4
    elif mode == "emotional":
        delta += 3

    # 给合理输入最小缓冲，但不再强制变成正收益，减少“必然被说服”。
    text = _safe_str(player_input)
    if text and len(text) >= 6 and mode in ("rational", "emotional") and delta < -2 and current < 55:
        delta = -1

    next_stance = _clamp(current + _clamp(delta, -22, 22), 0, 100)

    # 回合节奏控制：
    # - <3 回合：不直接结局，避免过快结束；
    # - 3~8 回合：逐步收敛；
    # - >=8 回合：强制成功/失败结局。
    if round_num < MIN_PERSUADE_ROUNDS:
        return _clamp(next_stance, 8, 92)

    hard = _infer_topic_hardness(" ".join([
        _safe_str(npc_info.get("Topic")),
        _safe_str(npc_info.get("BackgroundStory")),
        _safe_str(npc_info.get("Stance")),
    ]))
    # hard 越高越难成功；favorability 越高越易成功。
    success_bias = int((fav - 50) * 0.25 - hard * 5)
    if mode == "threat":
        success_bias -= 10 if moral >= 45 else 3
    elif mode == "deceit":
        success_bias -= 8 if moral >= 60 else 2
    elif mode == "rational":
        success_bias += 4
    elif mode == "emotional":
        success_bias += 2

    tendency = next_stance + success_bias

    if round_num >= MAX_PERSUADE_ROUNDS:
        return 100 if tendency >= 55 else 0

    # 3~7 回合：渐进式拉向结局，但保持可逆，不会每次都只往成功方向。
    progress = round_num - MIN_PERSUADE_ROUNDS + 1  # 1..5
    pull = 4 + progress * 2
    if tendency >= 55:
        next_stance = _clamp(next_stance + pull, 0, 100)
    elif tendency <= 45:
        next_stance = _clamp(next_stance - pull, 0, 100)
    else:
        # 中间区间保持拉扯感，防止长时间原地踏步
        jitter = 2 if mode in ("rational", "emotional") else -2
        next_stance = _clamp(next_stance + jitter, 0, 100)

    # 达到显著边界时可提前结局，但不会早于第3回合。
    if round_num >= MIN_PERSUADE_ROUNDS and next_stance >= 96:
        return 100
    if round_num >= MIN_PERSUADE_ROUNDS and next_stance <= 4:
        return 0
    return next_stance


def _tokenize_anim_name(name: str) -> set[str]:
    chunks = re.findall(r"[a-z0-9\u4e00-\u9fff]+", (name or "").lower())
    tokens: set[str] = set()
    for c in chunks:
        tokens.add(c)
        if "_" in c:
            tokens.update(x for x in c.split("_") if x)
    return tokens


def _pick_anim(
    mode: str,
    mood: str,
    hint: str,
    anim_play: list[str],
    anim_loop: list[str],
    round_num: int,
    current_stance: int,
    next_stance: int,
    player_input: str,
) -> tuple[str, str]:
    play = anim_play or []
    loop = anim_loop or []

    if not play and not loop:
        return "loop", ""

    hint_l = (hint or "").strip().lower()
    signal_mode = _player_signal(player_input).get("mode", "none")
    stance_trend = next_stance - current_stance

    core_safe_kws = {
        "talk", "dialog", "dialogue", "speak", "listen", "idle", "stand", "sit",
        "thinking", "think", "nod", "agree", "wave", "greet", "gesture", "point",
        "plead", "persuade", "convince", "discussion", "chat",
        "对话", "交谈", "说话", "思考", "点头", "同意", "招手", "站立", "坐",
    }
    danger_kws = {
        "attack", "hit", "hurt", "kill", "death", "die", "combat", "fight", "battle",
        "shoot", "cast", "skill", "spell", "rage", "run", "sprint", "jump", "roll", "dodge",
        "受击", "攻击", "死亡", "战斗", "施法", "技能", "翻滚", "冲刺", "跳",
    }
    mood_kws = {
        "positive": {"happy", "smile", "agree", "nod", "calm", "friendly", "cheer", "高兴", "微笑", "认可"},
        "neutral": {"idle", "talk", "dialogue", "thinking", "stand", "对话", "思考", "平静"},
        "negative": {"angry", "frustrated", "reject", "refuse", "disagree", "冷漠", "拒绝", "不耐烦"},
    }
    signal_kws = {
        "rational": {"think", "thinking", "explain", "talk", "point", "思考", "解释", "交流"},
        "emotional": {"plead", "comfort", "calm", "trust", "gesture", "安抚", "恳求", "共情"},
        "threat": {"warn", "angry", "reject", "shake", "警告", "愤怒", "拒绝"},
        "deceit": {"sneak", "side", "smirk", "sly", "狡猾", "试探"},
    }

    # 立场越高，动作应更积极；越低，动作可更冷淡，但仍避免战斗行为。
    trend_bonus_kws: set[str] = set()
    if stance_trend >= 12 or next_stance >= 70:
        trend_bonus_kws |= {"agree", "nod", "friendly", "smile", "高兴", "认可"}
    elif stance_trend <= -12 or next_stance <= 30:
        trend_bonus_kws |= {"reject", "refuse", "frustrated", "冷漠", "拒绝"}

    preferred_by_mode = {"play": 2, "loop": 2}
    if mode == "play":
        preferred_by_mode["loop"] = 0
    else:
        preferred_by_mode["play"] = 0

    def score_candidate(cand_mode: str, anim_name: str) -> int:
        name_l = (anim_name or "").lower()
        tokens = _tokenize_anim_name(anim_name)
        score = 0

        score += preferred_by_mode.get(cand_mode, 0)
        if hint_l and hint_l in name_l:
            score += 10

        if any(kw in name_l or kw in tokens for kw in core_safe_kws):
            score += 6
        if any(kw in name_l or kw in tokens for kw in mood_kws.get(mood, set())):
            score += 4
        if any(kw in name_l or kw in tokens for kw in signal_kws.get(signal_mode, set())):
            score += 3
        if any(kw in name_l or kw in tokens for kw in trend_bonus_kws):
            score += 2
        if round_num >= 5 and ("idle" in name_l or "站立" in name_l):
            score -= 1
        if any(kw in name_l or kw in tokens for kw in danger_kws):
            score -= 12
        return score

    all_candidates: list[tuple[str, str, int]] = []
    for a in play:
        all_candidates.append(("play", a, score_candidate("play", a)))
    for a in loop:
        all_candidates.append(("loop", a, score_candidate("loop", a)))

    best_mode = ""
    best_name = ""
    best_score = -10_000
    for m, n, s in all_candidates:
        if s > best_score:
            best_mode, best_name, best_score = m, n, s

    if best_name and best_score > -8:
        return best_mode, best_name

    # 最后的保底：优先找非战斗、偏对话/待机动作。
    for m, pool in (("loop", loop), ("play", play)):
        for n in pool:
            name_l = n.lower()
            if not any(k in name_l for k in danger_kws):
                if any(k in name_l for k in ("talk", "dialog", "idle", "thinking", "对话", "思考", "站立")):
                    return m, n
    for m, pool in (("loop", loop), ("play", play)):
        for n in pool:
            name_l = n.lower()
            if not any(k in name_l for k in danger_kws):
                return m, n
    if loop:
        return "loop", loop[0]
    if play:
        return "play", play[0]
    return "loop", ""


def _extract_json_blob(text: str) -> dict:
    s = (text or "").strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def _fallback_options(is_ending: bool, success: bool) -> dict:
    if is_ending and success:
        return {
            "Option1": "谢谢你愿意相信我。",
            "Option2": "我会兑现承诺，不辜负你的决定。",
            "Option3": "你现在反悔也来不及了。",
            "Option4": "其实我早就认识你的家人。",
        }
    if is_ending and not success:
        return {
            "Option1": "抱歉，是我太冒失了。",
            "Option2": "我尊重你的决定，我们改天再谈。",
            "Option3": "你会为今天的拒绝后悔。",
            "Option4": "其实我只是来试探你。",
        }
    return {
        "Option1": "我是真心请求你帮我一次。",
        "Option2": "你看，这么做对你也有好处。",
        "Option3": "如果你拒绝，后果你承担得起吗？",
        "Option4": "其实这件事别人早就同意了。",
    }


def generate_npc_persuade_reply(
    api_key: str,
    code: dict | None = None,
    additional_content: str | None = None,
    animations_play: list[str] | None = None,
    animations_loop: list[str] | None = None,
) -> dict:
    """生成说服回合结果，返回 Code.NPCInfo 结构。"""
    code = code if isinstance(code, dict) else {}
    npc_info = _normalize_npc_info(code.get("NPCInfo") if isinstance(code.get("NPCInfo"), dict) else code)
    round_num = _to_int(code.get("Round") or code.get("round"), 0)
    player_input = _safe_str(additional_content or "")

    input_stance_raw = code.get("Stance")
    if input_stance_raw is None:
        input_stance_raw = npc_info.get("Stance")
        
    parsed_stance = None
    if input_stance_raw is not None:
        try:
            val = float(input_stance_raw)
            if 0.0 <= val <= 1.0 and (isinstance(input_stance_raw, float) or val < 1.0 or val == 0.0 or val == 1.0):
                parsed_stance = int(val * 100)
            else:
                parsed_stance = int(val)
        except (ValueError, TypeError):
            pass
            
    if parsed_stance is None:
        parsed_stance = _compute_initial_stance(npc_info)
        
    current_stance = _clamp(parsed_stance, 0, 100)

    if round_num <= 0:
        next_stance = current_stance
    else:
        next_stance = _calc_next_stance(current_stance, round_num, npc_info, player_input)

    is_ending = next_stance in (0, 100)
    success = next_stance == 100

    anim_play = animations_play or []
    anim_loop = animations_loop or []
    lua_ref = load_merged_lua_function_markdown() or "（未加载 Lua_Function 文档）"

    prompt = NPC_PERSUADE_PROMPT.format(
        npc_info_json=json.dumps(npc_info, ensure_ascii=False, indent=2),
        round_val=round_num,
        player_input=player_input or "（空）",
        current_stance=current_stance,
        next_stance_candidate=next_stance,
        anim_play_str=", ".join(anim_play[:80]) or "（无）",
        anim_loop_str=", ".join(anim_loop[:120]) or "（无）",
        lua_reference=lua_ref[:12000],
    )

    line = ""
    mood = "neutral"
    anim_mode = "loop"
    anim_name_hint = ""
    options = _fallback_options(is_ending=is_ending, success=success)

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (resp.choices[0].message.content or "").strip()
        obj = _extract_json_blob(raw)
        if isinstance(obj, dict):
            line = _safe_str(obj.get("line"))
            mood = _safe_str(obj.get("mood"), "neutral").lower()
            if mood not in ("positive", "neutral", "negative"):
                mood = "neutral"
            anim_mode = _safe_str(obj.get("anim_mode"), "loop").lower()
            if anim_mode not in ("play", "loop"):
                anim_mode = "loop"
            anim_name_hint = _safe_str(obj.get("anim_name"))
            opt1 = _safe_str(obj.get("Option1"))
            opt2 = _safe_str(obj.get("Option2"))
            opt3 = _safe_str(obj.get("Option3"))
            opt4 = _safe_str(obj.get("Option4"))
            if opt1 and opt2 and opt3 and opt4:
                options = {
                    "Option1": opt1,
                    "Option2": opt2,
                    "Option3": opt3,
                    "Option4": opt4,
                }
    except Exception:
        pass

    if not line:
        if round_num == 0:
            line = "这件事没你想得那么简单。先说说你为什么非要这样做。"
        elif is_ending and success:
            line = "好吧，我被你说服了。这件事就按你说的办。"
        elif is_ending and not success:
            line = "够了，我不会再让步。到此为止。"
        else:
            line = "你的话我听进去了，但我还需要更多理由。"

    chosen_mode, chosen_anim = _pick_anim(
        anim_mode,
        mood,
        anim_name_hint,
        anim_play=anim_play,
        anim_loop=anim_loop,
        round_num=round_num,
        current_stance=current_stance,
        next_stance=next_stance,
        player_input=player_input,
    )
    line_escaped = line.replace("\\", "\\\\").replace('"', '\\"')
    topic_escaped = _safe_str(npc_info.get("Topic")).replace("\\", "\\\\").replace('"', '\\"')
    stance_float = next_stance / 100.0

    opt1_escaped = _safe_str(options.get("Option1")).replace("\\", "\\\\").replace('"', '\\"')
    opt2_escaped = _safe_str(options.get("Option2")).replace("\\", "\\\\").replace('"', '\\"')
    opt3_escaped = _safe_str(options.get("Option3")).replace("\\", "\\\\").replace('"', '\\"')
    opt4_escaped = _safe_str(options.get("Option4")).replace("\\", "\\\\").replace('"', '\\"')
    lua_options = f'{{"{opt1_escaped}", "{opt2_escaped}", "{opt3_escaped}", "{opt4_escaped}"}}'

    lua_lines = []
    if chosen_anim:
        if chosen_mode == "play":
            lua_lines.append(f'_self_:PlayAnim("{chosen_anim}")')
        else:
            lua_lines.append(f'_self_:PlayAnimLoop("{chosen_anim}", 1.5)')
            
    lua_lines.append(f'_self_:SayWithPersuadebox("{line_escaped}", "{topic_escaped}", {stance_float:.2f}, {lua_options})')
    lua_code = "\n".join(lua_lines)

    return {
        "NPCInfo": {
            "LUA": lua_code,
            "Stance": stance_float,
            "Response": {
                "Option1": _safe_str(options.get("Option1")),
                "Option2": _safe_str(options.get("Option2")),
                "Option3": _safe_str(options.get("Option3")),
                "Option4": _safe_str(options.get("Option4")),
            },
        }
    }
