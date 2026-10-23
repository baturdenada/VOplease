# VOplease TTS Providers
from providers.base import TTSProvider, Voice, TTSOptions, ProviderRegistry, register_provider
from providers.edge_tts import EdgeTTSProvider
from providers.elevenlabs import ElevenLabsProvider
from providers.azure_tts import AzureTTSProvider
from providers.siliconflow import SiliconFlowProvider
from providers.gemini_tts import GeminiTTSProvider

__all__ = [
    "TTSProvider",
    "Voice",
    "TTSOptions",
    "ProviderRegistry",
    "EdgeTTSProvider",
    "ElevenLabsProvider",
    "AzureTTSProvider",
    "SiliconFlowProvider",
    "GeminiTTSProvider",
]
