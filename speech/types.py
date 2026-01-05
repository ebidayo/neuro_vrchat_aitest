from dataclasses import dataclass, field
from typing import Optional, Union, Dict, Any

# Type alias for prosody
Prosody = Dict[str, object]

@dataclass(frozen=True)
class VoiceSpec:
    voice_id: str = "default"
    style: Optional[str] = None

@dataclass(frozen=True)
class TTSAudio:
    sample_rate: int
    pcm_bytes: bytes
    duration_ms: Optional[int] = None
    format: str = "pcm_s16le"  # can be 'pcm_s16le' or 'wav'

@dataclass(frozen=True)
class SpeechMeta:
    kind: str = "normal"  # "aizuchi"/"normal"/"announce"
    priority: int = 0
    can_interrupt: bool = False
    allow_overlap: bool = False
    request_id: Optional[str] = None
    seed: Optional[int] = None
    source_state: Optional[str] = None
    is_emergency: bool = False

@dataclass
class SpeechItem:
    text: str
    voice: VoiceSpec = field(default_factory=VoiceSpec)
    prosody: Prosody = field(default_factory=dict)
    meta: SpeechMeta = field(default_factory=SpeechMeta)
    created_at_ms: int = 0
