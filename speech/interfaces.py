from abc import ABC, abstractmethod
from .types import VoiceSpec, Prosody, TTSAudio

class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: VoiceSpec, prosody: Prosody, *, seed: int = None, request_id: str = None) -> TTSAudio | None:
        pass

class AudioSink(ABC):
    @abstractmethod
    def play(self, audio: TTSAudio) -> bool:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

class NullTTSProvider(TTSProvider):
    def synthesize(self, text: str, voice: VoiceSpec, prosody: Prosody, *, seed: int = None, request_id: str = None) -> TTSAudio | None:
        return None

class NullAudioSink(AudioSink):
    def play(self, audio: TTSAudio) -> bool:
        return False
    def stop(self) -> None:
        pass
