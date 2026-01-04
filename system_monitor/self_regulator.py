class SelfRegulator:
    def __init__(self):
        self.last_level = None

    def apply(self, level, config=None):
        """
        Args:
            level: 'ok'|'warn'|'danger'|None
            config: (optional) dict for future extension
        Returns:
            dict: {
                'tts_enabled': bool,
                'prosody_scale': float,
                'idle_interval_scale': float
            }
        """
        # Defaults
        tts_enabled = True
        prosody_scale = 1.0
        idle_interval_scale = 1.0
        if level == 'warn':
            tts_enabled = True
            prosody_scale = 0.85
            idle_interval_scale = 1.3
        elif level == 'danger':
            tts_enabled = False
            prosody_scale = 0.7
            idle_interval_scale = 1.6
        # Clamp for safety
        prosody_scale = max(0.5, min(1.0, float(prosody_scale)))
        idle_interval_scale = max(0.5, min(2.0, float(idle_interval_scale)))
        self.last_level = level
        return {
            'tts_enabled': tts_enabled,
            'prosody_scale': prosody_scale,
            'idle_interval_scale': idle_interval_scale
        }
