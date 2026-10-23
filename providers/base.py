from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import asyncio

@dataclass
class Voice:
    id: str
    name: str
    language: str = "en"
    gender: str = "neutral"
    preview_url: str = ""

@dataclass
class TTSOptions:
    text: str
    voice_id: str
    speed: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    output_format: str = "mp3"  # mp3, wav, ogg
    sample_rate: int = 24000

class TTSProvider(ABC):
    name: str = "base"
    display_name: str = "Base Provider"
    requires_api_key: bool = True
    supports_speed: bool = True
    supports_streaming: bool = False
    default_voice: str = ""
    supported_formats: List[str] = ["mp3", "wav"]
    max_text_length: int = 5000
    
    def __init__(self, api_key: str = "", **kwargs):
        self.api_key = api_key
        self.config = kwargs
        self._voices_cache: List[Voice] = []
    
    @abstractmethod
    async def get_voices(self) -> List[Voice]:
        """Get list of available voices"""
        pass
    
    @abstractmethod
    async def synthesize(self, options: TTSOptions) -> bytes:
        """Generate audio from text"""
        pass
    
    async def synthesize_stream(self, options: TTSOptions) -> AsyncGenerator[bytes, None]:
        """Stream audio generation (optional)"""
        audio = await self.synthesize(options)
        yield audio
    
    def validate_api_key(self) -> bool:
        return bool(self.api_key) if self.requires_api_key else True
    
    def get_default_voice(self) -> str:
        if self.default_voice:
            return self.default_voice
        voices = asyncio.run(self.get_voices())
        return voices[0].id if voices else ""
    
    def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """Estimate audio duration in seconds"""
        words = len(text.split())
        words_per_minute = 150 * speed
        return (words / words_per_minute) * 60

class ProviderRegistry:
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, provider_class: type):
        cls._providers[provider_class.name] = provider_class
    
    @classmethod
    def get(cls, name: str) -> type:
        return cls._providers.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, type]:
        return cls._providers.copy()
    
    @classmethod
    def get_available(cls, api_keys: dict = None) -> Dict[str, type]:
        available = {}
        for name, cls_ in cls._providers.items():
            instance = cls_(api_keys.get(name, "") if api_keys else "")
            if instance.validate_api_key():
                available[name] = cls_
        return available

def register_provider(cls):
    ProviderRegistry.register(cls)
    return cls