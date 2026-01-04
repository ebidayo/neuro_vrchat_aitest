import pytest
import time
from unittest.mock import MagicMock

from core.speech_brain import build_greet_plan

def make_greet_env():
    # Minimal state for GREET avatar hint logic
    return {
        'last_seen_hash_by_speaker': {},
        'last_avatar_hint_ts_by_speaker': {},
        'avatar_hint_cfg': {
            'enabled': True,
            'per_speaker_cooldown_sec': 180.0,
            'require_hash_in_payload': True,
            'low_confidence_threshold': 0.45,
            'max_extra_chars': 18,
        }
    }

def run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now, confidence=0.8, greet_text='や、テスト。', has_question=False, cooldown_ok=True):
    # Simulate the GREET logic for avatar hint
    env['last_seen_hash_by_speaker'][speaker_key] = prev_hash
    if not cooldown_ok:
        env['last_avatar_hint_ts_by_speaker'][speaker_key] = now - 100
    else:
        env['last_avatar_hint_ts_by_speaker'][speaker_key] = now - 9999
    avatar_hint_cfg = env['avatar_hint_cfg']
    extra = ""
    if (
        avatar_hint_cfg["enabled"]
        and isinstance(speaker_key, str) and speaker_key and not speaker_key.startswith("unknown_")
        and confidence >= avatar_hint_cfg["low_confidence_threshold"]
        and (not avatar_hint_cfg["require_hash_in_payload"] or (isinstance(current_hash, str) and current_hash))
    ):
        prev = env['last_seen_hash_by_speaker'].get(speaker_key)
        cooldown_ok = (now - env['last_avatar_hint_ts_by_speaker'].get(speaker_key, 0)) >= avatar_hint_cfg["per_speaker_cooldown_sec"]
        if prev is not None and current_hash and prev != current_hash and cooldown_ok:
            # 質問数ルール
            q_hint = "今日ちょっと雰囲気ちがう？"[:avatar_hint_cfg["max_extra_chars"]]
            n_hint = "あれ、雰囲気ちがうかも。"[:avatar_hint_cfg["max_extra_chars"]]
            if has_question:
                extra = n_hint
            else:
                extra = q_hint
            if extra:
                greet_text = (greet_text + " " + extra)[:28]
                env['last_avatar_hint_ts_by_speaker'][speaker_key] = now
        env['last_seen_hash_by_speaker'][speaker_key] = current_hash or prev
    else:
        env['last_seen_hash_by_speaker'][speaker_key] = current_hash
    return greet_text, extra

def test_greet_avatar_hint_added():
    env = make_greet_env()
    now = 1000
    speaker_key = 'user1'
    prev_hash = 'hashA'
    current_hash = 'hashB'
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now)
    assert '雰囲気ちがう' in greet_text
    assert extra

def test_greet_avatar_hint_not_added_same_hash():
    env = make_greet_env()
    now = 1000
    speaker_key = 'user1'
    prev_hash = 'hashA'
    current_hash = 'hashA'
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now)
    assert '雰囲気ちがう' not in greet_text
    assert not extra

def test_greet_avatar_hint_not_added_unknown():
    env = make_greet_env()
    now = 1000
    speaker_key = 'unknown_1'
    prev_hash = 'hashA'
    current_hash = 'hashB'
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now)
    assert '雰囲気ちがう' not in greet_text
    assert not extra

def test_greet_avatar_hint_not_added_low_confidence():
    env = make_greet_env()
    now = 1000
    speaker_key = 'user1'
    prev_hash = 'hashA'
    current_hash = 'hashB'
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now, confidence=0.2)
    assert '雰囲気ちがう' not in greet_text
    assert not extra

def test_greet_avatar_hint_not_added_cooldown():
    env = make_greet_env()
    now = 1000
    speaker_key = 'user1'
    prev_hash = 'hashA'
    current_hash = 'hashB'
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now, cooldown_ok=False)
    assert '雰囲気ちがう' not in greet_text
    assert not extra

def test_greet_avatar_hint_question_rule():
    env = make_greet_env()
    now = 1000
    speaker_key = 'user1'
    prev_hash = 'hashA'
    current_hash = 'hashB'
    # 既存GREETが質問あり
    greet_text, extra = run_greet_hint_logic(env, speaker_key, prev_hash, current_hash, now, has_question=True)
    assert extra == "あれ、雰囲気ちがうかも。"
    assert '？' not in extra
