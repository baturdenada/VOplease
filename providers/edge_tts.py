import edge_tts
from typing import List
from providers.base import TTSProvider, Voice, TTSOptions, register_provider

@register_provider
class EdgeTTSProvider(TTSProvider):
    name = "edge"
    display_name = "Edge TTS (Free)"
    requires_api_key = False
    supports_speed = True
    default_voice = "en-US-AriaNeural"
    supported_formats = ["mp3", "wav"]
    max_text_length = 10000
    
    # Popular Edge TTS voices
    EDGE_VOICES = [
        Voice("en-US-AriaNeural", "Aria (US English)", "en-US", "female"),
        Voice("en-US-DavisNeural", "Davis (US English)", "en-US", "male"),
        Voice("en-US-GuyNeural", "Guy (US English)", "en-US", "male"),
        Voice("en-US-JennyNeural", "Jenny (US English)", "en-US", "female"),
        Voice("en-US-NancyNeural", "Nancy (US English)", "en-US", "female"),
        Voice("en-US-TonyNeural", "Tony (US English)", "en-US", "male"),
        Voice("en-GB-LibbyNeural", "Libby (UK English)", "en-GB", "female"),
        Voice("en-GB-RyanNeural", "Ryan (UK English)", "en-GB", "male"),
        Voice("en-GB-SoniaNeural", "Sonia (UK English)", "en-GB", "female"),
        Voice("en-AU-NatashaNeural", "Natasha (AU English)", "en-AU", "female"),
        Voice("en-AU-WilliamNeural", "William (AU English)", "en-AU", "male"),
        Voice("en-CA-ClaraNeural", "Clara (CA English)", "en-CA", "female"),
        Voice("en-CA-LiamNeural", "Liam (CA English)", "en-CA", "male"),
        Voice("en-IN-NeerjaNeural", "Neerja (IN English)", "en-IN", "female"),
        Voice("en-IN-PrabhatNeural", "Prabhat (IN English)", "en-IN", "male"),
        Voice("es-ES-ElviraNeural", "Elvira (ES Spanish)", "es-ES", "female"),
        Voice("es-ES-AlvaroNeural", "Alvaro (ES Spanish)", "es-ES", "male"),
        Voice("es-MX-DaliaNeural", "Dalia (MX Spanish)", "es-MX", "female"),
        Voice("es-MX-JorgeNeural", "Jorge (MX Spanish)", "es-MX", "male"),
        Voice("fr-FR-DeniseNeural", "Denise (FR French)", "fr-FR", "female"),
        Voice("fr-FR-HenriNeural", "Henri (FR French)", "fr-FR", "male"),
        Voice("de-DE-KatjaNeural", "Katja (DE German)", "de-DE", "female"),
        Voice("de-DE-ConradNeural", "Conrad (DE German)", "de-DE", "male"),
        Voice("it-IT-ElsaNeural", "Elsa (IT Italian)", "it-IT", "female"),
        Voice("it-IT-DiegoNeural", "Diego (IT Italian)", "it-IT", "male"),
        Voice("pt-BR-FranciscaNeural", "Francisca (BR Portuguese)", "pt-BR", "female"),
        Voice("pt-BR-AntonioNeural", "Antonio (BR Portuguese)", "pt-BR", "male"),
        Voice("ja-JP-NanamiNeural", "Nanami (JP Japanese)", "ja-JP", "female"),
        Voice("ja-JP-KeitaNeural", "Keita (JP Japanese)", "ja-JP", "male"),
        Voice("ko-KR-SunHiNeural", "SunHi (KR Korean)", "ko-KR", "female"),
        Voice("ko-KR-InJoonNeural", "InJoon (KR Korean)", "ko-KR", "male"),
        Voice("zh-CN-XiaoxiaoNeural", "Xiaoxiao (CN Chinese)", "zh-CN", "female"),
        Voice("zh-CN-YunxiNeural", "Yunxi (CN Chinese)", "zh-CN", "male"),
        Voice("zh-TW-HsiaoChenNeural", "HsiaoChen (TW Chinese)", "zh-TW", "female"),
        Voice("zh-TW-YunJheNeural", "YunJhe (TW Chinese)", "zh-TW", "male"),
    ]
    
    async def get_voices(self) -> List[Voice]:
        return self.EDGE_VOICES
    
    async def synthesize(self, options: TTSOptions) -> bytes:
        # Edge TTS expects rate as percentage like "+50%", pitch as "+50Hz" or "-50Hz", volume as "+50%"
        rate = f"{int((options.speed - 1) * 100):+}%" if options.speed != 1.0 else "+0%"
        pitch = f"{int(options.pitch * 50):+}Hz" if options.pitch != 0.0 else "+0Hz"
        volume = f"{int((options.volume - 1) * 100):+}%" if options.volume != 1.0 else "+0%"
        
        communicate = edge_tts.Communicate(
            text=options.text,
            voice=options.voice_id,
            rate=rate,
            pitch=pitch,
            volume=volume
        )
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return audio_data