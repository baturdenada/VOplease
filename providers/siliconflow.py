import requests
from typing import List
from providers.base import TTSProvider, Voice, TTSOptions, register_provider

@register_provider
class SiliconFlowProvider(TTSProvider):
    name = "siliconflow"
    display_name = "SiliconFlow"
    requires_api_key = True
    supports_speed = True
    default_voice = "fishaudio/fish-speech-1.5"
    supported_formats = ["mp3", "wav"]
    max_text_length = 2000
    
    def __init__(self, api_key: str = "", base_url: str = "https://api.siliconflow.cn/v1", **kwargs):
        super().__init__(api_key, **kwargs)
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        } if api_key else {}
    
    async def get_voices(self) -> List[Voice]:
        # SiliconFlow voices - they have several models
        return [
            Voice("fishaudio/fish-speech-1.5", "Fish Speech 1.5", "en", "neutral"),
            Voice("fishaudio/fish-speech-1.4", "Fish Speech 1.4", "en", "neutral"),
            Voice("ChatTTS/ChatTTS", "ChatTTS", "en", "neutral"),
            Voice("THUDM/CogAudio", "CogAudio", "en", "neutral"),
        ]
    
    async def synthesize(self, options: TTSOptions) -> bytes:
        if not self.api_key:
            raise ValueError("SiliconFlow API key not configured")
        
        url = f"{self.base_url}/audio/speech"
        payload = {
            "model": options.voice_id,
            "input": options.text,
            "voice": options.voice_id.split("/")[-1],
            "response_format": options.output_format,
            "speed": options.speed,
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code == 200:
            return response.content
        else:
            raise RuntimeError(f"SiliconFlow TTS failed: {response.status_code} - {response.text}")