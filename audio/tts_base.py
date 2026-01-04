from abc import ABC, abstractmethod

class TTSBase(ABC):
    @abstractmethod
    def synthesize(self, text: str, prosody: dict, out_path: str) -> bool:
        """
        Synthesize speech to out_path (wav). Return True on success, False on fail (never raise).
        prosody: dict with keys pitch, speed, energy (all floats, 1.0=neutral)
        """
        pass
