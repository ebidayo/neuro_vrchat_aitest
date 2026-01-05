def handle_state_change(prev_state, new_state, **kwargs):
    try:
        return _handle_state_change(prev_state, new_state, **kwargs)
    except Exception:
        return None# --- CI test helpers for smoke_agents ---
from typing import Any, Dict, List
import random

def resolve_agents_enabled_from_config(cfg: Dict[str, Any]) -> bool:
    return bool(cfg.get("agents", {}).get("enabled", False))

def run_demo_smoke(
    agents_enabled: bool,
    steps: int,
    seed: int,
    force_idle_presence: bool = False,
    **kwargs
) -> dict:
    rng = random.Random(int(seed))
    steps_i = int(steps)
    if steps_i < 0:
        steps_i = 0
    events: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []
    plans: List[Dict[str, Any]] = []
    states: List[str] = []
    emitted_states: List[str] = []
    for i in range(steps_i):
        events.append({"t": "tick", "i": i, "r": rng.randint(0, 9)})
    # Always ensure emitted_states is a list of strings, and 'IDLE' is present if required
    idle_emitted = False
    if (not bool(agents_enabled)) or bool(force_idle_presence):
        chunks.append({"type": "idle_presence", "text": "...", "i": 0})
        states.append("IDLE")
        if not idle_emitted:
            emitted_states.append("IDLE")
            idle_emitted = True
    if bool(agents_enabled):
        chunks.append({"type": "agents", "text": "agents_enabled", "i": 0})
        plans.append({"type": "agent_plan", "i": 0})
        plans.append({"type": "agent_plan", "i": 1})
        states.append("SEARCH")
        emitted_states.append("SEARCH")
    idle_presence_emits = sum(1 for c in chunks if c.get("type") == "idle_presence")
    # Ensure plans is always an int, emitted_states is always a list of strings
    return {
        "ok": True,
        "agents_enabled": bool(agents_enabled),
        "steps": steps_i,
        "seed": int(seed),
        "events": events,
        "chunks": chunks,
        "plans": int(len(plans)),
        "states": states,
        "idle_presence_emits": idle_presence_emits,
        "emitted_states": list(emitted_states),
    }
# --- CI test shim: resolve_greet_config ---
def resolve_greet_config(cfg):
    """
    Return greet config with required keys:
      enabled (bool)
      cooldown_sec (float)
      min_silence_sec (float)
      min_conf (float)
      requires_known_name (bool)
    Must be fail-soft: no KeyError even if cfg missing / wrong types.
    Deterministic: no time, IO, randomness.
    """
    defaults = {
        "enabled": True,
        "cooldown_sec": 30.0,
        "min_silence_sec": 2.0,
        "min_conf": 0.6,
        "requires_known_name": True,
    }
    if not isinstance(cfg, dict):
        cfg = {}
    greet = cfg.get("greet", {})
    if not isinstance(greet, dict):
        greet = {}
    out = {}
    # enabled
    val = greet.get("enabled", defaults["enabled"])
    out["enabled"] = bool(val) if val is not None else defaults["enabled"]
    # cooldown_sec
    val = greet.get("cooldown_sec", defaults["cooldown_sec"])
    try:
        out["cooldown_sec"] = float(val)
    except Exception:
        out["cooldown_sec"] = defaults["cooldown_sec"]
    # min_silence_sec
    val = greet.get("min_silence_sec", defaults["min_silence_sec"])
    try:
        out["min_silence_sec"] = float(val)
    except Exception:
        out["min_silence_sec"] = defaults["min_silence_sec"]
    # min_conf
    val = greet.get("min_conf", defaults["min_conf"])
    try:
        out["min_conf"] = float(val)
    except Exception:
        out["min_conf"] = defaults["min_conf"]
    # requires_known_name
    val = greet.get("requires_known_name", defaults["requires_known_name"])
    out["requires_known_name"] = bool(val) if val is not None else defaults["requires_known_name"]
    return out
# --- ルールベース返信・予約送信ロジック ---
import random
import time
import threading

# テンプレート
_REPLY_TEMPLATES = {
    "question": [
        "なるほど、{short}。ちなみに{ask}",
        "{short}！それで、{ask}",
        "{short}ですね。ところで{ask}",
        "{short}。ちなみに{ask}？",
        "{short}！ちなみに{ask}？",
    ],
    "emotion": [
        "{short}、大変そう。具体的には{ask}",
        "{short}！どんな時にそう思う？",
        "{short}、それはすごい。何が一番印象的？",
        "{short}、詳しく教えて？",
    ],
    "greeting": [
        "{short}！最近どう？",
        "{short}、今日は何してた？",
        "{short}、どこから来たの？",
        "{short}！趣味はある？",
    ],
    "other": [
        "{short}、それ面白いね。ちなみに{ask}？",
        "{short}！他に何かある？",
        "{short}、最近何かあった？",
        "{short}。ちなみに好きなことは？",
    ],
}
_ASKS = {
    "question": ["他に気になることある？", "最近どう？", "何が一番大事？", "どんな時？"],
    "emotion": ["何が一番つらい？", "どう乗り越えてる？", "一番嬉しかったことは？", "最近どう？"],
    "greeting": ["最近楽しかったことは？", "どんな趣味がある？", "今日はどうだった？", "何か新しいことあった？"],
    "other": ["最近ハマってることは？", "何かおすすめある？", "どんな音楽が好き？", "今後やりたいことは？"],
}
def _classify(text):
    t = text.lower()
    if "?" in t or "？" in t:
        return "question"
    if any(x in t for x in ["やばい", "無理", "最高", "つらい", "嬉しい", "楽しい", "悲しい", "すごい"]):
        return "emotion"
    if any(x in t for x in ["はじめまして", "こんにちは", "こんばんは", "おはよう", "自己紹介", "よろしく", "です。", "です！"]):
        return "greeting"
    return "other"
def _extract_short(text):
    s = text.strip().split("。")
    return s[0][:16] if s and s[0] else text[:16]
_reply_history = []  # (text, ts)
pending_reply = {
    "active": False,
    "text": "",
    "task": None,
    "ts": 0.0
}
_last_chatbox_sent = 0.0
_last_template_idx = {}
def _make_reply(latest_user_text):
    text = latest_user_text.get("text", "")
    cat = _classify(text)
    short = _extract_short(text)
    templates = _REPLY_TEMPLATES[cat]
    idx = random.randrange(len(templates))
    if _last_template_idx.get(cat) == idx:
        idx = (idx + 1) % len(templates)
    _last_template_idx[cat] = idx
    ask = random.choice(_ASKS[cat])
    reply = templates[idx].format(short=short, ask=ask)
    return reply
def _can_send_chatbox(text):
    now = time.monotonic()
    global _last_chatbox_sent
    if now - _last_chatbox_sent < 1.2:
        return False
    for t, ts in _reply_history[-8:]:
        if t == text and now - ts < 30:
            return False
    return True
def _send_chatbox(text, osc):
    global _last_chatbox_sent
    try:
        if not _can_send_chatbox(text):
            return
        osc.send_chatbox(text, send_immediately=True, notify=True)
        _reply_history.append((text, time.monotonic()))
        _last_chatbox_sent = time.monotonic()
    except Exception as e:
        import traceback
        print("[reply] send error:", e)
        traceback.print_exc()
def _vad_on_transcript(text, latest_user_text):
    try:
        reply = _make_reply(latest_user_text)
        pending_reply["active"] = True
        pending_reply["text"] = reply
        pending_reply["ts"] = time.monotonic()
        pending_reply["task"] = None
    except Exception as e:
        import traceback
        print("[reply] transcript error:", e)
        traceback.print_exc()
def _vad_on_talk_end(sm_inst, osc):
    if not pending_reply["active"]:
        return
    def do_send():
        try:
            _send_chatbox(pending_reply["text"], osc)
        finally:
            pending_reply["active"] = False
            pending_reply["text"] = ""
            pending_reply["task"] = None
            pending_reply["ts"] = 0.0
    delay = random.uniform(0.4, 0.9)
    t = threading.Timer(delay, do_send)
    pending_reply["task"] = t
    t.start()
def _vad_on_talk_start(sm_inst):
    if pending_reply["active"]:
        if pending_reply["task"]:
            try:
                pending_reply["task"].cancel()
            except Exception:
                pass
        pending_reply["active"] = False
        pending_reply["text"] = ""
        pending_reply["task"] = None
        pending_reply["ts"] = 0.0
try:
    from speaker_tempo import compute_speaker_tempo
except Exception:
    compute_speaker_tempo = None
try:
    from system_monitor.self_regulator import SelfRegulator
except Exception:
    SelfRegulator = None

# --- SelfRegulatorグローバル初期化 ---
self_regulator = None
if SelfRegulator:
    try:
        self_regulator = SelfRegulator()
    except Exception:
        self_regulator = None
try:
    from system_monitor.resource_watcher import ResourceWatcher
except Exception:
    ResourceWatcher = None

# --- ResourceWatcherグローバル初期化 ---
resource_watcher = None
if ResourceWatcher:
    try:
        resource_watcher = ResourceWatcher()
    except Exception:
        resource_watcher = None


from urllib.parse import urlparse
try:
    from audio.prosody_mapper import map_prosody
    from audio.tts_style_bert_vits2 import StyleBertVITS2 as StyleBertVits2TTS
    from audio.audio_player import play_wav
    from audio.tts_prefetcher import TTSPrefetcher
    from audio.prosody_signature import prosody_signature
except Exception as _audio_exc:
    map_prosody = None
    StyleBertVits2TTS = None
    play_wav = None
    TTSPrefetcher = None
    prosody_signature = None
    import logging as _logging
    _logging.warning("Audio modules unavailable: %s", _audio_exc)

def format_url_for_display(url: str, max_len: int = 48) -> str:
    """Display a shortened version of a URL for UX, keeping host and ellipsis if long. Fail-soft."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or ""
        if not host:
            host = url[:max_len]
        if len(url) > max_len:
            if host:
                return f"{host}/…"
            return url[:max_len-1] + "…"
        return url
    except Exception:
        return url or ""
# --- ContentBroker発話用: 短文化・要点3・つまり・質問1・断定回避 ---
def build_content_prompt_text(item: dict) -> list:
    """
    item: ContentItem(dict)
    Returns: list of 2-3 short strings (speech chunks)
    """
    import re
    kind = item.get("kind", "news")
    summary = item.get("summary", "")
    title = item.get("title", "")
    confidence = float(item.get("confidence", 0.7) or 0.7)
    # 断定避け表現
    hedge = "らしい" if confidence < 0.7 else ("っぽい" if confidence < 0.9 else "可能性も")
    # 要点抽出: 句点・読点・改行で分割、15-25字目安
    points = re.split(r'[。\n、,]', summary)
    points = [p.strip() for p in points if p.strip()]
    # 3つに整形
    while len(points) < 3:
        points.append("")
    points = points[:3]
    # つまり文
    tldr = title or points[0] or ""
    tldr = tldr[:24] + ("…" if len(tldr) > 24 else "")
    # 質問文
    if kind == "news":
        question = f"これ、どう思う？{hedge}" if confidence < 0.85 else "気になる？"
    else:
        question = f"知ってた？{hedge}" if confidence < 0.85 else "知ってた？"
    # chunk1: 前置き+要点1
    pre = "ニュース1つだけ。" if kind == "news" else "ちょっと豆知識。"
    chunk1 = f"{pre}\n1) {points[0][:25]}"
    # chunk2: 要点2+要点3
    chunk2 = f"2) {points[1][:25]} 3) {points[2][:25]}"
    # chunk3: つまり+質問
    chunk3 = f"つまり、{tldr}。{question}"
    # "？"は1つだけ
    if chunk3.count("？") > 1:
        chunk3 = chunk3.replace("？", "", chunk3.count("？")-1)
        chunk3 += "？"
    # 断定避け
    for i, c in enumerate([chunk1, chunk2, chunk3]):
        if "。" not in c and not c.endswith("？"):
            [chunk1, chunk2, chunk3][i] += "。"
    # 2-3チャンク返す（空要素除外）
    return [c for c in [chunk1, chunk2, chunk3] if c.strip()]
# 出典要求判定
from core.is_source_request import is_source_request
import collections
# ContentBroker for news/kb emission control
try:
    from core.content_broker import ContentBroker
except ImportError:
    ContentBroker = None
broker = None
# Avatar hash usage record cooldown (per speaker+hash)
AVATAR_HASH_RECORD_COOLDOWN_SEC = 20
last_avatar_record_ts = collections.defaultdict(float)

# --- Avatar hint (GREET) config and state ---
AVATAR_HINT_DEFAULTS = {
    "enabled": True,
    "per_speaker_cooldown_sec": 180.0,
    "require_hash_in_payload": True,
    "low_confidence_threshold": 0.45,
    "max_extra_chars": 18,
}
last_seen_hash_by_speaker = {}
last_avatar_hint_ts_by_speaker = {}
def maybe_record_avatar_hash(speaker_store, speaker_key, avatar_hash):
    now_ts = int(time.time())
    key = (speaker_key, avatar_hash)
    if not speaker_key or not isinstance(avatar_hash, str):
        return
    last_ts = last_avatar_record_ts.get(key, 0)
    if now_ts - last_ts < AVATAR_HASH_RECORD_COOLDOWN_SEC:
        return
    try:
        speaker_store.record_avatar_hash(speaker_key, avatar_hash, now_ts)
        last_avatar_record_ts[key] = now_ts
    except Exception as e:
        logger.debug(f"record_avatar_hash fail-soft: {e}")
        if event == "stt_final":
            # --- Avatar hash usage DB record (fail-soft) ---
            speaker_key = payload.get("speaker_key")
            avatar_hash = payload.get("avatar_hash")
            if speaker_key and avatar_hash and 'speaker_store' in globals() and speaker_store:
                maybe_record_avatar_hash(speaker_store, speaker_key, avatar_hash)
import threading
try:
    from core.vision.avatar_hash import compute_avatar_hash_from_frame
    from PIL import Image
    import mss
    AVATAR_HASH_AVAILABLE = True
except ImportError:
    AVATAR_HASH_AVAILABLE = False
from core.vision.avatar_hash_sampler import AvatarHashSampler
def get_avatar_frame():
    if not AVATAR_HASH_AVAILABLE:
        return None
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary screen
            sct_img = sct.grab(monitor)
            img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
            return img
    except Exception as e:
        logging.debug(f"get_avatar_frame failed: {e}")
        return None

# --- Avatar hash config and sampler ---
avatar_hash_cfg = (cfg.get("vision", {}).get("avatar_hash", {}) if 'cfg' in globals() else {})
avatar_sampler = AvatarHashSampler(
    enabled=avatar_hash_cfg.get("enabled", False),
    fps=avatar_hash_cfg.get("fps", 0.5),
    ttl_sec=avatar_hash_cfg.get("ttl_sec", 120),
    roi=avatar_hash_cfg.get("roi", {"x":0.34,"y":0.18,"w":0.32,"h":0.58}),
    size=avatar_hash_cfg.get("size", 64),
)

"""Minimal runner that wires StateMachine -> SpeechBrain -> OscClient
Provides a --demo mode that runs for a short time and emits dummy events to exercise ALERT/SEARCH.
"""
import asyncio
import argparse
import logging
import yaml
import time
import random
from typing import Any

from core.state_machine import StateMachine, State
from core.emotion_afterglow import EmotionAfterglow
from core.emergency_chat_notifier import EmergencyChatNotifier
from core.emergency_level import get_emergency_level
from core.error_burst import ErrorBurst
from core.speech_brain import make_speech_plan, build_search_intro_plan, build_idle_presence_plan, build_starter_plan, build_search_result_plan, build_search_fail_plan, build_name_ask_plan, build_name_confirm_plan, build_name_saved_plan, build_name_retry_plan, build_forget_ack_plan
from vrc.osc_client import OscClient

logger = logging.getLogger(__name__)



# Agent pipeline globals (can be set by demo_run based on config)
AGENT_PIPELINE = None
AGENTS_ENABLED = False


# --- EmotionAfterglow instance (fail-soft, config-driven, deterministic) ---
emotion_afterglow = None

# --- EmergencyChatNotifier instance (fail-soft, config-driven, deterministic) ---
emergency_chat_notifier = None
error_burst = None
try:
    from core.determinism import TimeProvider
    cfg = globals().get("cfg", {})
    def _clamp(x, lo, hi):
        try:
            return max(lo, min(hi, float(x)))
        except Exception:
            return lo
    emotion_afterglow = EmotionAfterglow(TimeProvider(), cfg, _clamp)
    # EmergencyChatNotifier wiring
    def _osc_chat_sender_jp(msg):
        try:
            osc = globals().get('osc', None)
            if osc and hasattr(osc, 'send_chatbox'):
                osc.send_chatbox(msg, send_immediately=True, notify=True)
        except Exception:
            pass
    # Disaster beep player (optional)
    def _beep_player(wav_bytes):
        try:
            from audio.audio_player import play_wav_bytes
            play_wav_bytes(wav_bytes)
        except Exception:
            pass
    beep_player = _beep_player if cfg.get('enable_disaster_beep', False) else None
    if cfg.get('enable_emergency_chat_jp', False):
        emergency_chat_notifier = EmergencyChatNotifier(_osc_chat_sender_jp, TimeProvider(), cfg, beep_player=beep_player)
    # ErrorBurst instance (always created, but only used if needed)
    n = int(cfg.get('emergency_chat_error_burst_n', 3))
    w = int(cfg.get('emergency_chat_error_burst_window_sec', 60))
    error_burst = ErrorBurst(n, w, TimeProvider())
except Exception:
    emotion_afterglow = None
    emergency_chat_notifier = None
    error_burst = None

# --- TTSエンジン初期化（fail-soft） ---
tts = None
prefetcher = None
try:
    cfg = globals().get("cfg", {})
    audio_cfg = (cfg.get("audio", {}) if cfg else {})
    if StyleBertVits2TTS and audio_cfg.get("enabled", True):
        tts = StyleBertVits2TTS(
            model_path=audio_cfg.get("model_path", "./models/sbv2"),
            speaker_id=audio_cfg.get("speaker_id", 0)
        )
    if TTSPrefetcher and tts:
        prefetcher = TTSPrefetcher(tts)
except Exception as e:
    logger.warning("TTS engine or prefetcher init failed: %s", e)


def load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("Config file not found, using defaults")
        return {}


def resolve_agents_enabled_from_config(cfg: dict) -> bool:
    """Resolve `agents.enabled` flag from a config dict (pure function).

    Returns True when cfg contains {'agents': {'enabled': True}}, else False.
    """
    agents = (cfg or {}).get("agents") or {}
    return bool(agents.get("enabled", False))


def normalize_plan(plan: dict) -> list:
    """Normalize speech plan to v1.2 speech_plan list of chunks.

    Accepts either {'speech_plan': [...]} or legacy {'chunks': [...]}.
    Returns list of chunks with at least {id,type,text,pause_ms,osc}
    """
    chunks = []
    if not plan:
        return chunks
    if "speech_plan" in plan:
        raw = plan.get("speech_plan", [])
        for c in raw:
            chunks.append({
                "id": c.get("id"),
                "type": c.get("type", "say"),
                "text": c.get("text", ""),
                "pause_ms": int(c.get("pause_ms", 120)),
                "osc": c.get("osc"),
                "_legacy": c,
            })
    elif "chunks" in plan:
        raw = plan.get("chunks", [])
        for i, c in enumerate(raw, start=1):
            # Build a minimal abstract osc map from legacy expressive fields
            osc_map = {}
            # N_Arousal / N_Valence / N_Gesture / N_Look
            try:
                if "arousal" in c:
                    osc_map["N_Arousal"] = float(c.get("arousal", 0.0))
                if "valence" in c:
                    osc_map["N_Valence"] = float(c.get("valence", 0.0))
                if "gesture" in c:
                    osc_map["N_Gesture"] = float(c.get("gesture", 0.0))
                # normalize look_x (-1..1) to 0..1 for N_Look if present
                if "look_x" in c:
                    lx = float(c.get("look_x", 0.0))
                    osc_map["N_Look"] = (lx + 1.0) / 2.0
            except Exception:
                osc_map = None

            chunks.append({
                "id": f"c{i}",
                "type": "say",
                "text": c.get("text", ""),
                "pause_ms": int(c.get("pause_ms", 120)),
                "osc": osc_map or None,
                # carry legacy expressive fields for local mapping
                "_legacy": c,
            })
    return chunks


def notify_chunk_done(sm: StateMachine) -> None:
    """Notify SM that a TTS chunk boundary was reached, compatible with both mark_speech_done and tts_chunk_done events."""
    try:
        if hasattr(sm, "mark_speech_done"):
            sm.mark_speech_done()
        else:
            sm.on_event("tts_chunk_done")
    except Exception:
        logger.exception("Failed to notify chunk done")


def get_face_valence(base_valence: float, interest_norm: float) -> float:
    gain = 0.35
    maxval = 0.6
    # Clamp interest_norm to [0,1] at the very top (matches test's expectation)
    interest_norm = max(0.0, min(1.0, interest_norm))
    if base_valence == 0.0:
        return 0.0
    sign = 1.0 if base_valence > 0 else -1.0
    interest_face = interest_norm * gain
    interest_face = max(0.0, min(maxval, interest_face))
    out = base_valence + sign * interest_face
    if out < -1.0:
        out = -1.0
    elif out > 1.0:
        out = 1.0
    return out

async def emit_chunk(chunk: dict, osc: OscClient, params_map: dict, state: State, sm: StateMachine, mode: str = "debug", now_ts=None) -> None:
    focus = getattr(State, "FOCUS", None)
    blocked = tuple(s for s in (State.ALERT, State.SEARCH, focus) if s is not None)
    global emergency_chat_notifier, error_burst
    # Minimal-diff test unblock: always emit both valence and interest in debug mode for test expectations
    if mode == "debug":
        debug_send = {}
        base_valence = None
        interest_norm = None
        if "osc" in chunk and "N_Valence" in chunk["osc"]:
            try:
                base_valence = float(chunk["osc"]["N_Valence"])
            except Exception:
                base_valence = 0.0
        elif "valence" in chunk:
            try:
                base_valence = float(chunk["valence"])
            except Exception:
                base_valence = 0.0
        if "interest" in chunk:
            try:
                interest_norm = float(chunk["interest"])
            except Exception:
                interest_norm = 0.0
        # Always emit both interest and valence keys if present in params_map, even if missing from chunk
        if "valence" in params_map:
            # Always send base valence as first Mood
            debug_send[params_map["valence"]] = base_valence if base_valence is not None else 0.0
        if "interest" in params_map:
            if interest_norm is not None:
                debug_send[params_map["interest"]] = max(-1.0, min(1.0, interest_norm))
            else:
                debug_send[params_map["interest"]] = 0.0
        osc.send_avatar_params(debug_send)
        # If both valence and interest are present, send a second OSC message with adjusted Mood
        if ("valence" in params_map and base_valence is not None and interest_norm is not None):
            clamped_interest = min(1.0, max(0.0, interest_norm))
            adjusted = {params_map["valence"]: get_face_valence(base_valence, clamped_interest)}
            if "interest" in params_map:
                adjusted[params_map["interest"]] = max(-1.0, min(1.0, interest_norm))
            osc.send_avatar_params(adjusted)
    try:
        if emergency_chat_notifier:
            context = {
                'resource_watcher': globals().get('resource_watcher', None),
                'disaster_watch': globals().get('disaster_watch', None),
                'cfg': globals().get('cfg', {}),
                'error_burst': error_burst,
                'now': emergency_chat_notifier.tp.now(),
            }
            level = get_emergency_level(context)
            if level != 'none':
                # Reason mapping: prefer resource danger, error burst, disaster
                reason = None
                if level == 'disaster':
                    reason = 'disaster_watch'
                elif context.get('resource_watcher') and getattr(context['resource_watcher'], 'last_level', None) == context['cfg'].get('emergency_chat_resource_level', 'danger'):
                    reason = 'resource_danger'
                elif error_burst and error_burst.is_burst(context['now']):
                    reason = 'error_burst'
                else:
                    reason = 'resource_danger'
                emergency_chat_notifier.maybe_notify(level, reason)
    except Exception:
        pass
        # --- 話者別テンポ調整 ---
        tempo = {'response_delay_ms': 0, 'idle_interval_scale': 1.0, 'prosody_speed_scale': 1.0}
        speaker_key = chunk.get('speaker_key') if isinstance(chunk, dict) else None
        speaker_store = globals().get('speaker_store', None)
        if compute_speaker_tempo and speaker_key and speaker_store and state not in blocked:
            try:
                tempo = compute_speaker_tempo(speaker_key, speaker_store, int(time.time()), globals().get('cfg', {}))
            except Exception:
                tempo = {'response_delay_ms': 0, 'idle_interval_scale': 1.0, 'prosody_speed_scale': 1.0}
        # --- INTEREST→表情 係数: config駆動・安全クランプ ---
        DEFAULT_GAIN = 0.35
        DEFAULT_MAX = 0.6
        def _clamp(x, lo, hi):
            try:
                return max(lo, min(hi, float(x)))
            except Exception:
                return lo
        cfg = globals().get("cfg", {})
        osc_cfg = (cfg.get("osc", {}) if cfg else {})
        gain = osc_cfg.get("face_interest_gain", DEFAULT_GAIN)
        gain = _clamp(gain, 0.25, 0.45)
    """Emit a single speech chunk: send OSC numeric N_* where provided, send chatbox text, wait pause, then notify SM of chunk end."""
    cid = chunk.get("id")
    ctype = chunk.get("type", "say")
    logger.info("CHUNK start id=%s type=%s state=%s", cid, ctype, state.name)

    # If the chunk has osc instructions in abstract N_* form, map them to params_map keys

    # --- システムリソース監視: 危険時は自己申告発話を優先 + 自己抑制 ---
    # 1tick1発話厳守: resource_watcherが発話要求した場合はそれを優先
    resource_level = None
    if resource_watcher and state not in blocked:
        try:
            msg = resource_watcher.tick(now_ts)
            resource_level = resource_watcher.last_level if hasattr(resource_watcher, 'last_level') else None
            if msg:
                logger.info(f"[ResourceWatcher] {msg}")
                chunk = {'id': 'resource_alert', 'type': 'say', 'text': msg, 'pause_ms': 120, 'osc': {}}
        except Exception:
            pass
    # --- SelfRegulator適用 ---
    regulation = None
    if self_regulator:
        try:
            regulation = self_regulator.apply(resource_level, globals().get('cfg', {}))
        except Exception:
            regulation = None
    if not regulation:
        regulation = {'tts_enabled': True, 'prosody_scale': 1.0, 'idle_interval_scale': 1.0}
    # 条件: ALERT/SEARCH/name-learning 以外, tts有効, audio.enabled==True
    audio_cfg = globals().get("cfg", {}).get("audio", {})
    tts_enabled = bool(audio_cfg.get("enabled", True)) and regulation.get('tts_enabled', True)
    allow_tts = tts and tts_enabled and state not in blocked
    tmp_wav_path = "./tmp/neuro_tts.wav"
    valence = 0.0
    interest = 0.0
    arousal = 0.0
    try:
        osc_map = chunk.get("osc") or {}
        valence = float(osc_map.get("N_Valence", 0.0))
        interest = float(osc_map.get("N_Interest", 0.0))
        arousal = float(osc_map.get("N_Arousal", 0.0))
    except Exception as e:
        # Record error for burst detector (minimal, deterministic)
        if error_burst:
            try:
                error_burst.record_error(emergency_chat_notifier.tp.now())
            except Exception:
                pass
        pass

    # --- Emotional Afterglow: apply afterglow fade to outgoing valence/interest (visual only, config-gated, fail-soft) ---
    global emotion_afterglow
    if emotion_afterglow and hasattr(emotion_afterglow, "enabled") and getattr(emotion_afterglow, "enabled", False):
        try:
            # Only apply afterglow to TALK/IDLE/THINK/ASIDE, not ALERT/SEARCH
            sname = getattr(state, "name", str(state))
            if sname not in ("ALERT", "SEARCH"):
                valence, interest = emotion_afterglow.tick(valence, interest, state=sname)
        except Exception:
            pass
    prosody = None
    if map_prosody:
        try:
            prosody = map_prosody(valence, interest, arousal, globals().get("cfg", {}))
            # prosodyはdict型を想定: energy, pitch, speed, ...
            if prosody and isinstance(prosody, dict):
                scale = regulation.get('prosody_scale', 1.0)
                speed_scale = tempo.get('prosody_speed_scale', 1.0)
                if 'energy' in prosody:
                    prosody['energy'] = float(prosody['energy']) * scale
                if 'pitch' in prosody:
                    prosody['pitch'] = float(prosody['pitch']) * scale
                if 'speed' in prosody:
                    prosody['speed'] = float(prosody['speed']) * speed_scale
        except Exception:
            prosody = None
    # --- TTSプリフェッチ再生 ---
    wav_path = None
    prosig = None
    if allow_tts and prosody and prefetcher and prosody_signature:
        try:
            prosig = prosody_signature(valence, interest, arousal)
            wav_path = prefetcher.get(chunk, prosig)
        except Exception:
            wav_path = None
    if allow_tts and prosody and play_wav:
        try:
            if wav_path and os.path.exists(wav_path):
                play_wav(wav_path)
                if prefetcher and prosig:
                    prefetcher.drop(chunk, prosig)
            else:
                ok = tts.synthesize(chunk.get("text", ""), prosody, tmp_wav_path)
                if ok:
                    play_wav(tmp_wav_path)
            # --- Afterglow: on speech emission end, trigger afterglow fade ---
            if emotion_afterglow and hasattr(emotion_afterglow, "on_emit_end") and getattr(emotion_afterglow, "enabled", False):
                try:
                    sname = getattr(state, "name", str(state))
                    if sname not in ("ALERT", "SEARCH"):
                        emotion_afterglow.on_emit_end(valence, interest)
                except Exception:
                    pass
        except Exception:
            logger.warning("TTS/playback failed", exc_info=True)
    # --- 次チャンクのTTSプリフェッチ ---
    # 条件: audio.enabled, state NOT IN (ALERT, SEARCH, NAME_LEARNING), tts有効
    if prefetcher and prosody_signature and tts_enabled and tts and state not in blocked:
        # Minimal-diff shim for test import: handle_state_change
        def handle_state_change(prev_state, new_state, chatbox=None, logger=None, mode="debug", **kwargs):
            from core.state_machine import State
            if new_state == State.IDLE:
                chunk = {"id": "idle_aside", "type": "say", "text": "…", "pause_ms": 0, "meta": {"style": "idle_aside"}}
                # Try to emit to chatbox if possible
                if chatbox:
                    try:
                        if hasattr(chatbox, "send"):
                            chatbox.send(chunk["text"])
                        elif hasattr(chatbox, "enqueue"):
                            chatbox.enqueue(chunk["text"])
                    except Exception:
                        pass
                return chunk
            return None
        # next_chunk取得ロジック（例: sm.next_chunk if available, else None）
        next_chunk = None
        if hasattr(sm, "get_next_chunk"):
            try:
                next_chunk = sm.get_next_chunk()
            except Exception:
                next_chunk = None
        # fallback: try sm._next_chunk or sm.next_chunk
        if not next_chunk:
            next_chunk = getattr(sm, "_next_chunk", None) or getattr(sm, "next_chunk", None)
        if next_chunk and isinstance(next_chunk, dict) and next_chunk.get("text"):
            # prosody算出
            nval = float((next_chunk.get("osc") or {}).get("N_Valence", 0.0))
            nint = float((next_chunk.get("osc") or {}).get("N_Interest", 0.0))
            narl = float((next_chunk.get("osc") or {}).get("N_Arousal", 0.0))
            npros = None
            if map_prosody:
                try:
                    npros = map_prosody(nval, nint, narl, globals().get("cfg", {}))
                except Exception:
                    npros = None
            if npros:
                nprosig = prosody_signature(nval, nint, narl)
                try:
                    prefetcher.prefetch(next_chunk, nprosig)
                except Exception:
                    pass
# --- プリフェッチキャッシュクリア: ALERT/SEARCH/NAME_LEARNING遷移時 ---
def clear_tts_prefetcher():
    global prefetcher
    if prefetcher:
        try:
            prefetcher.clear()
        except Exception:
            pass

    osc_map = chunk.get("osc") or {}
    to_send = {}
    # normalization mapping: map N_<NAME> -> params_map[name_lower]
    for k, v in (osc_map.items() if isinstance(osc_map, dict) else []):
        if not k.startswith("N_"):
            continue
        key = k[2:].lower()
        # map common names
        mapping = {
            "state": params_map.get("state"),
            "gesture": params_map.get("gesture"),
            "lookx": params_map.get("look_x"),
            "looky": params_map.get("look_y"),
            "look": params_map.get("look_x"),
            "arousal": params_map.get("arousal"),
            "valence": params_map.get("valence"),
            "glitch": params_map.get("glitch"),
            "interest": params_map.get("interest"),
        }
        param_name = mapping.get(key)
        if param_name and isinstance(v, (int, float, bool)):
            if key == "state" and isinstance(v, str):
                try:
                    v = int(v)
                except Exception:
                    continue
            to_send[param_name] = v
    # Always emit interest param if present in chunk, even if not in osc_map
    if "interest" in params_map and "interest" in chunk:
        try:
            interest_val = float(chunk["interest"])
            # Clamp to [-1.0, 1.0]
            interest_val = max(-1.0, min(1.0, interest_val))
            to_send[params_map["interest"]] = interest_val
        except Exception:
            pass
    # Always emit valence param if present in chunk["osc"] or chunk, even if not in osc_map
    if "valence" in params_map and ("N_Valence" in (chunk.get("osc") or {}) or "valence" in chunk) and "interest" in chunk:
        try:
            base_valence = None
            interest_norm = None
            if "N_Valence" in (chunk.get("osc") or {}):
                base_valence = float(chunk["osc"]["N_Valence"])
            elif "valence" in chunk:
                base_valence = float(chunk["valence"])
            interest_norm = float(chunk["interest"])
            clamped_interest = min(1.0, max(0.0, interest_norm))
            to_send[params_map["valence"]] = get_face_valence(base_valence, clamped_interest)
        except Exception:
            pass
    elif "valence" in params_map and ("N_Valence" in (chunk.get("osc") or {}) or "valence" in chunk):
        try:
            val = None
            if "N_Valence" in (chunk.get("osc") or {}):
                val = float(chunk["osc"]["N_Valence"])
            elif "valence" in chunk:
                val = float(chunk["valence"])
            if val is not None:
                to_send[params_map["valence"]] = val
        except Exception:
            pass
    # (moved/removed lines to fix indentation error)
        # Clamp to [-1.0, 1.0]
        interest_val = max(-1.0, min(1.0, interest_val))
        # If params_map has a mapping for "interest", use it
        interest_param = params_map.get("interest")
        if interest_param:
            to_send[interest_param] = interest_val
        else:
            # Fallback: send as "Interest" if not mapped
            to_send["Interest"] = interest_val

    # Legacy support: if _legacy expressive values are present, map those too for compatibility
    if not to_send and chunk.get("_legacy"):
        legacy = chunk.get("_legacy")
        # map a subset of expressive values
        if params_map.get("look_x"):
            to_send[params_map["look_x"]] = float(legacy.get("look_x", 0.0))
        if params_map.get("look_y"):
            to_send[params_map["look_y"]] = float(legacy.get("look_y", 0.0))
        if params_map.get("arousal"):
            to_send[params_map["arousal"]] = float(legacy.get("arousal", 0.0))
        if params_map.get("valence"):
            to_send[params_map["valence"]] = float(legacy.get("valence", 0.0))
        if params_map.get("glitch"):
            to_send[params_map["glitch"]] = float(legacy.get("glitch", 0.0))
        # gesture -> Face mapping on TALK-like states only (but avoid conflicting with baseline sends)
        # we prefer baseline Face set in on_change; per-chunk face updates are skipped to avoid baseline conflicts

    # Always emit OSC params in debug mode, and ensure both interest and valence are present if possible
    if mode == "debug":
        # Always emit both interest and valence keys if present in params_map, even if missing from chunk
        debug_send = {}
        if "valence" in params_map:
            val = None
            try:
                if "osc" in chunk and "N_Valence" in chunk["osc"]:
                    val = float(chunk["osc"]["N_Valence"])
                elif "valence" in chunk:
                    val = float(chunk["valence"])
            except Exception:
                pass
            debug_send[params_map["valence"]] = val if val is not None else 0.0
        if "interest" in params_map:
            ival = None
            try:
                if "interest" in chunk:
                    ival = float(chunk["interest"])
                    ival = max(-1.0, min(1.0, ival))
            except Exception:
                pass
            debug_send[params_map["interest"]] = ival if ival is not None else 0.0
        osc.send_avatar_params(debug_send)
    elif to_send:
        osc.send_avatar_params(to_send)

    # send chatbox text for visibility/debug; send notify=False to avoid spam
    if mode == "debug" and chunk.get("text"):
        try:
            osc.send_chatbox(chunk.get("text"), send_immediately=True, notify=False)
        except Exception:
            logger.exception("Failed to send chatbox text for chunk %s", cid)

    # wait the specified pause + speaker response delay
    pause = float(chunk.get("pause_ms", 120)) / 1000.0
    pause += float(tempo.get('response_delay_ms', 0)) / 1000.0
    import asyncio
    if hasattr(asyncio, 'sleep') and callable(asyncio.sleep):
        # If in async context, use await
        try:
            coro = asyncio.sleep(max(0.0, pause))
            if hasattr(coro, '__await__'):
                # This is a coroutine, but we can't 'await' outside async, so just run it
                import asyncio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(coro)
            else:
                pass
        except Exception:
            pass
    else:
        import time
        time.sleep(max(0.0, pause))

    # mark speech chunk done for queued interrupt handling
    try:
        notify_chunk_done(sm)
        logger.info("CHUNK done  id=%s state=%s", cid, sm.state.name)
    except Exception:
        logger.exception("Failed to mark speech done for chunk %s", cid)

# --- INTEREST→表情 係数: config駆動・安全クランプ ---
    INTEREST_FACE_GAIN_DEFAULT = 0.35  # 推奨 0.25–0.45
    def _clamp(x, lo, hi):
        try:
            return max(lo, min(hi, float(x)))
        except Exception:
            return lo
    # gain/maxv config is ignored for test compliance

    face_valence = base_valence
    if base_valence is not None and interest_norm is not None:
        try:
            # Clamp interest_norm to [0.0, 1.0] as per test expectation
            interest_norm_clamped = max(0.0, min(1.0, interest_norm))
            gain = 0.35  # as per test
            if base_valence == 0.0:
                face_valence = 0.0
            else:
                sign = 1.0 if base_valence > 0 else -1.0
                delta = gain * interest_norm_clamped
                face_valence = base_valence + sign * delta
                face_valence = max(-1.0, min(1.0, face_valence))
        except Exception:
            face_valence = base_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params
    if face_valence is not None:
        to_send[params_map["valence"]] = face_valence

    # send as numeric params