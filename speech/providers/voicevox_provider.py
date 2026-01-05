import json
import urllib.request
import urllib.parse
from typing import Optional
from ..types import TTSAudio, VoiceSpec, Prosody
from ..interfaces import TTSProvider

class VoiceVoxTTSProvider(TTSProvider):
    def __init__(self, base_url: str = "http://127.0.0.1:50021", speaker_id: int = 1, timeout_sec: float = 2.5):
        self.base_url = base_url.rstrip("/")
        self.speaker_id = speaker_id
        self.timeout_sec = timeout_sec

    def synthesize(self, text: str, voice: VoiceSpec, prosody: Prosody, *, seed: Optional[int] = None, request_id: Optional[str] = None) -> Optional[TTSAudio]:
        try:
            if not text or not text.strip():
                return None
            # Step 1: audio_query
            query_url = f"{self.base_url}/audio_query?text={urllib.parse.quote(text)}&speaker={self.speaker_id}"
            req = urllib.request.Request(query_url, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                query_json = json.loads(resp.read().decode("utf-8"))
            # Step 2: apply prosody knobs (minimal)
            if prosody:
                if "rate" in prosody:
                    try:
                        query_json["speedScale"] = float(prosody["rate"])
                    except Exception:
                        pass
                if "pitch" in prosody:
                    try:
                        query_json["pitchScale"] = float(prosody["pitch"])
                    except Exception:
                        pass
                if "energy" in prosody:
                    try:
                        query_json["intonationScale"] = float(prosody["energy"])
                    except Exception:
                        pass
            # Step 3: synthesis
            synth_url = f"{self.base_url}/synthesis?speaker={self.speaker_id}"
            synth_req = urllib.request.Request(synth_url, data=json.dumps(query_json).encode("utf-8"), method="POST")
            synth_req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(synth_req, timeout=self.timeout_sec) as synth_resp:
                wav_bytes = synth_resp.read()
            return TTSAudio(
                sample_rate=0,  # unknown, keep minimal
                pcm_bytes=wav_bytes,
                duration_ms=None,
                format="wav"
            )
        except Exception:
            return None
