# core/emergency_chat_notifier.py
import hashlib

class EmergencyChatNotifier:
    def __init__(self, osc_chat_sender, time_provider, config, format_url_for_display=None, beep_player=None):
        self.send_chat = osc_chat_sender
        self.tp = time_provider
        self.cfg = config or {}
        self.format_url = format_url_for_display
        self.enabled = bool(self.cfg.get('enable_emergency_chat_jp', False))
        # Cooldowns and clamps
        self.em_cd = max(30, min(600, int(self.cfg.get('emergency_chat_cooldown_sec', 120))))
        self.dis_cd = max(8, int(self.cfg.get('disaster_chat_cooldown_sec', 10)))
        self.dedupe_window = max(30, int(self.cfg.get('emergency_chat_dedupe_window_sec', 600)))
        self.max_lines = max(2, min(6, int(self.cfg.get('emergency_chat_max_lines', 4))))
        self.max_chars = max(80, min(220, int(self.cfg.get('emergency_chat_max_chars', 180))))
        self.em_prefix = str(self.cfg.get('emergency_chat_prefix', '【緊急】'))
        self.dis_prefix = str(self.cfg.get('disaster_chat_prefix', '【緊急】'))
        # Disaster beep config
        self.enable_beep = bool(self.cfg.get('enable_disaster_beep', False))
        self.beep_min_interval = max(8, int(self.cfg.get('disaster_beep_min_interval_sec', 10)))
        self.beep_freq = max(600, min(2000, int(self.cfg.get('disaster_beep_freq_hz', 1000))))
        self.beep_dur = max(80, min(400, int(self.cfg.get('disaster_beep_duration_ms', 160))))
        self.beep_gain = max(0.05, min(0.6, float(self.cfg.get('disaster_beep_gain', 0.25))))
        self.beep_repeats = max(1, min(3, int(self.cfg.get('disaster_beep_repeats', 1))))
        self.beep_gap = max(60, min(400, int(self.cfg.get('disaster_beep_repeat_gap_ms', 120))))
        self.beep_player = beep_player
        self.last_beep_ts = 0.0
        self._disaster_beep_attempts = 0  # test observability only
        # State
        self.last_sent_ts_em = 0.0
        self.last_sent_ts_dis = 0.0
        self.last_hash_em = None
        self.last_hash_dis = None
        self.last_sent_ts_by_hash = {}
    def maybe_notify(self, level, reason, details=None):
        if not self.enabled or not self.send_chat:
            return
        now = self.tp.now()
        prefix = self.dis_prefix if level == 'disaster' else self.em_prefix
        cd = self.dis_cd if level == 'disaster' else self.em_cd
        last_ts = self.last_sent_ts_dis if level == 'disaster' else self.last_sent_ts_em
        last_hash = self.last_hash_dis if level == 'disaster' else self.last_hash_em
        # Format message
        msg = self._format_message(prefix, level, reason, details)
        h = hashlib.sha256(msg.encode('utf-8')).hexdigest()
        # Dedupe window: block if hash sent recently (identical content)
        if h in self.last_sent_ts_by_hash and now - self.last_sent_ts_by_hash[h] < self.dedupe_window:
            if h == last_hash and now - last_ts < cd:
                return
        # Content change: send immediately if hash differs
        if h != last_hash:
            try:
                self.send_chat(msg)
                if level == 'disaster':
                    self._maybe_beep_disaster(now)
            except Exception:
                return
            if level == 'disaster':
                self.last_sent_ts_dis = now
                self.last_hash_dis = h
            else:
                self.last_sent_ts_em = now
                self.last_hash_em = h
            self.last_sent_ts_by_hash[h] = now
            return
        # Same content: enforce cooldown
        if h == last_hash and now - last_ts < cd:
            return
        # Otherwise, send (cooldown elapsed)
        try:
            self.send_chat(msg)
            if level == 'disaster':
                self._maybe_beep_disaster(now)
        except Exception:
            return
        if level == 'disaster':
            self.last_sent_ts_dis = now
            self.last_hash_dis = h
        else:
            self.last_sent_ts_em = now
            self.last_hash_em = h
        self.last_sent_ts_by_hash[h] = now

    def _maybe_beep_disaster(self, now):
        if not self.enable_beep or not self.beep_player:
            return
        if now - self.last_beep_ts < self.beep_min_interval:
            return
        try:
            # Generate beep wav bytes
            from audio.beep import make_beep_wav_bytes
            from audio.audio_player import play_wav_bytes
            wav_bytes = make_beep_wav_bytes(self.beep_freq, self.beep_dur, self.beep_gain)
            # Only repeat=1 unless a non-blocking scheduler exists (see instructions)
            for _ in range(self.beep_repeats):
                self._disaster_beep_attempts += 1  # test observability only
                self.beep_player(wav_bytes)
                break  # Only 1 unless non-blocking repeat is supported
            self.last_beep_ts = now
        except Exception:
            pass
    def _format_message(self, prefix, level, reason, details):
        if level == 'disaster':
            # Fixed strict template (2–3 lines)
            lines = [self.dis_prefix, '災害の可能性があります。', '安全を最優先してください。']
            msg = '\n'.join(lines[:self.max_lines])
            if len(msg) > self.max_chars:
                msg = msg[:self.max_chars]
            return msg
        # Emergency: existing mapping
        reason_map = {
            'resource_danger': '負荷が高く安全運用モードです。',
            'audio_failure': '音声出力に問題があります。',
            'error_burst': '不安定な状態です。',
            'disaster_watch': '災害の可能性があります。',
        }
        line2 = reason_map.get(reason, '異常を検知しました。')
        lines = [prefix, line2]
        if reason == 'resource_danger':
            lines.append('発話を控えます。')
        elif reason == 'audio_failure':
            lines.append('再起動を検討してください。')
        elif reason == 'error_burst':
            lines.append('しばらくお待ちください。')
        # Clamp lines and chars
        lines = lines[:self.max_lines]
        msg = '\n'.join(lines)
        if len(msg) > self.max_chars:
            while len(msg) > self.max_chars and len(lines) > 2:
                lines = lines[:-1]
                msg = '\n'.join(lines)
            if len(msg) > self.max_chars:
                msg = msg[:self.max_chars]
        return msg
